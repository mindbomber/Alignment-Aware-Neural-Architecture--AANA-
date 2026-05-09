#!/usr/bin/env python
"""Run the AANA Grounded QA / Hallucination Hugging Face validation experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from adapter_runner.verifier_modules.grounded_qa import classify_grounded_answer, grounded_qa_tool_report  # noqa: E402
from eval_pipeline.hf_dataset_registry import load_registry, validate_hf_dataset_registry  # noqa: E402
from eval_pipeline.semantic_verifier import build_semantic_verifier  # noqa: E402


DEFAULT_EXPERIMENT = ROOT / "examples" / "grounded_qa_hf_experiment.json"
DEFAULT_REGISTRY = ROOT / "examples" / "hf_dataset_validation_registry.json"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "grounded_qa_hf_experiment_results.json"
HF_ROWS_API = "https://datasets-server.huggingface.co/rows"


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


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
        for attempt in range(3):
            try:
                batch = _fetch_hf_rows(dataset_name, config, split, current_offset, batch_length)
                break
            except (OSError, TimeoutError) as exc:
                if attempt == 2:
                    raise RuntimeError(f"Failed to fetch {dataset_name} after retries: {exc}") from exc
                time.sleep(2 + attempt)
        rows.extend(batch)
        if len(batch) < batch_length:
            break
        current_offset += batch_length
        remaining -= batch_length
    return rows


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
    if experiment.get("adapter_family") != "grounded_qa":
        errors.append("experiment.adapter_family must be grounded_qa.")
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


def _ragtruth_hallucinated(label_value: Any) -> bool:
    if isinstance(label_value, str):
        try:
            label_value = json.loads(label_value)
        except json.JSONDecodeError:
            return bool(label_value and label_value != "[]")
    if isinstance(label_value, dict):
        return any(int(value or 0) > 0 for value in label_value.values())
    return bool(label_value)


def _expected_from_dataset(dataset: dict[str, Any], row: dict[str, Any]) -> tuple[bool, str, str]:
    schema = dataset["schema"]
    label = row.get(dataset["label_field"])
    if schema == "halubench":
        unsupported = str(label).upper() == "FAIL"
        return unsupported, "unsupported" if unsupported else "supported", "revise" if unsupported else "accept"
    if schema == "ragtruth_processed":
        unsupported = _ragtruth_hallucinated(label)
        return unsupported, "unsupported" if unsupported else "supported", "revise" if unsupported else "accept"
    if schema == "rag_grounded_qa":
        return False, "supported", "accept"
    return False, "supported", "accept"


def _route_from_report(report: dict[str, Any]) -> str:
    routes = report.get("correction_routes") or {}
    for code in (
        "grounded_qa_high_impact_defer",
        "grounded_qa_unsupported_claim",
        "grounded_qa_unanswerable_answered",
        "grounded_qa_invalid_citation",
        "grounded_qa_citation_missing",
        "grounded_qa_evidence_gap_unlabeled",
        "grounded_qa_semantic_unanswerable",
        "grounded_qa_semantic_uncertain",
        "grounded_qa_semantic_unsupported",
        "grounding_source_boundary_violation",
        "grounding_uncertainty_missing",
    ):
        if code in routes:
            return str(routes[code])
    return "accept"


def _audit_safe_semantic_result(semantic_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(semantic_result, dict):
        return None
    return {
        "semantic_verifier_version": semantic_result.get("semantic_verifier_version"),
        "provider": semantic_result.get("provider"),
        "model": semantic_result.get("model"),
        "task": semantic_result.get("task"),
        "label": semantic_result.get("label"),
        "route": semantic_result.get("route"),
        "confidence": semantic_result.get("confidence"),
        "reason_codes": semantic_result.get("reason_codes", []),
        "claim_level": {
            "claim_count": (semantic_result.get("claim_level") or {}).get("claim_count"),
            "unsupported_claim_count": (semantic_result.get("claim_level") or {}).get("unsupported_claim_count"),
            "unsupported_claim_types": (semantic_result.get("claim_level") or {}).get("unsupported_claim_types", []),
            "max_unsupported_claim_confidence": (semantic_result.get("claim_level") or {}).get("max_unsupported_claim_confidence"),
            "reason_codes": (semantic_result.get("claim_level") or {}).get("reason_codes", []),
        },
        "revision_required": semantic_result.get("revision_required"),
        "raw_payload_logged": False,
    }


def _case_from_row(dataset: dict[str, Any], row: dict[str, Any], index: int) -> dict[str, Any]:
    context = str(row.get(dataset["context_field"]) or "")
    question = str(row.get(dataset["question_field"]) or "")
    answer = str(row.get(dataset["answer_field"]) or "")
    unsupported, expected_label, expected_route = _expected_from_dataset(dataset, row)
    prompt = (
        "Citation optional. Use retrieved evidence as source. "
        f"Question: {question}\nRetrieved evidence:\n{context}"
    )
    case_id = str(row.get(dataset.get("id_field", "")) or f"{dataset['dataset_name']}:{index}")
    return {
        "id": case_id,
        "source_dataset": dataset["dataset_name"],
        "schema": dataset["schema"],
        "split_role": dataset["allowed_use"],
        "prompt": prompt,
        "answer": answer,
        "unsupported": unsupported,
        "expected_label": expected_label,
        "expected_route": expected_route,
        "answerable": not unsupported,
        "citation_required": False,
        "context_present": bool(context.strip()),
        "question_sha256": _sha256(question),
        "context_sha256": _sha256(context),
        "answer_sha256": _sha256(answer),
    }


def load_cases(*, experiment: dict[str, Any], max_rows_per_source: int) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for dataset in experiment.get("datasets", []):
        offsets = dataset.get("sample_offsets") or [0]
        per_offset = max(1, math.ceil(max_rows_per_source / len(offsets)))
        dataset_cases = []
        for offset in offsets:
            rows = _fetch_hf_rows_batched(
                dataset["dataset_name"],
                dataset["config"],
                dataset["split"],
                offset=int(offset),
                length=per_offset,
            )
            dataset_cases.extend(_case_from_row(dataset, row, int(offset) + index) for index, row in enumerate(rows))
        cases.extend(dataset_cases[:max_rows_per_source])
    return cases


def evaluate_cases(cases: list[dict[str, Any]], *, semantic_verifier: Any = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    by_dataset: dict[str, Counter] = defaultdict(Counter)
    totals = Counter()

    for case in cases:
        classification = classify_grounded_answer(case["prompt"], case["answer"])
        report = grounded_qa_tool_report(case["prompt"], case["answer"], semantic_verifier=semantic_verifier)
        semantic_result = (
            (report.get("checks") or [{}])[0].get("semantic_verifier")
            if isinstance((report.get("checks") or [{}])[0], dict)
            else None
        )
        actual_label = str(classification["label"])
        actual_route = _route_from_report(report)
        expected_route = case["expected_route"]
        unsupported = bool(case["unsupported"])
        supported = not unsupported
        aana_blocks = actual_route != "accept"

        totals["case_count"] += 1
        dataset_counter = by_dataset[case["source_dataset"]]
        dataset_counter["case_count"] += 1
        if unsupported:
            totals["unsupported_total"] += 1
            dataset_counter["unsupported_total"] += 1
            if aana_blocks or actual_label in {"unsupported", "unanswerable", "defer", "needs_citation"}:
                totals["unsupported_caught"] += 1
                dataset_counter["unsupported_caught"] += 1
        if supported:
            totals["supported_total"] += 1
            dataset_counter["supported_total"] += 1
            if actual_route == "accept":
                totals["supported_allowed"] += 1
                dataset_counter["supported_allowed"] += 1
            else:
                totals["supported_over_refused"] += 1
                dataset_counter["supported_over_refused"] += 1
        if case["context_present"]:
            totals["evidence_context_total"] += 1
            dataset_counter["evidence_context_total"] += 1
            if classification.get("citation_optional") or classification.get("answer_citations"):
                totals["evidence_context_covered"] += 1
                dataset_counter["evidence_context_covered"] += 1
        if actual_route == expected_route:
            totals["route_correct"] += 1
            dataset_counter["route_correct"] += 1

        rows.append(
            {
                "id": case["id"],
                "source_dataset": case["source_dataset"],
                "schema": case["schema"],
                "split_role": case["split_role"],
                "question_sha256": case["question_sha256"],
                "context_sha256": case["context_sha256"],
                "answer_sha256": case["answer_sha256"],
                "expected_label": case["expected_label"],
                "actual_label": actual_label,
                "expected_route": expected_route,
                "actual_route": actual_route,
                "base_accept_route": "accept",
                "aana_gate_blocks": aana_blocks,
                "classification": {
                    "label": actual_label,
                    "citation_optional": classification.get("citation_optional"),
                    "answer_abstains": classification.get("answer_abstains"),
                    "lexical_support_gap": classification.get("lexical_support_gap"),
                    "answer_shape_gap": classification.get("answer_shape_gap"),
                    "numeric_consistency_gap": classification.get("numeric_consistency_gap"),
                    "entity_consistency_gap": classification.get("entity_consistency_gap"),
                    "introduced_fact_gap": classification.get("introduced_fact_gap"),
                    "evident_contradiction_gap": classification.get("evident_contradiction_gap"),
                    "unsupported_proper_name_count": classification.get("unsupported_proper_name_count"),
                    "unsupported_numeric_fact_count": classification.get("unsupported_numeric_fact_count"),
                    "contradiction_signal_count": classification.get("contradiction_signal_count"),
                    "unsupported_token_ratio": classification.get("unsupported_token_ratio"),
                    "unsupported_terms": classification.get("unsupported_terms"),
                    "invalid_citations": classification.get("invalid_citations"),
                    "semantic_verifier": _audit_safe_semantic_result(semantic_result),
                },
                "violation_codes": [violation.get("code") for violation in report.get("violations", [])],
            }
        )

    def rate(num: str, den: str) -> float:
        return totals[num] / totals[den] if totals[den] else 0.0

    metrics = {
        "case_count": totals["case_count"],
        "unsupported_claim_recall": rate("unsupported_caught", "unsupported_total"),
        "answerable_safe_allow_rate": rate("supported_allowed", "supported_total"),
        "citation_evidence_coverage": rate("evidence_context_covered", "evidence_context_total"),
        "over_refusal_rate": rate("supported_over_refused", "supported_total"),
        "route_accuracy": rate("route_correct", "case_count"),
    }
    base_metrics = {
        "case_count": totals["case_count"],
        "unsupported_claim_recall": 0.0,
        "answerable_safe_allow_rate": 1.0 if totals["supported_total"] else 0.0,
        "citation_evidence_coverage": 0.0,
        "over_refusal_rate": 0.0,
        "route_accuracy": (totals["supported_total"] / totals["case_count"]) if totals["case_count"] else 0.0,
    }
    gate_metrics = {
        "case_count": totals["case_count"],
        "unsupported_claim_recall": metrics["unsupported_claim_recall"],
        "answerable_safe_allow_rate": metrics["answerable_safe_allow_rate"],
        "over_refusal_rate": metrics["over_refusal_rate"],
    }
    dataset_metrics = {}
    for dataset_name, counts in by_dataset.items():
        dataset_metrics[dataset_name] = {
            "case_count": counts["case_count"],
            "unsupported_claim_recall": counts["unsupported_caught"] / counts["unsupported_total"] if counts["unsupported_total"] else 0.0,
            "answerable_safe_allow_rate": counts["supported_allowed"] / counts["supported_total"] if counts["supported_total"] else 0.0,
            "over_refusal_rate": counts["supported_over_refused"] / counts["supported_total"] if counts["supported_total"] else 0.0,
            "route_accuracy": counts["route_correct"] / counts["case_count"] if counts["case_count"] else 0.0,
        }

    return {
        "metrics": metrics,
        "comparisons": {
            "base_accept_blindly": base_metrics,
            "aana_groundedness_gate": gate_metrics,
            "aana_revise_defer_route": metrics,
        },
        "dataset_metrics": dataset_metrics,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", default=str(DEFAULT_EXPERIMENT))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--max-rows-per-source", type=int, default=25)
    parser.add_argument("--semantic-verifier", choices=["none", "openai"], default="none")
    parser.add_argument("--semantic-model", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    experiment = _load_json(pathlib.Path(args.experiment))
    registry = load_registry(args.registry)
    errors = validate_experiment(experiment, registry)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1

    cases = load_cases(experiment=experiment, max_rows_per_source=args.max_rows_per_source)
    semantic_verifier = build_semantic_verifier(args.semantic_verifier, model=args.semantic_model)
    result = evaluate_cases(cases, semantic_verifier=semantic_verifier)
    result.update(
        {
            "experiment_id": experiment["experiment_id"],
            "claim_boundary": experiment["public_claim_boundary"],
            "detector_version": "grounded_qa_v1",
            "semantic_verifier": args.semantic_verifier,
            "semantic_model": args.semantic_model,
            "dataset_sources": experiment["datasets"],
            "raw_text_storage": experiment["outputs"]["raw_text_storage"],
        }
    )

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
