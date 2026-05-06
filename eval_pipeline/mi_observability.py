"""MI observability dashboard metrics."""

from __future__ import annotations

import json
import pathlib
from typing import Any


MI_OBSERVABILITY_DASHBOARD_VERSION = "0.1"
GLOBAL_MODE = "full_global_aana_gate"


def _rate(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _global_mode(workflow: dict[str, Any]) -> dict[str, Any]:
    for mode in workflow.get("modes", []) if isinstance(workflow.get("modes"), list) else []:
        if isinstance(mode, dict) and mode.get("mode") == GLOBAL_MODE:
            return mode
    return {}


def _sum_counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        values = row.get(field)
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if isinstance(value, int):
                counts[str(key)] = counts.get(str(key), 0) + value
    return counts


def mi_dashboard_from_benchmark(benchmark_report: dict[str, Any]) -> dict[str, Any]:
    """Build dashboard-ready MI observability metrics from a benchmark report."""

    workflows = benchmark_report.get("workflows") if isinstance(benchmark_report, dict) else []
    workflow_rows = [workflow for workflow in workflows if isinstance(workflow, dict)] if isinstance(workflows, list) else []
    global_rows = [_global_mode(workflow) for workflow in workflow_rows]

    expected_positive = sum(1 for workflow in workflow_rows if workflow.get("expected_detection") is True)
    expected_negative = sum(1 for workflow in workflow_rows if workflow.get("expected_detection") is False)
    true_positive = false_negative = false_positive = true_negative = 0
    correction_success = 0
    propagated_workflows = 0
    drift_deltas = []
    max_drops = []

    handoff_total = 0
    handoff_blocked = 0
    handoff_pass = 0
    for workflow, mode in zip(workflow_rows, global_rows):
        expected = workflow.get("expected_detection") is True
        detected = mode.get("detected") is True
        if expected and detected:
            true_positive += 1
        elif expected and not detected:
            false_negative += 1
        elif not expected and detected:
            false_positive += 1
        else:
            true_negative += 1

        if expected and detected and int(mode.get("shared_correction_action_count") or 0) > 0:
            correction_success += 1
        if int(mode.get("propagated_risk_count") or 0) > 0:
            propagated_workflows += 1

        total = int(mode.get("handoff_total") or 0)
        blocked = int(mode.get("handoff_blocked") or 0)
        handoff_total += total
        handoff_blocked += blocked
        gate_decisions = mode.get("gate_decisions") if isinstance(mode.get("gate_decisions"), dict) else {}
        handoff_pass += int(gate_decisions.get("pass") or 0)

        delta = mode.get("workflow_score_delta")
        if isinstance(delta, (int, float)):
            drift_deltas.append(float(delta))
        max_drop = mode.get("workflow_max_drop")
        if isinstance(max_drop, (int, float)):
            max_drops.append(float(max_drop))

    gate_counts = _sum_counts(global_rows, "gate_decisions")
    action_counts = _sum_counts(global_rows, "recommended_actions")
    metrics = {
        "workflow_count": len(workflow_rows),
        "handoff_count": handoff_total,
        "handoff_pass_count": handoff_pass,
        "handoff_fail_count": handoff_blocked,
        "handoff_pass_rate": _rate(handoff_pass, handoff_total),
        "handoff_fail_rate": _rate(handoff_blocked, handoff_total),
        "propagated_error_workflow_count": propagated_workflows,
        "propagated_error_rate": _rate(propagated_workflows, len(workflow_rows)),
        "correction_success_count": correction_success,
        "correction_success_rate": _rate(correction_success, expected_positive),
        "false_accept_count": false_negative,
        "false_accept_rate": _rate(false_negative, expected_positive),
        "false_refusal_count": false_positive,
        "false_refusal_rate": _rate(false_positive, expected_negative),
        "global_aix_drift_average_delta": round(sum(drift_deltas) / len(drift_deltas), 4) if drift_deltas else 0.0,
        "global_aix_drift_min_delta": round(min(drift_deltas), 4) if drift_deltas else 0.0,
        "global_aix_drift_max_drop": round(max(max_drops), 4) if max_drops else 0.0,
        "global_aix_drift_detected_count": sum(1 for row in global_rows if row.get("workflow_drift_detected") is True),
        "true_positive": true_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
        "false_positive": false_positive,
    }

    return {
        "mi_observability_dashboard_version": MI_OBSERVABILITY_DASHBOARD_VERSION,
        "source": "mi_benchmark",
        "metrics": metrics,
        "panels": {
            "handoff_health": {
                "pass_rate": metrics["handoff_pass_rate"],
                "fail_rate": metrics["handoff_fail_rate"],
                "gate_decisions": gate_counts,
                "recommended_actions": action_counts,
            },
            "propagated_error": {
                "rate": metrics["propagated_error_rate"],
                "workflow_count": metrics["propagated_error_workflow_count"],
            },
            "correction": {
                "success_rate": metrics["correction_success_rate"],
                "success_count": metrics["correction_success_count"],
            },
            "classification_quality": {
                "false_accept_rate": metrics["false_accept_rate"],
                "false_refusal_rate": metrics["false_refusal_rate"],
                "true_positive": true_positive,
                "true_negative": true_negative,
            },
            "global_aix_drift": {
                "average_delta": metrics["global_aix_drift_average_delta"],
                "min_delta": metrics["global_aix_drift_min_delta"],
                "max_drop": metrics["global_aix_drift_max_drop"],
                "drift_detected_count": metrics["global_aix_drift_detected_count"],
            },
        },
        "workflow_rows": [
            {
                "workflow_id": workflow.get("workflow_id"),
                "expected_issue": workflow.get("expected_issue"),
                "expected_detection": workflow.get("expected_detection"),
                "global_detected": mode.get("detected"),
                "signals": mode.get("signals", []),
                "handoff_total": mode.get("handoff_total", 0),
                "handoff_blocked": mode.get("handoff_blocked", 0),
                "propagated_risk_count": mode.get("propagated_risk_count", 0),
                "shared_correction_action_count": mode.get("shared_correction_action_count", 0),
                "workflow_score_delta": mode.get("workflow_score_delta"),
                "workflow_max_drop": mode.get("workflow_max_drop"),
            }
            for workflow, mode in zip(workflow_rows, global_rows)
        ],
    }


def mi_dashboard_from_benchmark_file(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        return mi_dashboard_from_benchmark(json.load(handle))


def write_mi_dashboard(path: str | pathlib.Path, dashboard: dict[str, Any]) -> str:
    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dashboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(output_path)


def write_mi_dashboard_from_benchmark(
    benchmark_path: str | pathlib.Path,
    output_path: str | pathlib.Path,
) -> dict[str, Any]:
    dashboard = mi_dashboard_from_benchmark_file(benchmark_path)
    write_mi_dashboard(output_path, dashboard)
    return dashboard


__all__ = [
    "MI_OBSERVABILITY_DASHBOARD_VERSION",
    "mi_dashboard_from_benchmark",
    "mi_dashboard_from_benchmark_file",
    "write_mi_dashboard",
    "write_mi_dashboard_from_benchmark",
]
