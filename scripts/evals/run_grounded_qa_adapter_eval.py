#!/usr/bin/env python
"""Run the Grounded QA / Hallucination adapter validation suite."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from adapter_runner.verifier_modules.grounded_qa import classify_grounded_answer, grounded_qa_tool_report
from eval_pipeline.hf_dataset_registry import load_registry, validate_hf_dataset_registry


DEFAULT_CASES = ROOT / "examples" / "grounded_qa_validation_cases.json"
DEFAULT_REGISTRY = ROOT / "examples" / "hf_dataset_validation_registry.json"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "grounded_qa_adapter_upgrade_results.json"


def _route_from_report(report: dict) -> str:
    routes = report.get("correction_routes") or {}
    for code in (
        "grounded_qa_high_impact_defer",
        "grounded_qa_unsupported_claim",
        "grounded_qa_unanswerable_answered",
        "grounded_qa_invalid_citation",
        "grounded_qa_citation_missing",
        "grounded_qa_evidence_gap_unlabeled",
    ):
        if code in routes:
            return routes[code]
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
        if dataset_name == "RAGTruth-style schema":
            continue
        if dataset_name not in allowed:
            errors.append(f"{case.get('id')}: source_dataset is not registered: {dataset_name}")
        elif split_role not in allowed[dataset_name]:
            errors.append(f"{case.get('id')}: split_role {split_role} is not allowed for {dataset_name}")
    return errors


def evaluate_cases(cases: list[dict]) -> dict:
    rows = []
    unsupported_total = 0
    unsupported_caught = 0
    answerable_total = 0
    answerable_allowed = 0
    citation_total = 0
    citation_covered = 0
    safe_total = 0
    safe_refused = 0
    route_correct = 0

    for case in cases:
        classification = classify_grounded_answer(case["prompt"], case["answer"])
        report = grounded_qa_tool_report(case["prompt"], case["answer"])
        actual_label = classification["label"]
        actual_route = _route_from_report(report)
        expected_label = case["expected_label"]
        expected_route = case["expected_route"]

        if case.get("unsupported"):
            unsupported_total += 1
            if actual_label in {"unsupported", "unanswerable", "defer"} or any(
                violation.get("code") == "grounded_qa_unsupported_claim"
                for violation in report.get("violations", [])
            ):
                unsupported_caught += 1

        if case.get("answerable") and expected_route == "accept":
            answerable_total += 1
            if actual_route == "accept" and actual_label == "supported":
                answerable_allowed += 1

        if case.get("citation_required") and expected_route == "accept":
            citation_total += 1
            answer_citations = set(classification["answer_citations"])
            indexed_citations = set(classification["indexed_citations"])
            if answer_citations and answer_citations <= indexed_citations and not classification["invalid_citations"]:
                citation_covered += 1

        if not case.get("unsupported"):
            safe_total += 1
            if actual_route in {"refuse", "defer"} and expected_route == "accept":
                safe_refused += 1

        if actual_label == expected_label and actual_route == expected_route:
            route_correct += 1

        rows.append(
            {
                "id": case["id"],
                "source_dataset": case["source_dataset"],
                "schema_style": case["schema_style"],
                "expected_label": expected_label,
                "actual_label": actual_label,
                "expected_route": expected_route,
                "actual_route": actual_route,
                "classification": classification,
                "violations": report.get("violations", []),
            }
        )

    total = len(cases)
    metrics = {
        "case_count": total,
        "unsupported_claim_recall": unsupported_caught / unsupported_total if unsupported_total else 0.0,
        "answerable_safe_allow_rate": answerable_allowed / answerable_total if answerable_total else 0.0,
        "citation_evidence_coverage": citation_covered / citation_total if citation_total else 0.0,
        "over_refusal_rate": safe_refused / safe_total if safe_total else 0.0,
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

    metrics = result["metrics"]
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            "pass -- "
            f"cases={metrics['case_count']} "
            f"unsupported_claim_recall={metrics['unsupported_claim_recall']:.3f} "
            f"answerable_safe_allow_rate={metrics['answerable_safe_allow_rate']:.3f} "
            f"citation_evidence_coverage={metrics['citation_evidence_coverage']:.3f} "
            f"over_refusal_rate={metrics['over_refusal_rate']:.3f} "
            f"route_accuracy={metrics['route_accuracy']:.3f} "
            f"output={output_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
