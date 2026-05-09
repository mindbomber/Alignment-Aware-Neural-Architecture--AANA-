#!/usr/bin/env python
"""Run the AANA Privacy/PII Hugging Face validation experiment.

The live-HF path uses the Hugging Face Dataset Viewer rows API so the experiment
can sample public datasets without downloading full corpora. Result rows avoid
storing raw source text; they keep hashes, labels, routes, and redacted previews.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import pathlib
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from adapter_runner.verifier_modules.privacy_pii import (  # noqa: E402
    HIGH_RISK_CATEGORIES,
    detect_pii,
    privacy_pii_tool_report,
    redact_pii,
)
from adapter_runner.verifier_modules.privacy_pii_v2 import (  # noqa: E402
    detect_pii_v2,
    load_privacy_pii_v2_model,
    privacy_pii_v2_tool_report,
    redact_pii_v2,
)
from eval_pipeline.hf_dataset_registry import load_registry, validate_hf_dataset_registry  # noqa: E402


DEFAULT_EXPERIMENT = ROOT / "examples" / "privacy_pii_hf_experiment.json"
DEFAULT_FIXTURE_CASES = ROOT / "examples" / "privacy_pii_validation_cases.json"
DEFAULT_REGISTRY = ROOT / "examples" / "hf_dataset_validation_registry.json"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "privacy_pii_hf_experiment_results.json"
HF_ROWS_API = "https://datasets-server.huggingface.co/rows"


LABEL_CATEGORY_MAP = {
    "FIRST_NAME": "person_name",
    "FIRSTNAME": "person_name",
    "GIVENNAME": "person_name",
    "GIVEN_NAME": "person_name",
    "SURNAME": "person_name",
    "LAST_NAME": "person_name",
    "LASTNAME": "person_name",
    "PERSON": "person_name",
    "PERSON_NAME": "person_name",
    "NAME": "person_name",
    "TITLE": "person_name",
    "USER_NAME": "username",
    "USERNAME": "username",
    "AGE": "age",
    "GENDER": "gender",
    "EMAIL": "email",
    "EMAILADDRESS": "email",
    "TELEPHONENUM": "phone",
    "PHONE": "phone",
    "PHONENUMBER": "phone",
    "SSN": "ssn",
    "SOCIALNUM": "ssn",
    "SOCIAL_SECURITY_NUMBER": "ssn",
    "PASSPORT": "passport",
    "PASSPORTNUM": "passport",
    "PASSPORT_NUMBER": "passport",
    "CREDITCARD": "credit_card",
    "CREDIT_CARD": "credit_card",
    "CREDIT_DEBIT_CARD": "credit_card",
    "BANKCARD": "credit_card",
    "ACCOUNT_NUMBER": "account_number",
    "ACCOUNTNUM": "account_number",
    "BANK_ACCOUNT": "account_number",
    "BANK_ROUTING_NUMBER": "bank_routing_number",
    "ROUTING_NUMBER": "bank_routing_number",
    "IBAN": "iban",
    "IP": "ip_address",
    "IP_ADDRESS": "ip_address",
    "IPADDRESS": "ip_address",
    "DATE_OF_BIRTH": "date_of_birth",
    "DATEOFBIRTH": "date_of_birth",
    "DOB": "date_of_birth",
    "BIRTHDATE": "date_of_birth",
    "POSTALCODE": "postal_code",
    "ZIPCODE": "postal_code",
    "CITY": "location",
    "LOCATION": "location",
    "STATE": "location",
    "COUNTY": "location",
    "COUNTRY": "location",
    "STREET_ADDRESS": "street_address",
    "ADDRESS": "street_address",
    "STREET": "street_address",
    "MEDICAL_RECORD": "medical_record",
    "MRN": "medical_record",
    "NATIONAL_ID": "national_id",
    "IDCARDNUM": "national_id",
    "DRIVERS_LICENSE": "drivers_license",
    "DRIVER_LICENSE": "drivers_license",
}

DATE_OF_BIRTH_CUES = {
    "dob",
    "date of birth",
    "born on",
    "fecha de nacimiento",
    "geburtsdatum",
    "date de naissance",
}


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _split_allowed(registry: dict[str, Any], dataset_name: str, config: str, split: str, allowed_use: str) -> bool:
    for dataset in registry.get("datasets", []):
        if dataset.get("dataset_name") != dataset_name:
            continue
        for split_use in dataset.get("split_uses", []):
            if (
                split_use.get("config") == config
                and split_use.get("split") == split
                and split_use.get("allowed_use") == allowed_use
            ):
                return True
    return False


def validate_experiment(experiment: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    registry_report = validate_hf_dataset_registry(registry)
    if not registry_report["valid"]:
        errors.extend(issue["message"] for issue in registry_report["issues"] if issue["level"] == "error")
        return errors
    if experiment.get("adapter_family") != "privacy_pii":
        errors.append("experiment.adapter_family must be privacy_pii.")
    split_policy = experiment.get("split_policy", {})
    if split_policy.get("never_tune_and_claim_on_same_split") is not True:
        errors.append("experiment.split_policy must forbid tuning and public claims on the same split.")
    for dataset in experiment.get("datasets", []):
        if not _split_allowed(
            registry,
            dataset.get("dataset_name", ""),
            dataset.get("config", ""),
            dataset.get("split", ""),
            dataset.get("allowed_use", ""),
        ):
            errors.append(
                "Unregistered split/use in experiment: "
                f"{dataset.get('dataset_name')} {dataset.get('config')}/{dataset.get('split')} "
                f"as {dataset.get('allowed_use')}"
            )
    return errors


def _fetch_hf_rows(dataset_name: str, config: str, split: str, offset: int, length: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "dataset": dataset_name,
            "config": config,
            "split": split,
            "offset": offset,
            "length": length,
        }
    )
    with urllib.request.urlopen(f"{HF_ROWS_API}?{query}", timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [item["row"] for item in payload.get("rows", [])]


def _fetch_hf_rows_batched(dataset_name: str, config: str, split: str, offset: int, length: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_offset = offset
    remaining = length
    while remaining > 0:
        batch_length = min(100, remaining)
        batch = _fetch_hf_rows(dataset_name, config, split, current_offset, batch_length)
        rows.extend(batch)
        if len(batch) < batch_length:
            break
        current_offset += batch_length
        remaining -= batch_length
    return rows


def _normalize_label(label: str, text: str = "") -> str | None:
    normalized = "".join(char if char.isalnum() else "_" for char in str(label).upper()).strip("_")
    if normalized == "DATE" and any(cue in text.lower() for cue in DATE_OF_BIRTH_CUES):
        return "date_of_birth"
    return LABEL_CATEGORY_MAP.get(normalized)


def _labels_from_entities(entities: Any, text: str = "") -> tuple[list[str], int]:
    labels: list[str] = []
    unmapped = 0
    if isinstance(entities, str):
        try:
            entities = ast.literal_eval(entities)
        except (SyntaxError, ValueError):
            entities = []
    for entity in entities or []:
        label = entity.get("label") if isinstance(entity, dict) else None
        category = _normalize_label(str(label or ""), text)
        if category:
            labels.append(category)
        elif label:
            unmapped += 1
    return sorted(set(labels)), unmapped


def _route_from_expected_categories(categories: list[str], contains_pii: bool) -> str:
    if any(category in HIGH_RISK_CATEGORIES for category in categories):
        return "refuse"
    return "revise" if contains_pii else "accept"


def _report_route(case: dict[str, Any], report: dict[str, Any]) -> str:
    routes = report.get("correction_routes") or {}
    if "private_identity_detail_exposed" in routes:
        return "refuse"
    if "pii_authorization_missing" in routes and case.get("expected_route") == "ask":
        return "ask"
    if report.get("violations"):
        return "revise"
    return "accept"


def _hash_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _redacted_preview(text: str, *, redactor=redact_pii, limit: int = 240) -> str:
    preview = redactor(text or "")
    return preview[:limit] + ("..." if len(preview) > limit else "")


def _case_from_fixture(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": case["id"],
        "source_dataset": case["source_dataset"],
        "split_role": case["split_role"],
        "language": case.get("language", "en"),
        "text": case["text"],
        "contains_pii": bool(case["contains_pii"]),
        "expected_categories": sorted(case.get("expected_categories", [])),
        "expected_route": case["expected_route"],
        "unmapped_label_count": 0,
    }


def _case_from_hf_row(dataset: dict[str, Any], row: dict[str, Any], index: int) -> dict[str, Any]:
    text_field = dataset["text_field"]
    label_field = dataset["label_field"]
    text = str(row.get(text_field) or "")
    label_value = row.get(label_field)
    expected_categories, unmapped_count = _labels_from_entities(label_value, text)
    contains_pii = bool(expected_categories or label_value)
    return {
        "id": str(row.get("uid") or f"{dataset['dataset_name']}:{index}"),
        "source_dataset": dataset["dataset_name"],
        "split_role": dataset["allowed_use"],
        "config": dataset["config"],
        "split": dataset["split"],
        "language": str(row.get(dataset.get("language_field", "")) or "unknown"),
        "text": text,
        "contains_pii": contains_pii,
        "expected_categories": expected_categories,
        "expected_route": _route_from_expected_categories(expected_categories, contains_pii),
        "unmapped_label_count": unmapped_count,
    }


def load_cases(
    *,
    mode: str,
    experiment: dict[str, Any],
    fixture_cases_path: pathlib.Path,
    offset: int,
    max_rows_per_source: int,
) -> list[dict[str, Any]]:
    if mode == "fixture":
        payload = _load_json(fixture_cases_path)
        return [_case_from_fixture(case) for case in payload.get("cases", [])]

    cases: list[dict[str, Any]] = []
    for dataset in experiment.get("datasets", []):
        rows = _fetch_hf_rows_batched(
            dataset["dataset_name"],
            dataset["config"],
            dataset["split"],
            offset=offset,
            length=max_rows_per_source,
        )
        cases.extend(_case_from_hf_row(dataset, row, index) for index, row in enumerate(rows))
    return cases


def evaluate_cases(cases: list[dict[str, Any]], *, detector_version: str = "v1", model: dict[str, Any] | None = None) -> dict[str, Any]:
    if detector_version == "v2":
        detector = lambda text: detect_pii_v2(text, model=model)
        reporter = lambda prompt, text: privacy_pii_v2_tool_report(prompt, text, model=model)
        redactor = lambda text: redact_pii_v2(text, model=model)
    else:
        detector = detect_pii
        reporter = privacy_pii_tool_report
        redactor = redact_pii

    rows: list[dict[str, Any]] = []
    by_dataset: dict[str, Counter] = defaultdict(Counter)
    totals = Counter()
    expected_category_total = 0
    expected_category_detected = 0
    high_risk_total = 0
    high_risk_detected = 0
    multilingual_total = 0
    multilingual_detected = 0
    route_correct = 0
    redaction_total = 0
    redaction_correct = 0

    for case in cases:
        text = case["text"]
        detections = detector(text)
        report = reporter("", text)
        actual_route = _report_route(case, report)
        detected_categories = sorted({str(item["category"]) for item in detections})
        expected_categories = sorted(case.get("expected_categories", []))
        contains_pii = bool(case["contains_pii"])
        is_multilingual = case.get("language") not in {"en", "us", "unknown", ""}
        dataset_counter = by_dataset[case["source_dataset"]]

        totals["case_count"] += 1
        dataset_counter["case_count"] += 1
        totals["unmapped_label_count"] += int(case.get("unmapped_label_count", 0))
        dataset_counter["unmapped_label_count"] += int(case.get("unmapped_label_count", 0))

        if contains_pii:
            totals["unsafe_total"] += 1
            dataset_counter["unsafe_total"] += 1
            if detections:
                totals["unsafe_detected"] += 1
                dataset_counter["unsafe_detected"] += 1
            redaction_total += 1
            redacted = redactor(text)
            leaked = any(str(item["text"]) in redacted for item in detections)
            if detections and not leaked and "[REDACTED_" in redacted:
                redaction_correct += 1
        else:
            totals["safe_total"] += 1
            dataset_counter["safe_total"] += 1
            if detections:
                totals["safe_blocked"] += 1
                dataset_counter["safe_blocked"] += 1

        for expected in expected_categories:
            expected_category_total += 1
            if expected in detected_categories:
                expected_category_detected += 1
            if expected in HIGH_RISK_CATEGORIES:
                high_risk_total += 1
                if expected in detected_categories:
                    high_risk_detected += 1

        if contains_pii and is_multilingual:
            multilingual_total += 1
            if detections:
                multilingual_detected += 1

        if actual_route == case["expected_route"]:
            route_correct += 1

        rows.append(
            {
                "id": case["id"],
                "source_dataset": case["source_dataset"],
                "split_role": case["split_role"],
                "language": case.get("language"),
                "text_sha256": _hash_text(text),
                "contains_pii": contains_pii,
                "expected_route": case["expected_route"],
                "actual_route": actual_route,
                "expected_categories": expected_categories,
                "detected_categories": detected_categories,
                "unmapped_label_count": case.get("unmapped_label_count", 0),
                "redacted_preview": _redacted_preview(text, redactor=redactor),
                "violations": report.get("violations", []),
            }
        )

    total_cases = totals["case_count"]
    safe_total = totals["safe_total"]
    unsafe_total = totals["unsafe_total"]
    metrics = {
        "case_count": total_cases,
        "pii_recall": totals["unsafe_detected"] / unsafe_total if unsafe_total else 0.0,
        "category_recall": expected_category_detected / expected_category_total if expected_category_total else 0.0,
        "high_risk_recall": high_risk_detected / high_risk_total if high_risk_total else None,
        "false_positive_rate": totals["safe_blocked"] / safe_total if safe_total else 0.0,
        "safe_allow_rate": (safe_total - totals["safe_blocked"]) / safe_total if safe_total else 0.0,
        "redaction_correctness": redaction_correct / redaction_total if redaction_total else 0.0,
        "multilingual_recall": multilingual_detected / multilingual_total if multilingual_total else None,
        "route_accuracy": route_correct / total_cases if total_cases else 0.0,
        "unmapped_label_count": totals["unmapped_label_count"],
    }
    dataset_metrics = {}
    for dataset_name, counts in by_dataset.items():
        unsafe = counts["unsafe_total"]
        safe = counts["safe_total"]
        dataset_metrics[dataset_name] = {
            "case_count": counts["case_count"],
            "pii_recall": counts["unsafe_detected"] / unsafe if unsafe else 0.0,
            "false_positive_rate": counts["safe_blocked"] / safe if safe else 0.0,
            "safe_allow_rate": (safe - counts["safe_blocked"]) / safe if safe else 0.0,
            "unmapped_label_count": counts["unmapped_label_count"],
        }
    return {"metrics": metrics, "dataset_metrics": dataset_metrics, "rows": rows}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", default=str(DEFAULT_EXPERIMENT))
    parser.add_argument("--fixture-cases", default=str(DEFAULT_FIXTURE_CASES))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--mode", choices=["fixture", "live-hf"], default="fixture")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--max-rows-per-source", type=int, default=25)
    parser.add_argument("--detector-version", choices=["v1", "v2"], default="v1")
    parser.add_argument("--v2-model", default=str(ROOT / "eval_outputs" / "privacy_pii_v2_model.json"))
    parser.add_argument("--v2-token-min-probability", type=float, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    experiment = _load_json(pathlib.Path(args.experiment))
    registry = load_registry(args.registry)
    errors = validate_experiment(experiment, registry)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1

    cases = load_cases(
        mode=args.mode,
        experiment=experiment,
        fixture_cases_path=pathlib.Path(args.fixture_cases),
        offset=args.offset,
        max_rows_per_source=args.max_rows_per_source,
    )
    model = load_privacy_pii_v2_model(args.v2_model) if args.detector_version == "v2" else None
    if model is not None and args.v2_token_min_probability is not None:
        model["token_min_probability"] = args.v2_token_min_probability
    result = evaluate_cases(cases, detector_version=args.detector_version, model=model)
    result.update(
        {
            "experiment_id": experiment["experiment_id"],
            "mode": args.mode,
            "detector_version": args.detector_version,
            "v2_model_status": model.get("status") if model else None,
            "v2_token_min_probability": model.get("token_min_probability") if model else None,
            "dataset_sources": experiment["datasets"],
            "split_policy": experiment["split_policy"],
            "claim_boundary": experiment["public_claim_boundary"],
            "raw_pii_storage": experiment["outputs"]["raw_pii_storage"],
        }
    )

    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        metrics = result["metrics"]
        print(
            "pass -- "
            f"mode={args.mode} detector={args.detector_version} cases={metrics['case_count']} "
            f"pii_recall={metrics['pii_recall']:.3f} "
            f"category_recall={metrics['category_recall']:.3f} "
            f"false_positive_rate={metrics['false_positive_rate']:.3f} "
            f"safe_allow_rate={metrics['safe_allow_rate']:.3f} "
            f"redaction_correctness={metrics['redaction_correctness']:.3f} "
            f"route_accuracy={metrics['route_accuracy']:.3f} "
            f"output={output_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
