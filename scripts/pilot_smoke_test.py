#!/usr/bin/env python
"""Run an end-to-end smoke test for the AANA internal pilot profile."""

import argparse
import json
import os
import pathlib
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api, agent_server


DEFAULT_MANIFEST = ROOT / "examples" / "production_deployment_internal_pilot.json"
DEFAULT_EVENT = ROOT / "examples" / "agent_event_support_reply.json"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_MAX_BODY_BYTES = 1_048_576


class SmokeTestError(RuntimeError):
    pass


def load_json(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def manifest_audit_log_path(manifest_path):
    manifest = load_json(manifest_path)
    sink = manifest.get("audit", {}).get("sink", "")
    if isinstance(sink, str) and sink.startswith("jsonl://"):
        return pathlib.Path(sink.removeprefix("jsonl://"))
    return ROOT / "eval_outputs" / "audit" / "aana-pilot-smoke.jsonl"


def request_json(base_url, method, path, payload=None, token=None, timeout=10):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            return response.status, json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8")
        return exc.code, json.loads(response_body) if response_body else {}


def wait_for_health(base_url, timeout_seconds=5):
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while time.monotonic() < deadline:
        try:
            status, payload = request_json(base_url, "GET", "/health", timeout=1)
            if status == 200 and payload.get("status") == "ok":
                return payload
        except OSError as exc:
            last_error = exc
        time.sleep(0.05)
    raise SmokeTestError(f"Bridge health check did not pass for {base_url}: {last_error}")


def start_local_bridge(host, port, gallery_path, max_body_bytes, token, audit_log_path):
    handler = agent_server.make_handler(
        pathlib.Path(gallery_path),
        max_body_bytes=max_body_bytes,
        auth_token=token,
        audit_log_path=audit_log_path,
    )
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, name="aana-pilot-smoke-server", daemon=True)
    thread.start()
    actual_host, actual_port = server.server_address
    base_url = f"http://{actual_host}:{actual_port}"
    return server, thread, base_url


def assert_status(name, actual, expected):
    if actual != expected:
        raise SmokeTestError(f"{name} returned HTTP {actual}; expected HTTP {expected}.")


def assert_payload(name, condition, payload):
    if not condition:
        raise SmokeTestError(f"{name} returned unexpected payload: {json.dumps(payload, indent=2)}")


