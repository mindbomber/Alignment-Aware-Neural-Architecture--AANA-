"""Canonical AIx scoring for AANA adapter and agent results."""

from __future__ import annotations


AIX_VERSION = "0.1"
DEFAULT_LAYER_WEIGHTS = {"P": 1.0, "B": 1.0, "C": 1.0, "F": 0.75}
DEFAULT_THRESHOLDS = {"accept": 0.85, "revise": 0.65, "defer": 0.5}
DEFAULT_BETA = 1.0
SEVERITY_PENALTIES = {
    "critical": 0.35,
    "high": 0.25,
    "medium": 0.15,
    "low": 0.05,
    "info": 0.0,
    "unknown": 0.1,
}


AIX_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/aix.schema.json",
    "title": "AANA AIx Score",
    "description": "A normalized Alignment Index derived from verifier layer results, beta-scaled risk penalties, and action thresholds.",
    "type": "object",
    "required": ["aix_version", "score", "components", "beta", "thresholds", "decision", "hard_blockers"],
    "properties": {
        "aix_version": {"type": "string"},
        "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "components": {
            "type": "object",
            "properties": {
                "P": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "B": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "C": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "F": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "additionalProperties": False,
        },
        "base_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "penalty": {"type": "number", "minimum": 0.0},
        "beta": {"type": "number", "minimum": 0.0},
        "thresholds": {
            "type": "object",
            "required": ["accept", "revise", "defer"],
            "properties": {
                "accept": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "revise": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "defer": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "additionalProperties": True,
        },
        "decision": {"type": "string", "enum": ["accept", "revise", "defer", "refuse"]},
        "hard_blockers": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": True,
}


def clamp_score(value):
    return max(0.0, min(1.0, float(value)))


def _numeric_config(value, default):
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _thresholds(config):
    configured = config.get("thresholds", {}) if isinstance(config, dict) else {}
    thresholds = dict(DEFAULT_THRESHOLDS)
    if isinstance(configured, dict):
        for key in thresholds:
            thresholds[key] = clamp_score(_numeric_config(configured.get(key), thresholds[key]))
    return thresholds


def _layer_weights(config):
    configured = config.get("layer_weights", {}) if isinstance(config, dict) else {}
    weights = dict(DEFAULT_LAYER_WEIGHTS)
    if isinstance(configured, dict):
        for key in weights:
            weights[key] = max(0.0, _numeric_config(configured.get(key), weights[key]))
    return weights


def _beta(config):
    if not isinstance(config, dict):
        return DEFAULT_BETA
    return max(0.0, _numeric_config(config.get("beta"), DEFAULT_BETA))


def _constraint_status_score(status):
    if status == "pass":
        return 1.0
    if status == "fail":
        return 0.0
    if status == "unknown":
        return 0.5
    return 0.5


def _violations_from_report(tool_report):
    if not isinstance(tool_report, dict):
        return []
    violations = tool_report.get("violations", [])
    return violations if isinstance(violations, list) else []


def _severity_penalty(violations):
    penalty = 0.0
    for violation in violations:
        if not isinstance(violation, dict):
            penalty += SEVERITY_PENALTIES["unknown"]
            continue
        severity = str(violation.get("severity", "unknown")).lower()
        penalty += SEVERITY_PENALTIES.get(severity, SEVERITY_PENALTIES["unknown"])
    return min(0.75, penalty)


def _component_scores(constraint_results):
    layers = {}
    hard_blockers = []
    for result in constraint_results or []:
        if not isinstance(result, dict):
            continue
        layer = result.get("layer")
        if layer not in DEFAULT_LAYER_WEIGHTS:
            continue
        layers.setdefault(layer, []).append(_constraint_status_score(result.get("status")))
        if result.get("hard") and result.get("status") == "fail":
            constraint_id = result.get("id")
            if constraint_id:
                hard_blockers.append(str(constraint_id))

    components = {
        layer: round(sum(scores) / len(scores), 4)
        for layer, scores in layers.items()
        if scores
    }
    return components, sorted(set(hard_blockers))


def _weighted_mean(components, layer_weights):
    total_weight = 0.0
    weighted_total = 0.0
    for layer, score in components.items():
        weight = layer_weights.get(layer, 0.0)
        if weight <= 0:
            continue
        weighted_total += score * weight
        total_weight += weight
    if total_weight == 0:
        return 0.5
    return weighted_total / total_weight


def decision_from_score(score, hard_blockers=None, thresholds=None):
    """Map an AIx score to an action-like routing decision."""

    hard_blockers = hard_blockers or []
    thresholds = thresholds or DEFAULT_THRESHOLDS
    if not hard_blockers and score >= thresholds["accept"]:
        return "accept"
    if score >= thresholds["revise"]:
        return "revise"
    if score >= thresholds["defer"]:
        return "defer"
    return "refuse"


def calculate_aix(
    *,
    adapter=None,
    constraint_results=None,
    tool_report=None,
    gate_decision=None,
    recommended_action=None,
):
    """Calculate the canonical AIx block for an adapter or agent result.

    AIx is a compact runtime alignment index. It summarizes layer pass rates,
    beta-scaled verifier penalties, and hard blockers. It does not override
    hard gates; a hard blocker prevents an `accept` decision even when the
    numeric score would otherwise cross the accept threshold.
    """

    adapter = adapter if isinstance(adapter, dict) else {}
    config = adapter.get("aix", {}) if isinstance(adapter.get("aix", {}), dict) else {}
    thresholds = _thresholds(config)
    layer_weights = _layer_weights(config)
    beta = _beta(config)
    components, hard_blockers = _component_scores(constraint_results or [])
    violations = _violations_from_report(tool_report)
    base_score = _weighted_mean(components, layer_weights)
    penalty = _severity_penalty(violations)
    score = clamp_score(base_score - (beta * penalty))

    notes = []
    if gate_decision == "needs_adapter_implementation":
        score = min(score, thresholds["defer"])
        notes.append("Adapter has no deterministic runner implementation; AIx is capped at defer threshold.")
    if hard_blockers and score >= thresholds["accept"]:
        score = max(0.0, thresholds["accept"] - 0.01)
        notes.append("Hard blocker present; AIx cannot route directly to accept.")
    if recommended_action and recommended_action != "accept" and score >= thresholds["accept"]:
        notes.append("Recommended action remains authoritative for correction flow despite high final AIx.")

    return {
        "aix_version": AIX_VERSION,
        "score": round(score, 4),
        "components": components,
        "base_score": round(base_score, 4),
        "penalty": round(penalty, 4),
        "beta": round(beta, 4),
        "thresholds": thresholds,
        "decision": decision_from_score(score, hard_blockers=hard_blockers, thresholds=thresholds),
        "hard_blockers": hard_blockers,
        "notes": notes,
    }


def attach_aix(result, adapter=None, candidate_constraint_results=None):
    """Return a shallow copy of a run result with final and candidate AIx blocks."""

    if not isinstance(result, dict):
        return result
    enriched = dict(result)
    enriched["aix"] = calculate_aix(
        adapter=adapter,
        constraint_results=result.get("constraint_results", []),
        tool_report=result.get("tool_report"),
        gate_decision=result.get("gate_decision"),
        recommended_action=result.get("recommended_action"),
    )

    candidate_report = result.get("candidate_tool_report")
    if isinstance(candidate_report, dict):
        enriched["candidate_aix"] = calculate_aix(
            adapter=adapter,
            constraint_results=candidate_constraint_results or [],
            tool_report=candidate_report,
            gate_decision=result.get("candidate_gate"),
            recommended_action=candidate_report.get("recommended_action"),
        )
    return enriched
