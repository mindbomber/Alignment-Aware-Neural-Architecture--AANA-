import csv
import json
import os
import pathlib
import time
import urllib.error
import urllib.request


DEFAULT_TASKS = pathlib.Path("eval_outputs/heldout/heldout_ats_aana_tasks.jsonl")


def load_dotenv(path=".env"):
    path = pathlib.Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def read_jsonl(path):
    rows = []
    with pathlib.Path(path).open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no} of {path}: {exc}") from exc
    return rows


def append_jsonl(path, row):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path, rows, fieldnames):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_existing_keys(path):
    path = pathlib.Path(path)
    if not path.exists():
        return set()
    keys = set()
    for row in read_jsonl(path):
        keys.add((row["id"], row["model"], row["pressure"], row["correction"]))
    return keys


def extract_response_text(payload):
    if isinstance(payload, dict) and payload.get("output_text"):
        return payload["output_text"]

    parts = []
    for content in payload.get("content", []) if isinstance(payload, dict) else []:
        if content.get("type") == "text" and "text" in content:
            parts.append(content["text"])

    for item in payload.get("output", []) if isinstance(payload, dict) else []:
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and "text" in content:
                parts.append(content["text"])
    return "\n".join(parts).strip()


def responses_api_config():
    load_dotenv()
    api_key = os.environ.get("AANA_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("AANA_API_KEY or OPENAI_API_KEY is not set in the environment or .env.")

    explicit_url = os.environ.get("AANA_RESPONSES_URL") or os.environ.get("OPENAI_RESPONSES_URL")
    if explicit_url:
        return explicit_url, api_key

    base_url = os.environ.get("AANA_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    if base_url:
        return base_url.rstrip("/") + "/responses", api_key

    return "https://api.openai.com/v1/responses", api_key


def model_provider():
    load_dotenv()
    provider = os.environ.get("AANA_PROVIDER", "openai").strip().lower()
    aliases = {
        "openai_responses": "openai",
        "responses": "openai",
        "openai-compatible": "openai",
        "openai_compatible": "openai",
        "claude": "anthropic",
    }
    return aliases.get(provider, provider)


def anthropic_api_config():
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("AANA_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY or AANA_API_KEY is not set in the environment or .env.")

    explicit_url = os.environ.get("ANTHROPIC_MESSAGES_URL")
    if explicit_url:
        url = explicit_url
    else:
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        url = base_url.rstrip("/") + "/messages"

    version = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")
    return url, api_key, version


def build_model_request(*, model, system_prompt, user_prompt, max_output_tokens=450):
    provider = model_provider()
    if provider == "openai":
        responses_url, api_key = responses_api_config()
        return {
            "provider": provider,
            "url": responses_url,
            "headers": {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            "body": {
                "model": model,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_output_tokens": max_output_tokens,
            },
        }

    if provider == "anthropic":
        messages_url, api_key, version = anthropic_api_config()
        return {
            "provider": provider,
            "url": messages_url,
            "headers": {
                "x-api-key": api_key,
                "anthropic-version": version,
                "Content-Type": "application/json",
            },
            "body": {
                "model": model,
                "system": system_prompt,
                "max_tokens": max_output_tokens,
                "messages": [
                    {"role": "user", "content": user_prompt},
                ],
            },
        }

    raise RuntimeError(
        f"Unsupported AANA_PROVIDER {provider!r}. Supported providers: openai, anthropic."
    )


def post_json_with_retries(request_config, *, retries=3, timeout=120):
    data = json.dumps(request_config["body"]).encode("utf-8")
    request = urllib.request.Request(
        request_config["url"],
        data=data,
        headers=request_config["headers"],
        method="POST",
    )

    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {detail}"
            if exc.code not in {429, 500, 502, 503, 504}:
                break
        except urllib.error.URLError as exc:
            last_error = str(exc)
        time.sleep(2**attempt)
    raise RuntimeError(last_error or f"{request_config['provider']} API request failed.")


def call_responses_api(
    *,
    model,
    system_prompt,
    user_prompt,
    max_output_tokens=450,
    retries=3,
    timeout=120,
):
    request_config = build_model_request(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_output_tokens=max_output_tokens,
    )
    return post_json_with_retries(request_config, retries=retries, timeout=timeout)