def run_smoke_test(args):
    event = load_json(args.event)
    token = args.token or os.environ.get("AANA_BRIDGE_TOKEN")
    audit_log = pathlib.Path(args.audit_log) if args.audit_log else manifest_audit_log_path(args.deployment_manifest)
    generated_token = False
    if not token and args.require_env_token:
        raise SmokeTestError("AANA_BRIDGE_TOKEN is required but not set.")
    if not token and not args.base_url:
        token = secrets.token_urlsafe(32)
        generated_token = True

    server = None
    server_thread = None
    base_url = args.base_url
    try:
        if base_url:
            if not token:
                raise SmokeTestError("--base-url requires --token or AANA_BRIDGE_TOKEN.")
        else:
            server, server_thread, base_url = start_local_bridge(
                args.host,
                args.port,
                args.gallery,
                args.max_body_bytes,
                token,
                audit_log,
            )

        health = wait_for_health(base_url, timeout_seconds=args.timeout)

        unauth_status, unauth_payload = request_json(base_url, "POST", "/validate-event", event, timeout=args.timeout)
        assert_status("unauthorized validate-event", unauth_status, 401)
        assert_payload(
            "unauthorized validate-event",
            unauth_payload.get("error") == "Unauthorized.",
            unauth_payload,
        )

        validate_status, validate_payload = request_json(
            base_url,
            "POST",
            "/validate-event",
            event,
            token=token,
            timeout=args.timeout,
        )
        assert_status("authorized validate-event", validate_status, 200)
        assert_payload("authorized validate-event", validate_payload.get("valid") is True, validate_payload)

        check_status, check_payload = request_json(
            base_url,
            "POST",
            "/agent-check",
            event,
            token=token,
            timeout=args.timeout,
        )
        assert_status("authorized agent-check", check_status, 200)

        metadata = event.get("metadata", {})
        expected_candidate_gate = metadata.get("expected_candidate_gate")
        expected_gate_decision = metadata.get("expected_gate_decision", "pass")
        expected_action = metadata.get("expected_recommended_action")
        assert_payload(
            "authorized agent-check",
            check_payload.get("gate_decision") == expected_gate_decision,
            check_payload,
        )
        if expected_candidate_gate:
            assert_payload(
                "authorized agent-check candidate gate",
                check_payload.get("candidate_gate") == expected_candidate_gate,
                check_payload,
            )
        if expected_action:
            assert_payload(
                "authorized agent-check recommended action",
                check_payload.get("recommended_action") == expected_action,
                check_payload,
            )

        client_audit = getattr(args, "client_audit", False)
        if client_audit:
            record = agent_api.audit_event_check(event, check_payload)
            agent_api.append_audit_record(audit_log, record)
        audit_summary = agent_api.summarize_audit_file(audit_log)
        assert_payload(
            "audit summary",
            audit_summary.get("total", 0) >= 1,
            audit_summary,
        )

        return {
            "status": "pass",
            "base_url": base_url,
            "started_local_bridge": server is not None,
            "generated_process_token": generated_token,
            "health": health,
            "auth": {
                "unauthorized_status": unauth_status,
                "authorized_validate_status": validate_status,
                "authorized_agent_check_status": check_status,
            },
            "agent_check": {
                "adapter_id": check_payload.get("adapter_id"),
                "candidate_gate": check_payload.get("candidate_gate"),
                "gate_decision": check_payload.get("gate_decision"),
                "recommended_action": check_payload.get("recommended_action"),
                "violations": [item.get("code") for item in check_payload.get("violations", [])],
            },
            "audit": {
                "audit_log": str(audit_log),
                "client_audit": client_audit,
                "summary": audit_summary,
            },
        }
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if server_thread is not None:
            server_thread.join(timeout=2)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run an AANA internal pilot HTTP/audit smoke test.")
    parser.add_argument("--base-url", default=None, help="Target an already-running bridge instead of starting one.")
    parser.add_argument("--host", default="127.0.0.1", help="Host for the local smoke-test bridge.")
    parser.add_argument("--port", type=int, default=0, help="Port for the local smoke-test bridge. Use 0 for an ephemeral port.")
    parser.add_argument("--token", default=None, help="Bridge token. Defaults to AANA_BRIDGE_TOKEN.")
    parser.add_argument("--require-env-token", action="store_true", help="Fail instead of generating a process-local token.")
    parser.add_argument("--event", default=DEFAULT_EVENT, help="Agent event JSON to send through the bridge.")
    parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON used by a locally started bridge.")
    parser.add_argument("--deployment-manifest", default=DEFAULT_MANIFEST, help="Deployment manifest used to resolve the default audit sink.")
    parser.add_argument("--audit-log", default=None, help="Audit JSONL path. Defaults to the deployment manifest jsonl:// audit sink.")
    parser.add_argument(
        "--client-audit",
        action="store_true",
        help="Append an audit record from the smoke-test client. Default expects the bridge to write audit records.",
    )
    parser.add_argument("--max-body-bytes", type=int, default=DEFAULT_MAX_BODY_BYTES, help="Local bridge max POST body bytes.")
    parser.add_argument("--timeout", type=float, default=10, help="HTTP timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        result = run_smoke_test(args)
    except SmokeTestError as exc:
        print(f"AANA pilot smoke test: FAIL - {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("AANA pilot smoke test: PASS")
        print(f"- Bridge: {result['base_url']}")
        print(f"- Started local bridge: {result['started_local_bridge']}")
        print(f"- Generated process-local token: {result['generated_process_token']}")
        print(f"- Auth rejection without token: HTTP {result['auth']['unauthorized_status']}")
        print(f"- Authenticated validate-event: HTTP {result['auth']['authorized_validate_status']}")
        print(f"- Authenticated agent-check: HTTP {result['auth']['authorized_agent_check_status']}")
        print(
            "- Gate: "
            f"candidate={result['agent_check']['candidate_gate']} "
            f"final={result['agent_check']['gate_decision']} "
            f"action={result['agent_check']['recommended_action']}"
        )
        print(f"- Audit log: {result['audit']['audit_log']}")
        print(f"- Client audit append: {result['audit']['client_audit']}")
        print(f"- Audit records: {result['audit']['summary']['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
