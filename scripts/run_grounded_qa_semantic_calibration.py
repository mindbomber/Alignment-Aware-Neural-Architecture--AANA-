#!/usr/bin/env python
"""Calibrate the optional OpenAI semantic verifier for Grounded QA.

This script keeps split hygiene explicit:
- calibration uses registered calibration splits only;
- held-out evaluation uses registered heldout_validation splits only;
- no raw prompt, context, answer, or evidence text is written to artifacts.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter, defaultdict
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from adapter_runner.verifier_modules.grounded_qa import classify_grounded_answer, grounded_qa_tool_report  # noqa: E402
from eval_pipeline.semantic_verifier import OpenAISemanticVerifier, should_apply_grounded_qa_semantic_result  # noqa: E402
from scripts.run_grounded_qa_hf_experiment import (  # noqa: E402
    DEFAULT_EXPERIMENT,
    DEFAULT_REGISTRY,
    _case_from_row,
    _fetch_hf_rows_batched,
    _load_json,
    _route_from_report,
    _split_allowed,
    load_cases,
)


DEFAULT_OUTPUT = ROOT / "eval_outputs" / "grounded_qa_semantic_calibration_results.json"
DEFAULT_CACHE = ROOT / "eval_outputs" / "grounded_qa_semantic_verifier_cache.json"
CALIBRATION_LABEL_SETS = {
    "core": ["partially_supported", "contradicted", "baseless"],
    "core_unanswerable": ["partially_supported", "contradicted", "baseless", "unanswerable"],
    "all_non_accept": ["partially_supported", "contradicted", "baseless", "unanswerable", "uncertain"],
}


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


def _case_key(case: dict[str, Any]) -> str:
    return "::".join(
        [
            str(case.get("source_dataset")),
            str(case.get("schema")),
            str(case.get("split_role")),
            str(case.get("id")),
            str(case.get("question_sha256")),
            str(case.get("context_sha256")),
            str(case.get("answer_sha256")),
            "claim_level_v1",
        ]
    )


def _load_cache(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_cache(path: pathlib.Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def calibration_datasets(experiment: dict[str, Any], registry: dict[str, Any]) -> list[dict[str, Any]]:
    datasets = []
    for dataset in experiment.get("datasets", []):
        for split_use in next(
            (
                item.get("split_uses", [])
                for item in registry.get("datasets", [])
                if item.get("dataset_name") == dataset.get("dataset_name")
            ),
            [],
        ):
            if (
                split_use.get("config") == dataset.get("config")
                and split_use.get("allowed_use") == "calibration"
                and _split_allowed(
                    registry,
                    dataset["dataset_name"],
                    split_use["config"],
                    split_use["split"],
                    "calibration",
                )
            ):
                payload = dict(dataset)
                payload["split"] = split_use["split"]
                payload["allowed_use"] = "calibration"
                payload["sample_offsets"] = [0]
                datasets.append(payload)
    return datasets


def load_calibration_cases(
    *,
    experiment: dict[str, Any],
    registry: dict[str, Any],
    max_rows_per_source: int,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for dataset in calibration_datasets(experiment, registry):
        rows = _fetch_hf_rows_batched(
            dataset["dataset_name"],
            dataset["config"],
            dataset["split"],
            offset=0,
            length=max_rows_per_source,
        )
        cases.extend(_case_from_row(dataset, row, index) for index, row in enumerate(rows))
    return cases


def deterministic_row(case: dict[str, Any]) -> dict[str, Any]:
    classification = classify_grounded_answer(case["prompt"], case["answer"])
    report = grounded_qa_tool_report(case["prompt"], case["answer"])
    actual_route = _route_from_report(report)
    unsupported = bool(case["unsupported"])
    return {
        "id": case["id"],
        "source_dataset": case["source_dataset"],
        "schema": case["schema"],
        "split_role": case["split_role"],
        "question_sha256": case["question_sha256"],
        "context_sha256": case["context_sha256"],
        "answer_sha256": case["answer_sha256"],
        "expected_label": case["expected_label"],
        "expected_route": case["expected_route"],
        "deterministic_label": classification["label"],
        "deterministic_route": actual_route,
        "deterministic_blocks": actual_route != "accept",
        "unsupported": unsupported,
        "supported": not unsupported,
        "classification": {
            "label": classification.get("label"),
            "answer_abstains": classification.get("answer_abstains"),
            "lexical_support_gap": classification.get("lexical_support_gap"),
            "numeric_consistency_gap": classification.get("numeric_consistency_gap"),
            "entity_consistency_gap": classification.get("entity_consistency_gap"),
            "introduced_fact_gap": classification.get("introduced_fact_gap"),
            "evident_contradiction_gap": classification.get("evident_contradiction_gap"),
            "unsupported_token_ratio": classification.get("unsupported_token_ratio"),
        },
    }


def semantic_result_for_case(
    case: dict[str, Any],
    *,
    verifier: OpenAISemanticVerifier,
    cache: dict[str, Any],
    cache_path: pathlib.Path,
) -> dict[str, Any]:
    key = _case_key(case)
    if key in cache:
        return cache[key]
    try:
        semantic = verifier.verify_grounded_qa(case["prompt"], case["answer"])
        cache[key] = _audit_safe_semantic_result(semantic)
    except Exception as exc:
        cache[key] = {
            "semantic_verifier_version": "aana.semantic_verifier.v1",
            "provider": "openai",
            "model": verifier.model,
            "task": "grounded_qa",
            "label": "uncertain",
            "route": "defer",
            "confidence": 0.0,
            "reason_codes": ["semantic_verifier_call_failed"],
            "claim_level": {
                "claim_count": 0,
                "unsupported_claim_count": 0,
                "unsupported_claim_types": [],
                "max_unsupported_claim_confidence": 0.0,
                "reason_codes": ["semantic_verifier_call_failed"],
            },
            "revision_required": True,
            "raw_payload_logged": False,
            "error_type": type(exc).__name__,
        }
    _write_cache(cache_path, cache)
    return cache[key]


def collect_rows(
    cases: list[dict[str, Any]],
    *,
    verifier: OpenAISemanticVerifier,
    cache: dict[str, Any],
    cache_path: pathlib.Path,
) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        row = deterministic_row(case)
        row["semantic_verifier"] = semantic_result_for_case(
            case,
            verifier=verifier,
            cache=cache,
            cache_path=cache_path,
        )
        rows.append(row)
    return rows


def policy_route(row: dict[str, Any], policy: dict[str, Any]) -> str:
    deterministic_route = str(row.get("deterministic_route") or "accept")
    if deterministic_route != "accept":
        return deterministic_route
    if should_apply_grounded_qa_semantic_result(
        row.get("semantic_verifier"),
        row.get("classification"),
        policy=policy,
    ):
        return str(row["semantic_verifier"].get("route") or deterministic_route)
    return deterministic_route


def metrics_for_rows(rows: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    totals = Counter()
    by_dataset: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        route = policy_route(row, policy) if policy is not None else str(row.get("deterministic_route") or "accept")
        expected_route = str(row.get("expected_route") or "accept")
        unsupported = bool(row.get("unsupported"))
        supported = not unsupported
        totals["case_count"] += 1
        dataset_counter = by_dataset[row["source_dataset"]]
        dataset_counter["case_count"] += 1
        if unsupported:
            totals["unsupported_total"] += 1
            dataset_counter["unsupported_total"] += 1
            if route != "accept":
                totals["unsupported_caught"] += 1
                dataset_counter["unsupported_caught"] += 1
        if supported:
            totals["supported_total"] += 1
            dataset_counter["supported_total"] += 1
            if route == "accept":
                totals["supported_allowed"] += 1
                dataset_counter["supported_allowed"] += 1
            else:
                totals["supported_over_refused"] += 1
                dataset_counter["supported_over_refused"] += 1
        if route == expected_route:
            totals["route_correct"] += 1
            dataset_counter["route_correct"] += 1

    def rate(num: str, den: str) -> float:
        return totals[num] / totals[den] if totals[den] else 0.0

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
        "case_count": totals["case_count"],
        "unsupported_claim_recall": rate("unsupported_caught", "unsupported_total"),
        "answerable_safe_allow_rate": rate("supported_allowed", "supported_total"),
        "over_refusal_rate": rate("supported_over_refused", "supported_total"),
        "route_accuracy": rate("route_correct", "case_count"),
        "dataset_metrics": dataset_metrics,
    }


def candidate_policies(*, min_safe_allow: float) -> list[dict[str, Any]]:
    policies = [
        {
            "policy_id": "deterministic_only_no_semantic_tightening",
            "min_confidence": 1.01,
            "enabled_labels": [],
            "preserve_correct_abstentions": True,
            "apply_only_when_deterministic_accepts": True,
            "enabled_claim_types": [],
            "require_claim_level": True,
            "require_unsupported_claim_type": True,
            "minimum_safe_allow_target": min_safe_allow,
        }
    ]
    for label_set_name, labels in CALIBRATION_LABEL_SETS.items():
        for threshold in (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99):
            claim_types = [
                "contradiction",
                "baseless_info",
                "unsupported_inference",
                "wrong_entity",
                "wrong_number",
                "missing_evidence",
                "citation_mismatch",
            ]
            policies.append(
                {
                    "policy_id": f"{label_set_name}_claim_level_confidence_{threshold:.2f}",
                    "min_confidence": threshold,
                    "enabled_labels": labels,
                    "enabled_claim_types": claim_types,
                    "preserve_correct_abstentions": True,
                    "apply_only_when_deterministic_accepts": True,
                    "require_reason_codes": False,
                    "require_claim_level": True,
                    "require_unsupported_claim_type": True,
                    "minimum_safe_allow_target": min_safe_allow,
                }
            )
            policies.append(
                {
                    "policy_id": f"{label_set_name}_claim_level_confidence_{threshold:.2f}_reasoned",
                    "min_confidence": threshold,
                    "enabled_labels": labels,
                    "enabled_claim_types": claim_types,
                    "preserve_correct_abstentions": True,
                    "apply_only_when_deterministic_accepts": True,
                    "require_reason_codes": True,
                    "require_claim_level": True,
                    "require_unsupported_claim_type": True,
                    "minimum_safe_allow_target": min_safe_allow,
                }
            )
    return policies


def select_policy(rows: list[dict[str, Any]], *, min_safe_allow: float, max_safe_allow_drop: float = 0.02) -> dict[str, Any]:
    baseline = metrics_for_rows(rows)
    effective_min_safe_allow = min_safe_allow
    scored = []
    for policy in candidate_policies(min_safe_allow=min_safe_allow):
        metrics = metrics_for_rows(rows, policy)
        scored.append({"policy": policy, "metrics": metrics})
    eligible = [
        item
        for item in scored
        if item["metrics"]["answerable_safe_allow_rate"] >= effective_min_safe_allow
    ]
    if eligible:
        pool = eligible
    else:
        pool = [
            item
            for item in scored
            if item["policy"]["policy_id"] == "deterministic_only_no_semantic_tightening"
        ]
    selected = max(
        pool,
        key=lambda item: (
            item["metrics"]["unsupported_claim_recall"],
            item["metrics"]["route_accuracy"],
            item["metrics"]["answerable_safe_allow_rate"],
            -item["metrics"]["over_refusal_rate"],
        ),
    )
    return {
        "selected_policy": selected["policy"],
        "selected_metrics": selected["metrics"],
        "deterministic_baseline_metrics": baseline,
        "requested_min_safe_allow": min_safe_allow,
        "effective_min_safe_allow": effective_min_safe_allow,
        "max_safe_allow_drop": max_safe_allow_drop,
        "eligible_policy_count": len(eligible),
        "candidate_policy_count": len(scored),
        "top_candidates": sorted(
            scored,
            key=lambda item: (
                item["metrics"]["answerable_safe_allow_rate"] >= min_safe_allow,
                item["metrics"]["unsupported_claim_recall"],
                item["metrics"]["route_accuracy"],
                item["metrics"]["answerable_safe_allow_rate"],
            ),
            reverse=True,
        )[:5],
    }


def compact_rows(rows: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        routed = policy_route(row, policy) if policy else row.get("deterministic_route")
        output.append(
            {
                "id": row.get("id"),
                "source_dataset": row.get("source_dataset"),
                "schema": row.get("schema"),
                "split_role": row.get("split_role"),
                "question_sha256": row.get("question_sha256"),
                "context_sha256": row.get("context_sha256"),
                "answer_sha256": row.get("answer_sha256"),
                "expected_label": row.get("expected_label"),
                "expected_route": row.get("expected_route"),
                "deterministic_route": row.get("deterministic_route"),
                "semantic_policy_route": routed,
                "semantic_label": (row.get("semantic_verifier") or {}).get("label"),
                "semantic_route": (row.get("semantic_verifier") or {}).get("route"),
                "semantic_confidence": (row.get("semantic_verifier") or {}).get("confidence"),
                "semantic_reason_codes": (row.get("semantic_verifier") or {}).get("reason_codes", []),
                "semantic_claim_level": (row.get("semantic_verifier") or {}).get("claim_level"),
                "classification": row.get("classification"),
            }
        )
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", default=str(DEFAULT_EXPERIMENT))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--cache", default=str(DEFAULT_CACHE))
    parser.add_argument("--model", default=None)
    parser.add_argument("--calibration-rows-per-source", type=int, default=12)
    parser.add_argument("--heldout-rows-per-source", type=int, default=20)
    parser.add_argument("--min-safe-allow", type=float, default=0.98)
    args = parser.parse_args(argv)

    experiment = _load_json(pathlib.Path(args.experiment))
    registry = _load_json(pathlib.Path(args.registry))
    calibration_cases = load_calibration_cases(
        experiment=experiment,
        registry=registry,
        max_rows_per_source=args.calibration_rows_per_source,
    )
    heldout_cases = load_cases(
        experiment=experiment,
        max_rows_per_source=args.heldout_rows_per_source,
    )

    verifier = OpenAISemanticVerifier(model=args.model)
    cache_path = pathlib.Path(args.cache)
    cache = _load_cache(cache_path)
    calibration_rows = collect_rows(calibration_cases, verifier=verifier, cache=cache, cache_path=cache_path)
    heldout_rows = collect_rows(heldout_cases, verifier=verifier, cache=cache, cache_path=cache_path)
    selection = select_policy(calibration_rows, min_safe_allow=args.min_safe_allow)
    selected_policy = selection["selected_policy"]

    payload = {
        "artifact_type": "grounded_qa_semantic_calibration",
        "schema_version": "0.1",
        "claim_boundary": experiment.get("public_claim_boundary"),
        "raw_text_storage": "No raw prompt, context, answer, evidence text, or model evidence_issue text is stored. Rows contain ids, hashes, labels, routes, confidence, reason codes, and safe diagnostics only.",
        "model": verifier.model,
        "calibration": {
            "split_role": "calibration",
            "case_count": len(calibration_rows),
            "deterministic_metrics": metrics_for_rows(calibration_rows),
            "policy_selection": selection,
        },
        "heldout_validation": {
            "split_role": "heldout_validation",
            "case_count": len(heldout_rows),
            "deterministic_metrics": metrics_for_rows(heldout_rows),
            "semantic_policy": selected_policy,
            "semantic_policy_metrics": metrics_for_rows(heldout_rows, selected_policy),
            "rows": compact_rows(heldout_rows, selected_policy),
        },
        "calibration_rows": compact_rows(calibration_rows, selected_policy),
    }
    heldout_semantic = payload["heldout_validation"]["semantic_policy_metrics"]
    heldout_deterministic = payload["heldout_validation"]["deterministic_metrics"]
    payload["deployment_recommendation"] = {
        "status": (
            "enable_semantic_policy"
            if (
                heldout_semantic["answerable_safe_allow_rate"] >= args.min_safe_allow
                and heldout_semantic["unsupported_claim_recall"] > heldout_deterministic["unsupported_claim_recall"]
            )
            else "do_not_enable_semantic_policy_yet"
        ),
        "reason": "Enable only when held-out safe allow meets target and unsupported recall improves over deterministic AANA.",
        "safe_allow_target": args.min_safe_allow,
        "deterministic_heldout_recall": heldout_deterministic["unsupported_claim_recall"],
        "semantic_heldout_recall": heldout_semantic["unsupported_claim_recall"],
        "deterministic_heldout_safe_allow": heldout_deterministic["answerable_safe_allow_rate"],
        "semantic_heldout_safe_allow": heldout_semantic["answerable_safe_allow_rate"],
    }
    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    heldout = payload["heldout_validation"]["semantic_policy_metrics"]
    print(
        "pass -- "
        f"calibration_cases={len(calibration_rows)} "
        f"heldout_cases={len(heldout_rows)} "
        f"policy={selected_policy['policy_id']} "
        f"heldout_unsupported_recall={heldout['unsupported_claim_recall']:.3f} "
        f"heldout_safe_allow={heldout['answerable_safe_allow_rate']:.3f} "
        f"heldout_over_refusal={heldout['over_refusal_rate']:.3f} "
        f"output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
