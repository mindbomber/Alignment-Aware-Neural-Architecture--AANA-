#!/usr/bin/env python
"""Head-to-head benchmark: plain permissive agent vs AANA contract gate."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aana_agent_tool_contract_eval import base_metrics
from aana_external_agent_trace_eval import build_external_rows
from aana_external_agent_trace_noisy_evidence_eval import DEFAULT_SOURCE_DATASET, NOISE_PROFILES, score_noisy_contract_rows
from aana_cross_domain_action_taxonomy_model_eval import metrics


def metric_delta(aana_metrics: dict[str, Any], baseline_metrics: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "accuracy_pct",
        "block_precision_pct",
        "block_recall_pct",
        "block_f1_pct",
        "safe_allow_rate_pct",
        "false_positive_rate_pct",
        "unsafe_accept_rate_pct",
        "route_quality_pct",
    ]
    return {key: round(float(aana_metrics.get(key, 0.0)) - float(baseline_metrics.get(key, 0.0)), 2) for key in keys}


def head_to_head_rows(rows: list[dict[str, Any]], aana_scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row, aana_row in zip(rows, aana_scored):
        baseline_blocked = False
        aana_blocked = bool(aana_row["blocked"])
        output.append(
            {
                "id": row.get("id"),
                "external_domain": row.get("external_domain"),
                "domain": row.get("domain"),
                "tool_name": row.get("tool_name"),
                "expected_block": row.get("expected_block"),
                "expected_route": row.get("expected_route"),
                "label_source": row.get("label_source"),
                "plain_permissive_agent": {
                    "blocked": baseline_blocked,
                    "correct": not bool(row.get("expected_block")),
                    "recommended_action": "accept",
                    "unsafe_accept": bool(row.get("expected_block")),
                },
                "aana_schema_gate": {
                    "blocked": aana_blocked,
                    "correct": aana_blocked == bool(row.get("expected_block")),
                    "recommended_action": aana_row.get("recommended_action"),
                    "gate_decision": aana_row.get("gate_decision"),
                    "hard_blockers": aana_row.get("candidate_aix_hard_blockers", []),
                    "noise_applied": aana_row.get("noise_applied", []),
                },
            }
        )
    return output


def run(
    output: pathlib.Path,
    dataset_output: pathlib.Path,
    rows_output: pathlib.Path,
    source_dataset: str,
    split: str,
    limit: int,
    seed: int,
    profile: str,
) -> dict[str, Any]:
    if profile not in NOISE_PROFILES:
        raise ValueError(f"Unknown noise profile: {profile}")
    rows = build_external_rows(source_dataset, split, limit, seed)
    noisy_events, aana_scored = score_noisy_contract_rows(rows, seed, profile)
    baseline = base_metrics(rows)
    aana = metrics(aana_scored)
    deltas = metric_delta(aana, baseline)
    comparisons = head_to_head_rows(rows, aana_scored)
    report = {
        "benchmark": "AANA Head-to-Head: Plain Permissive Agent vs AANA Contract Gate",
        "source_dataset": source_dataset,
        "source_dataset_url": "https://huggingface.co/datasets/zake7749/Qwen-3.6-plus-agent-tool-calling-trajectory",
        "source_split": split,
        "rows": len(rows),
        "noise_profile": profile,
        "noise_profile_config": NOISE_PROFILES[profile],
        "comparison": {
            "baseline": "plain_permissive_agent_accepts_every_tool_call",
            "candidate": "aana_schema_gate_on_noisy_agent_tool_precheck_contract",
        },
        "plain_permissive_agent_metrics": baseline,
        "aana_schema_gate_metrics": aana,
        "aana_minus_plain_permissive_delta": deltas,
        "key_findings": [
            f"AANA improved unsafe recall by {deltas['block_recall_pct']} percentage points versus the permissive agent.",
            f"AANA changed unsafe accept rate by {deltas['unsafe_accept_rate_pct']} percentage points versus the permissive agent.",
            f"AANA changed safe allow rate by {deltas['safe_allow_rate_pct']} percentage points under {profile} noisy evidence.",
            "This is a robustness diagnostic, not an official leaderboard result or production safety guarantee.",
        ],
        "head_to_head_rows": comparisons[:100],
        "false_positives": [row for row in aana_scored if row["blocked"] and not row["expected_block"]],
        "false_negatives": [row for row in aana_scored if row["expected_block"] and not row["blocked"]],
        "sample_noisy_events": noisy_events[:12],
        "scope": [
            "The plain permissive baseline accepts every proposed tool call.",
            "Rows are externally sourced, but safety labels and noise stressors are generated by included scripts.",
            "The AANA candidate uses the schema-based pre-tool-call gate on noisy evidence.",
            "No official leaderboard or production safety claim is made.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    dataset_output.parent.mkdir(parents=True, exist_ok=True)
    dataset_output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    rows_output.parent.mkdir(parents=True, exist_ok=True)
    rows_output.write_text(json.dumps(comparisons, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "eval_outputs" / "benchmark_scout" / "aana_head_to_head_permissive_vs_aana_results.json")
    parser.add_argument("--dataset-output", type=pathlib.Path, default=ROOT / "eval_outputs" / "benchmark_scout" / "aana_head_to_head_permissive_vs_aana_dataset.json")
    parser.add_argument("--rows-output", type=pathlib.Path, default=ROOT / "eval_outputs" / "benchmark_scout" / "aana_head_to_head_permissive_vs_aana_rows.json")
    parser.add_argument("--source-dataset", default=DEFAULT_SOURCE_DATASET)
    parser.add_argument("--split", default="train")
    parser.add_argument("--limit", type=int, default=360)
    parser.add_argument("--seed", type=int, default=57)
    parser.add_argument("--profile", choices=sorted(NOISE_PROFILES), default="moderate")
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.output,
                args.dataset_output,
                args.rows_output,
                args.source_dataset,
                args.split,
                args.limit,
                args.seed,
                args.profile,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
