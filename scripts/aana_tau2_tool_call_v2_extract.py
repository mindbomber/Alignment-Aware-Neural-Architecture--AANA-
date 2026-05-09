#!/usr/bin/env python
"""Extract τ²-style tool-call calibration rows from AANA trajectory artifacts."""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_TRAJECTORY_DIR = (
    ROOT
    / "eval_outputs"
    / "tau2_aana_gpt41mini_1trial_submission"
    / "aana-contract-gate-+-gpt-4-1-mini_aana_2026-05-07"
    / "trajectories"
)
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "benchmark_scout" / "aana_tau2_tool_call_v2_dataset.json"


def latest_user_before(messages: list[dict[str, Any]], turn_idx: int | None) -> str:
    for message in reversed(messages):
        if turn_idx is not None and message.get("turn_idx", -1) >= turn_idx:
            continue
        if message.get("role") == "user" and message.get("content"):
            return str(message["content"])[:900]
    return ""


def action_check_map(simulation: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    checks = ((simulation.get("reward_info") or {}).get("action_checks") or [])
    mapped: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(checks, list):
        return mapped
    for check in checks:
        action = check.get("action") if isinstance(check, dict) else None
        if not isinstance(action, dict):
            continue
        name = str(action.get("name") or "")
        if name:
            mapped.setdefault(name, []).append(check)
    return mapped


def gate_records_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    raw = message.get("raw_data") or {}
    if not isinstance(raw, dict):
        return []
    records = raw.get("aana_gate_records") or []
    return [record for record in records if isinstance(record, dict)]


def matching_gate_record(records: list[dict[str, Any]], tool_name: str) -> dict[str, Any] | None:
    for record in reversed(records):
        if record.get("tool_name") == tool_name:
            return record
    return records[-1] if records else None


def label_for_row(
    *,
    reward: float,
    tool_name: str,
    gate_record: dict[str, Any] | None,
    checks_by_tool: dict[str, list[dict[str, Any]]],
) -> tuple[str, str]:
    checks = checks_by_tool.get(tool_name, [])
    if any(check.get("action_match") is True or float(check.get("action_reward") or 0.0) > 0.0 for check in checks):
        return "should_execute", "matched_positive_action_check"
    if any(check.get("action_match") is False or float(check.get("action_reward") or 0.0) <= 0.0 for check in checks):
        return "should_block_or_ask", "failed_action_check"
    if gate_record and gate_record.get("validation_errors"):
        return "should_block_or_ask", "v1_schema_validation_failure"
    if reward >= 1.0 and (not gate_record or gate_record.get("recommended_action") == "accept"):
        return "should_execute", "successful_trajectory_accepted_tool"
    if reward <= 0.0 and gate_record and gate_record.get("recommended_action") != "accept":
        return "should_block_or_ask", "failed_trajectory_blocked_tool"
    return "review_or_holdout", "ambiguous_reward_without_action_check"


def row_from_tool_call(
    *,
    domain: str,
    file_name: str,
    simulation: dict[str, Any],
    message: dict[str, Any],
    tool_call: dict[str, Any],
    gate_record: dict[str, Any] | None,
    checks_by_tool: dict[str, list[dict[str, Any]]],
    index: int,
) -> dict[str, Any]:
    reward = float(((simulation.get("reward_info") or {}).get("reward") or 0.0))
    turn_idx = message.get("turn_idx")
    tool_name = str(tool_call.get("name") or (gate_record or {}).get("tool_name") or "")
    label, label_source = label_for_row(
        reward=reward,
        tool_name=tool_name,
        gate_record=gate_record,
        checks_by_tool=checks_by_tool,
    )
    return {
        "id": f"{domain}:{simulation.get('task_id')}:{simulation.get('trial')}:{turn_idx}:{index}:{tool_name}",
        "source_file": file_name,
        "domain": domain,
        "task_id": simulation.get("task_id"),
        "trial": simulation.get("trial"),
        "simulation_id": simulation.get("id"),
        "turn_idx": turn_idx,
        "reward": reward,
        "task_success": reward >= 1.0,
        "termination_reason": simulation.get("termination_reason"),
        "latest_user_message": latest_user_before(simulation.get("messages") or [], turn_idx),
        "tool_name": tool_name,
        "tool_arguments": tool_call.get("arguments") or {},
        "v1_gate_result": gate_record or {},
        "v1_recommended_action": (gate_record or {}).get("recommended_action"),
        "v1_gate_decision": (gate_record or {}).get("gate_decision"),
        "v1_tool_category": (gate_record or {}).get("tool_category"),
        "v1_authorization_state": (gate_record or {}).get("authorization_state"),
        "v1_hard_blockers": (gate_record or {}).get("hard_blockers", []),
        "v1_validation_errors": (gate_record or {}).get("validation_errors", []),
        "action_checks": checks_by_tool.get(tool_name, []),
        "label": label,
        "label_source": label_source,
    }


def extract_rows(trajectory_dir: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(trajectory_dir.glob("*_results.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        domain = str((data.get("info") or {}).get("environment_info", {}).get("domain_name") or path.name.removesuffix("_results.json"))
        for simulation in data.get("simulations") or []:
            checks_by_tool = action_check_map(simulation)
            for message in simulation.get("messages") or []:
                records = gate_records_from_message(message)
                tool_calls = message.get("tool_calls") or []
                if tool_calls:
                    for index, tool_call in enumerate(tool_calls):
                        gate_record = matching_gate_record(records, str(tool_call.get("name") or ""))
                        row = row_from_tool_call(
                            domain=domain,
                            file_name=path.name,
                            simulation=simulation,
                            message=message,
                            tool_call=tool_call,
                            gate_record=gate_record,
                            checks_by_tool=checks_by_tool,
                            index=index,
                        )
                        key = json.dumps([row["simulation_id"], row["turn_idx"], row["tool_name"], row["tool_arguments"]], sort_keys=True)
                        if key not in seen:
                            seen.add(key)
                            rows.append(row)
                    continue
                if records:
                    gate_record = records[-1]
                    row = row_from_tool_call(
                        domain=domain,
                        file_name=path.name,
                        simulation=simulation,
                        message=message,
                        tool_call={"name": gate_record.get("tool_name"), "arguments": {}},
                        gate_record=gate_record,
                        checks_by_tool=checks_by_tool,
                        index=0,
                    )
                    key = json.dumps([row["simulation_id"], row["turn_idx"], row["tool_name"], row["v1_recommended_action"]], sort_keys=True)
                    if key not in seen:
                        seen.add(key)
                        rows.append(row)
    return rows


def report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "label_counts": dict(Counter(row["label"] for row in rows)),
        "domain_counts": dict(Counter(row["domain"] for row in rows)),
        "label_source_counts": dict(Counter(row["label_source"] for row in rows)),
        "v1_route_counts": dict(Counter(str(row.get("v1_recommended_action")) for row in rows)),
        "schema_failure_rows": sum(1 for row in rows if row.get("v1_validation_errors")),
    }


def run(trajectory_dir: pathlib.Path, output: pathlib.Path) -> dict[str, Any]:
    rows = extract_rows(trajectory_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return {
        "benchmark": "AANA τ² Tool-Call v2 Dataset Extraction",
        "trajectory_dir": str(trajectory_dir),
        "output": str(output),
        **report(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory-dir", type=pathlib.Path, default=DEFAULT_TRAJECTORY_DIR)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.trajectory_dir, args.output), indent=2))


if __name__ == "__main__":
    main()
