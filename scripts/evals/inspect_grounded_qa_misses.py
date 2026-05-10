#!/usr/bin/env python
"""Write audit-safe diagnostics for Grounded QA / hallucination misses."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import Counter
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from scripts.hf.run_grounded_qa_hf_experiment import DEFAULT_EXPERIMENT, _load_json, load_cases  # noqa: E402
from adapter_runner.verifier_modules.grounded_qa import classify_grounded_answer  # noqa: E402


DEFAULT_INPUT = ROOT / "eval_outputs" / "grounded_qa_hf_experiment_results.json"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "grounded_qa_safe_miss_inspection.json"

QUESTION_CUE_TERMS = {
    "numeric_reasoning": (
        "how many",
        "how much",
        "percent",
        "percentage",
        "yards",
        "points",
        "more",
        "longest",
        "shortest",
        "second",
        "difference",
    ),
    "entity_selection": (
        "which",
        "who",
        "what team",
        "what title",
        "what person",
        "where",
        "when",
    ),
    "yes_no_or_verification": (
        "does",
        "did",
        "is",
        "are",
        "can",
        "was",
        "were",
    ),
    "unanswerable_or_missing_evidence": (
        "not enough",
        "cannot answer",
        "insufficient",
        "unanswerable",
        "unknown",
    ),
}


def _safe_question_cues(question: str) -> list[str]:
    lower = question.lower()
    cues = [name for name, terms in QUESTION_CUE_TERMS.items() if any(term in lower for term in terms)]
    return cues or ["general_factoid"]


def _parse_ragtruth_labels(case: dict[str, Any]) -> dict[str, int]:
    prompt = case.get("prompt", "")
    # RAGTruth labels are not present in normalized cases, so this function is
    # intentionally conservative. The result artifact already carries expected
    # unsupported status; detailed label subtype is unavailable without storing
    # dataset-specific raw label payloads.
    if case.get("schema") != "ragtruth_processed":
        return {}
    return {"processed_hallucination_label_present": int(case.get("unsupported", False) or "hallucination" in prompt.lower())}


def _safe_counts(text: str) -> dict[str, int]:
    return {
        "number_count": len(re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", text or "")),
        "list_marker_count": len(re.findall(r"[\[\],;]", text or "")),
        "capitalized_token_count": len(re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text or "")),
        "token_count": len(re.findall(r"[A-Za-z0-9]+", text or "")),
    }


def _diagnostic_clusters(result_row: dict[str, Any], case: dict[str, Any], classification: dict[str, Any]) -> list[str]:
    clusters: set[str] = set()
    question = str(case.get("prompt") or "")
    answer = str(case.get("answer") or "")
    question_cues = _safe_question_cues(question)

    if classification.get("numeric_consistency_gap") or "numeric_reasoning" in question_cues:
        clusters.add("numeric_reasoning")
    if classification.get("answer_shape_gap"):
        clusters.add("answer_shape_mismatch")
    if classification.get("entity_consistency_gap"):
        clusters.add("entity_consistency_gap")
    if classification.get("introduced_fact_gap"):
        clusters.add("introduced_fact_gap")
    if classification.get("evident_contradiction_gap"):
        clusters.add("evident_contradiction_gap")
    if "entity_selection" in question_cues and _safe_counts(answer)["capitalized_token_count"] > 0:
        clusters.add("entity_mismatch_likely")
    if result_row.get("schema") == "ragtruth_processed":
        clusters.add("contradiction_or_baseless_info_label")
    if classification.get("lexical_support_gap") or float(classification.get("unsupported_token_ratio") or 0.0) >= 0.30:
        clusters.add("lexical_support_gap_or_near_threshold")
    if "unanswerable_or_missing_evidence" in question_cues or classification.get("prompt_unanswerable"):
        clusters.add("missing_evidence_or_unanswerable")
    if result_row.get("actual_route") == "accept" and result_row.get("expected_route") != "accept":
        clusters.add("accepted_unsupported_answer")
    if result_row.get("actual_route") != "accept" and result_row.get("expected_route") == "accept":
        clusters.add("over_refusal")
    return sorted(clusters) or ["unclustered"]


def _case_key(source_dataset: str, case_id: str) -> str:
    return f"{source_dataset}::{case_id}"


def inspect_misses(
    *,
    result_payload: dict[str, Any],
    experiment: dict[str, Any],
    max_rows_per_source: int,
) -> dict[str, Any]:
    cases = load_cases(experiment=experiment, max_rows_per_source=max_rows_per_source)
    case_by_key = {_case_key(case["source_dataset"], case["id"]): case for case in cases}

    rows: list[dict[str, Any]] = []
    cluster_counts = Counter()
    miss_type_counts = Counter()

    for result_row in result_payload.get("rows", []):
        expected_route = result_row.get("expected_route")
        actual_route = result_row.get("actual_route")
        if expected_route == actual_route:
            continue
        key = _case_key(str(result_row.get("source_dataset")), str(result_row.get("id")))
        case = case_by_key.get(key)
        if not case:
            continue
        classification = classify_grounded_answer(case["prompt"], case["answer"])
        clusters = _diagnostic_clusters(result_row, case, classification)
        for cluster in clusters:
            cluster_counts[cluster] += 1
        miss_type = "unsupported_missed" if expected_route != "accept" and actual_route == "accept" else "over_refusal"
        miss_type_counts[miss_type] += 1
        rows.append(
            {
                "id": result_row.get("id"),
                "source_dataset": result_row.get("source_dataset"),
                "schema": result_row.get("schema"),
                "expected_label": result_row.get("expected_label"),
                "actual_label": result_row.get("actual_label"),
                "expected_route": expected_route,
                "actual_route": actual_route,
                "miss_type": miss_type,
                "question_sha256": result_row.get("question_sha256"),
                "context_sha256": result_row.get("context_sha256"),
                "answer_sha256": result_row.get("answer_sha256"),
                "question_cues": _safe_question_cues(case["prompt"]),
                "context_clusters": clusters,
                "answer_safe_counts": _safe_counts(case["answer"]),
                "context_safe_counts": _safe_counts(case["prompt"]),
                "diagnostic_signals": {
                    "answer_shape_gap": bool(classification.get("answer_shape_gap")),
                    "numeric_consistency_gap": bool(classification.get("numeric_consistency_gap")),
                    "entity_consistency_gap": bool(classification.get("entity_consistency_gap")),
                    "introduced_fact_gap": bool(classification.get("introduced_fact_gap")),
                    "evident_contradiction_gap": bool(classification.get("evident_contradiction_gap")),
                    "unsupported_proper_name_count": classification.get("unsupported_proper_name_count"),
                    "unsupported_numeric_fact_count": classification.get("unsupported_numeric_fact_count"),
                    "contradiction_signal_count": classification.get("contradiction_signal_count"),
                    "lexical_support_gap": bool(classification.get("lexical_support_gap")),
                    "unsupported_token_ratio": classification.get("unsupported_token_ratio"),
                    "ragtruth_label_summary": _parse_ragtruth_labels(case),
                },
                "recommended_next_step": _recommend_next_step(clusters),
            }
        )

    return {
        "schema_version": "0.1",
        "artifact_type": "grounded_qa_safe_miss_inspection",
        "raw_text_storage": "No raw context, question, or answer text is stored. Output contains hashes, route labels, safe counts, cue classes, diagnostic clusters, and next-step recommendations only.",
        "source_result_artifact": result_payload.get("experiment_id"),
        "detector_version": result_payload.get("detector_version"),
        "miss_count": len(rows),
        "miss_type_counts": dict(sorted(miss_type_counts.items())),
        "cluster_counts": dict(sorted(cluster_counts.items())),
        "rows": rows,
    }


def _recommend_next_step(clusters: list[str]) -> str:
    if "numeric_reasoning" in clusters:
        return "Add or calibrate arithmetic/equation evidence checks before route acceptance."
    if "entity_mismatch_likely" in clusters or "answer_shape_mismatch" in clusters:
        return "Add entity/answer-shape verification against question type and evidence candidates."
    if "contradiction_or_baseless_info_label" in clusters:
        return "Add contradiction/baseless-info detector or model-judged entailment layer."
    if "lexical_support_gap_or_near_threshold" in clusters:
        return "Calibrate lexical support thresholds on calibration splits before changing held-out rules."
    if "over_refusal" in clusters:
        return "Inspect false-positive threshold and preserve safe allow before tightening checks."
    return "Needs human-reviewed diagnostic labels before rule changes."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--experiment", default=str(DEFAULT_EXPERIMENT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--max-rows-per-source", type=int, default=50)
    args = parser.parse_args(argv)

    result_payload = _load_json(pathlib.Path(args.input))
    experiment = _load_json(pathlib.Path(args.experiment))
    report = inspect_misses(
        result_payload=result_payload,
        experiment=experiment,
        max_rows_per_source=args.max_rows_per_source,
    )
    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        "pass -- "
        f"misses={report['miss_count']} "
        f"types={report['miss_type_counts']} output={output_path}"
    )
    for cluster, count in report["cluster_counts"].items():
        print(f"- {cluster}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
