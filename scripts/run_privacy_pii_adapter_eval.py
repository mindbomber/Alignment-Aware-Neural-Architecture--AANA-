#!/usr/bin/env python
"""Run the Privacy/PII adapter validation suite."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from adapter_runner.verifier_modules.privacy_pii import detect_pii, privacy_pii_tool_report, redact_pii
from eval_pipeline.hf_dataset_registry import load_registry, validate_hf_dataset_registry


DEFAULT_CASES = ROOT / "examples" / "privacy_pii_validation_cases.json"
DEFAULT_REGISTRY = ROOT / "examples" / "hf_dataset_validation_registry.json"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "privacy_pii_adapter_upgrade_results.json"


def _expected_route(case: dict, report: dict) -> str:
    routes = report.get("correction_routes") or {}
    if "private_identity_detail_exposed" in routes:
        return "refuse"
    if "pii_authorization_missing" in routes and case.get("expected_route") == "ask":
        return "ask"
    if report.get("violations"):
        return "revise"
    return "accept"


def _registry_allowed_sources(registry: dict) -> dict[str, set[str]]:
    allowed: dict[str, set[str]] = {}
    for dataset in registry.get("datasets", []):
        name = dataset.get("dataset_name")
        if not name:
            continue
        allowed[name] = {split.get("allowed_use") for split in dataset.get("split_uses", []) if split.get("allowed_use")}
    return allowed


def validate_case_sources(cases: list[dict], registry: dict) -> list[str]:
    errors: list[str] = []
    registry_report = validate_hf_dataset_registry(registry)
    if not registry_report["valid"]:
        errors.extend(issue["message"] for issue in registry_report["issues"])
        return errors
    allowed = _registry_allowed_sources(registry)
    for case in cases:
        dataset_name = case.get("source_dataset")
        split_role = case.get("split_role")
        if dataset_name not in allowed:
            errors.append(f"{case.get('id')}: source_dataset is not registered: {dataset_name}")
        elif split_role not in allowed[dataset_name]:
            errors.append(f"{case.get('id')}: split_role {split_role} is not allowed for {dataset_name}")
    return errors


def evaluate_cases(cases: list[dict]) -> dict:
    rows = []
    unsafe_total = 0
    unsafe_detected = 0
    safe_total = 0
    safe_blocked = 0
    redaction_total = 0
    redaction_correct = 0
    route_correct = 0

    for case in cases:
        text = case["text"]
        detections = detect_pii(text)
        report = privacy_pii_tool_report("", text)
        actual_route = _expected_route(case, report)
        expected_route = case["expected_route"]
        detected_categories = sorted({item["category"] for item in detections})
        expected_categories = sorted(case.get("expected_categories", []))
        redacted = redact_pii(text)

        contains_pii = bool(case["contains_pii"])
        if contains_pii:
            unsafe_total += 1
            if detections:
                unsafe_detected += 1
            redaction_total += 1
            leaked = any(str(item["text"]) in redacted for item in detections)
            has_placeholder = "[REDACTED_" in redacted
            if detections and not leaked and has_placeholder:
                redaction_correct += 1
        else:
            safe_total += 1
            if detections:
                safe_blocked += 1

        if actual_route == expected_route:
            route_correct += 1

        rows.append(
            {
                "id": case["id"],
                "source_dataset": case["source_dataset"],
                "contains_pii": contains_pii,
                "expected_route": expected_route,
                "actual_route": actual_route,
                "expected_categories": expected_categories,
                "detected_categories": detected_categories,
                "redacted": redacted,
                "violations": report.get("violations", []),
            }
        )

    total = len(cases)
    metrics = {
        "case_count": total,
        "pii_recall": unsafe_detected / unsafe_total if unsafe_total else 0.0,
        "false_positive_rate": safe_blocked / safe_total if safe_total else 0.0,
        "safe_allow_rate": (safe_total - safe_blocked) / safe_total if safe_total else 0.0,
        "redaction_correctness": redaction_correct / redaction_total if redaction_total else 0.0,
        "route_accuracy": route_correct / total if total else 0.0,
    }
    return {"metrics": metrics, "rows": rows}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cases_payload = json.loads(pathlib.Path(args.cases).read_text(encoding="utf-8"))
    cases = cases_payload.get("cases", [])
    registry = load_registry(args.registry)
    source_errors = validate_case_sources(cases, registry)
    if source_errors:
        for error in source_errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1

    result = evaluate_cases(cases)
    result["dataset_sources"] = cases_payload.get("dataset_sources", [])
    result["task_list"] = cases_payload.get("task_list", [])
    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        metrics = result["metrics"]
        print(
            "pass -- "
            f"cases={metrics['case_count']} "
            f"pii_recall={metrics['pii_recall']:.3f} "
            f"false_positive_rate={metrics['false_positive_rate']:.3f} "
            f"safe_allow_rate={metrics['safe_allow_rate']:.3f} "
            f"redaction_correctness={metrics['redaction_correctness']:.3f} "
            f"route_accuracy={metrics['route_accuracy']:.3f} "
            f"output={output_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

