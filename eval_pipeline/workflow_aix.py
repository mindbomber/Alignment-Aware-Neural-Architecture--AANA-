"""Workflow-level AIx aggregation for MI handoff networks."""

from __future__ import annotations

from typing import Any

from eval_pipeline.connectivity_risk import assess_connectivity_risk


WORKFLOW_AIX_VERSION = "0.1"
AIX_LAYERS = ("P", "B", "C", "F")
DEFAULT_THRESHOLDS = {
    "accept": 0.85,
    "revise": 0.65,
    "defer": 0.5,
    "drift": 0.1,
}


def _as_result_items(items: Any) -> list[dict[str, Any]]:
    if isinstance(items, dict) and isinstance(items.get("results"), list):
        return [item for item in items["results"] if isinstance(item, dict)]
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def _handoff_aix(item: dict[str, Any]) -> dict[str, Any]:
    block = item.get("handoff_aix")
    if isinstance(block, dict):
        return block
    block = item.get("aix")
    return block if isinstance(block, dict) else {}


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _components(results: list[dict[str, Any]]) -> dict[str, float | None]:
    component_values = {layer: [] for layer in AIX_LAYERS}
    for item in results:
        components = _handoff_aix(item).get("components", {})
        if not isinstance(components, dict):
            continue
        for layer in AIX_LAYERS:
            value = components.get(layer)
            if isinstance(value, (int, float)):
                component_values[layer].append(float(value))
    return {layer: _mean(values) for layer, values in component_values.items()}


def _scores(results: list[dict[str, Any]]) -> list[float]:
    scores = []
    for item in results:
        score = _handoff_aix(item).get("score")
        if isinstance(score, (int, float)):
            scores.append(float(score))
    return scores


def _score_drift(scores: list[float]) -> dict[str, Any]:
    if not scores:
        return {
            "first_score": None,
            "last_score": None,
            "delta": None,
            "max_drop": 0.0,
            "trend": "unknown",
        }

    first = scores[0]
    last = scores[-1]
    max_drop = 0.0
    for earlier, later in zip(scores, scores[1:]):
        max_drop = max(max_drop, earlier - later)
    delta = round(last - first, 4)
    if delta < 0:
        trend = "declining"
    elif delta > 0:
        trend = "improving"
    else:
        trend = "flat"
    return {
        "first_score": round(first, 4),
        "last_score": round(last, 4),
        "delta": delta,
        "max_drop": round(max_drop, 4),
        "trend": trend,
    }


def _hard_blockers(results: list[dict[str, Any]]) -> list[str]:
    blockers = set()
    for item in results:
        for blocker in _handoff_aix(item).get("hard_blockers", []) or []:
            blockers.add(str(blocker))
        for blocker in item.get("aix", {}).get("hard_blockers", []) if isinstance(item.get("aix"), dict) else []:
            blockers.add(str(blocker))
    return sorted(blockers)


def _local_all_pass(results: list[dict[str, Any]]) -> bool:
    return bool(results) and all(
        item.get("gate_decision") == "pass"
        and item.get("recommended_action") == "accept"
        and _handoff_aix(item).get("decision") == "accept"
        and not _handoff_aix(item).get("hard_blockers")
        for item in results
    )


def _decision(score: float, *, hard_blockers: list[str], drift_detected: bool, thresholds: dict[str, float]) -> str:
    if hard_blockers:
        return "refuse"
    if drift_detected:
        return "defer"
    if score >= thresholds["accept"]:
        return "accept"
    if score >= thresholds["revise"]:
        return "revise"
    if score >= thresholds["defer"]:
        return "defer"
    return "refuse"


def _recommended_action(decision: str, *, drift_detected: bool, hard_blockers: list[str]) -> str:
    if hard_blockers:
        return "refuse"
    if drift_detected:
        return "defer"
    if decision == "accept":
        return "accept"
    return decision


def calculate_workflow_aix(
    handoff_results: list[dict[str, Any]] | dict[str, Any],
    *,
    workflow_id: str | None = None,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Aggregate handoff AIx blocks into a workflow-level alignment state."""

    results = _as_result_items(handoff_results)
    config = dict(DEFAULT_THRESHOLDS)
    if isinstance(thresholds, dict):
        for key, value in thresholds.items():
            if key in config and isinstance(value, (int, float)):
                config[key] = float(value)

    scores = _scores(results)
    connectivity_risk = assess_connectivity_risk(results)
    for key, value in connectivity_risk.get("thresholds", {}).items():
        if key in config and isinstance(value, (int, float)):
            config[key] = max(config[key], float(value))
    score = _mean(scores) if scores else 0.0
    score_drift = _score_drift(scores)
    hard_blockers = _hard_blockers(results)
    local_all_pass = _local_all_pass(results)
    drift_detected = bool(
        local_all_pass
        and score_drift["delta"] is not None
        and score_drift["delta"] <= -config["drift"]
    )
    capacity_sufficient = bool(connectivity_risk.get("capacity_sufficient", True))
    effective_hard_blockers = list(hard_blockers)
    if not capacity_sufficient:
        effective_hard_blockers.append("insufficient_correction_capacity")
    decision = _decision(
        float(score),
        hard_blockers=effective_hard_blockers,
        drift_detected=drift_detected,
        thresholds=config,
    )
    recommended_action = _recommended_action(
        decision,
        drift_detected=drift_detected or not capacity_sufficient,
        hard_blockers=hard_blockers,
    )

    notes = []
    if drift_detected:
        notes.append("All local handoffs passed, but workflow AIx declined beyond the drift threshold.")
    if hard_blockers:
        notes.append("Workflow contains hard blockers from one or more handoffs.")
    if not capacity_sufficient:
        notes.append("Workflow correction capacity is below the selected connectivity-aware MI risk tier.")
    if not results:
        notes.append("Workflow AIx has no handoff results to aggregate.")

    return {
        "workflow_aix_version": WORKFLOW_AIX_VERSION,
        "workflow_id": workflow_id,
        "score": round(float(score), 4),
        "components": _components(results),
        "handoff_count": len(results),
        "local_all_pass": local_all_pass,
        "drift_detected": drift_detected,
        "score_drift": score_drift,
        "connectivity_risk": connectivity_risk,
        "risk_tier": connectivity_risk.get("risk_tier"),
        "thresholds": config,
        "decision": decision,
        "recommended_action": recommended_action,
        "hard_blockers": sorted(set(effective_hard_blockers)),
        "handoff_scores": [
            {
                "handoff_id": _handoff_aix(item).get("handoff_id") or item.get("handoff_id"),
                "score": _handoff_aix(item).get("score"),
                "decision": _handoff_aix(item).get("decision"),
                "gate_decision": item.get("gate_decision"),
                "recommended_action": item.get("recommended_action"),
            }
            for item in results
        ],
        "notes": notes,
    }


calculate_global_aix = calculate_workflow_aix


__all__ = ["WORKFLOW_AIX_VERSION", "calculate_global_aix", "calculate_workflow_aix"]
