#!/usr/bin/env python
"""Compare AANA v1 and v2 gate decisions on extracted τ² tool-call rows."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter, defaultdict
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.pre_tool_call_gate import gate_pre_tool_call, gate_pre_tool_call_v2  # noqa: E402
from scripts.benchmarks.aana_tau2_action_taxonomy_v2_train import DEFAULT_DATASET, event_from_row  # noqa: E402


DEFAULT_OUTPUT = ROOT / "eval_outputs" / "benchmark_scout" / "aana_tau2_v1_v2_comparison.json"


def load_rows(path: pathlib.Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def blocked(result: dict[str, Any]) -> bool:
    return result.get("recommended_action") != "accept" or result.get("gate_decision") != "pass" or bool(result.get("hard_blockers"))


def labeled_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("label") in {"should_execute", "should_block_or_ask"}]


def score(rows: list[dict[str, Any]], version: str) -> list[dict[str, Any]]:
    scored = []
    for row in rows:
        event = event_from_row(row)
        result = gate_pre_tool_call_v2(event) if version == "v2" else gate_pre_tool_call(event)
        should_block = row["label"] == "should_block_or_ask"
        did_block = blocked(result)
        scored.append(
            {
                "id": row["id"],
                "domain": row["domain"],
                "tool_name": row["tool_name"],
                "label": row["label"],
                "version": version,
                "recommended_action": result.get("recommended_action"),
                "gate_decision": result.get("gate_decision"),
                "hard_blockers": result.get("hard_blockers", []),
                "schema_failure": "schema_validation_failed" in result.get("hard_blockers", []),
                "blocked": did_block,
                "correct": did_block == should_block,
            }
        )
    return scored


def metrics(scored: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(scored)
    correct = sum(row["correct"] for row in scored)
    should_execute = [row for row in scored if row["label"] == "should_execute"]
    should_block = [row for row in scored if row["label"] == "should_block_or_ask"]
    return {
        "rows": total,
        "accuracy_pct": round((correct / total) * 100, 2) if total else 0.0,
        "execute_allow_pct": round((sum(not row["blocked"] for row in should_execute) / len(should_execute)) * 100, 2) if should_execute else 0.0,
        "block_recall_pct": round((sum(row["blocked"] for row in should_block) / len(should_block)) * 100, 2) if should_block else 0.0,
        "schema_failure_count": sum(row["schema_failure"] for row in scored),
        "route_counts": dict(Counter(str(row["recommended_action"]) for row in scored)),
    }


def grouped(scored: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored:
        groups[str(row.get(key))].append(row)
    return [{"name": name, **metrics(items)} for name, items in sorted(groups.items())]


def run(dataset: pathlib.Path, output: pathlib.Path) -> dict[str, Any]:
    rows = labeled_rows(load_rows(dataset))
    v1 = score(rows, "v1")
    v2 = score(rows, "v2")
    report = {
        "benchmark": "AANA τ² v1 vs v2 Tool-Call Gate Comparison",
        "dataset": str(dataset),
        "rows": len(rows),
        "v1_metrics": metrics(v1),
        "v2_metrics": metrics(v2),
        "v1_by_domain": grouped(v1, "domain"),
        "v2_by_domain": grouped(v2, "domain"),
        "schema_failure_delta": metrics(v1)["schema_failure_count"] - metrics(v2)["schema_failure_count"],
        "scored_samples": {"v1": v1[:20], "v2": v2[:20]},
        "scope": [
            "This compares gate decisions on extracted τ² v1 trajectory rows.",
            "It is not a replacement for a full τ² simulator rerun.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=pathlib.Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.output), indent=2))


if __name__ == "__main__":
    main()
