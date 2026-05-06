"""Connectivity-aware risk scaling for MI workflows."""

from __future__ import annotations

from typing import Any


CONNECTIVITY_RISK_VERSION = "0.1"
RISK_TIERS = ("low", "elevated", "high", "strict")
DEFAULT_RISK_TIER_RULES = {
    "low": {
        "min_connectivity": 0,
        "max_connectivity": 1,
        "irreversible": False,
        "beta": 1.0,
        "thresholds": {"accept": 0.85, "revise": 0.65, "defer": 0.5, "drift": 0.1},
        "required_correction_capacity": 1,
    },
    "elevated": {
        "min_connectivity": 2,
        "max_connectivity": 3,
        "irreversible": False,
        "beta": 1.15,
        "thresholds": {"accept": 0.9, "revise": 0.7, "defer": 0.55, "drift": 0.075},
        "required_correction_capacity": 2,
    },
    "high": {
        "min_connectivity": 4,
        "max_connectivity": 5,
        "irreversible": False,
        "beta": 1.35,
        "thresholds": {"accept": 0.93, "revise": 0.75, "defer": 0.6, "drift": 0.05},
        "required_correction_capacity": 3,
    },
    "strict": {
        "min_connectivity": 6,
        "max_connectivity": None,
        "irreversible": True,
        "beta": 1.6,
        "thresholds": {"accept": 0.96, "revise": 0.8, "defer": 0.65, "drift": 0.025},
        "required_correction_capacity": 4,
    },
}


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _bool(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.strip().lower() in {"true", "yes", "1"})


def _connectivity_from_item(item: dict[str, Any]) -> int:
    metadata = _metadata(item)
    for key in ("connectivity", "downstream_count", "blast_radius"):
        value = metadata.get(key)
        if isinstance(value, (int, float)):
            return max(0, int(value))
    propagation = item.get("propagation")
    if isinstance(propagation, dict) and isinstance(propagation.get("connectivity"), (int, float)):
        return max(0, int(propagation["connectivity"]))
    return 1


def _irreversible(item: dict[str, Any]) -> bool:
    metadata = _metadata(item)
    if any(_bool(metadata.get(key)) for key in ("irreversible", "irreversible_action", "requires_human_approval")):
        return True
    message_schema = item.get("message_schema")
    if isinstance(message_schema, dict) and _bool(message_schema.get("irreversible")):
        return True
    return any(
        _bool(violation.get("irreversible")) or violation.get("severity") == "critical"
        for violation in item.get("violations", []) if isinstance(violation, dict)
    )


def _declared_tier(item: dict[str, Any]) -> str | None:
    metadata = _metadata(item)
    for candidate in (
        metadata.get("mi_risk_tier"),
        metadata.get("risk_tier"),
        metadata.get("aix", {}).get("risk_tier") if isinstance(metadata.get("aix"), dict) else None,
    ):
        if candidate in RISK_TIERS:
            return str(candidate)
    return None


def _tier_rank(tier: str) -> int:
    return RISK_TIERS.index(tier)


def _max_tier(*tiers: str) -> str:
    return max(tiers, key=_tier_rank)


def tier_for_connectivity(connectivity: int, *, irreversible: bool = False) -> str:
    """Return the minimum MI risk tier required by connectivity and reversibility."""

    if irreversible or connectivity >= 6:
        return "strict"
    if connectivity >= 4:
        return "high"
    if connectivity >= 2:
        return "elevated"
    return "low"


def risk_tier_rules() -> dict[str, Any]:
    """Return the configured low/elevated/high/strict MI risk-tier rules."""

    return {
        "connectivity_risk_version": CONNECTIVITY_RISK_VERSION,
        "principle": "C_global >= D_global",
        "tiers": DEFAULT_RISK_TIER_RULES,
    }


def assess_connectivity_risk(handoff_results: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    """Assess workflow-level MI risk pressure from connectivity and irreversibility."""

    items = handoff_results.get("results") if isinstance(handoff_results, dict) else handoff_results
    results = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    connectivity_values = [_connectivity_from_item(item) for item in results]
    max_connectivity = max(connectivity_values) if connectivity_values else 0
    total_connectivity = sum(connectivity_values)
    irreversible = any(_irreversible(item) for item in results)
    inferred_tier = tier_for_connectivity(max_connectivity, irreversible=irreversible)

    declared_tiers = [tier for item in results for tier in [_declared_tier(item)] if tier]
    declared_tier = max(declared_tiers, key=_tier_rank) if declared_tiers else None
    tier = _max_tier(inferred_tier, declared_tier) if declared_tier else inferred_tier
    rules = DEFAULT_RISK_TIER_RULES[tier]

    correction_capacity = len(results)
    required_capacity = int(rules["required_correction_capacity"])
    capacity_gap = max(0, required_capacity - correction_capacity)
    capacity_sufficient = correction_capacity >= required_capacity

    return {
        "connectivity_risk_version": CONNECTIVITY_RISK_VERSION,
        "principle": "C_global >= D_global",
        "risk_tier": tier,
        "inferred_risk_tier": inferred_tier,
        "declared_risk_tier": declared_tier,
        "max_connectivity": max_connectivity,
        "total_connectivity": total_connectivity,
        "irreversible": irreversible,
        "beta": rules["beta"],
        "thresholds": dict(rules["thresholds"]),
        "required_correction_capacity": required_capacity,
        "observed_correction_capacity": correction_capacity,
        "capacity_sufficient": capacity_sufficient,
        "capacity_gap": capacity_gap,
        "notes": [] if capacity_sufficient else ["Correction capacity is below the selected MI risk-tier rule."],
    }


__all__ = [
    "CONNECTIVITY_RISK_VERSION",
    "DEFAULT_RISK_TIER_RULES",
    "RISK_TIERS",
    "assess_connectivity_risk",
    "risk_tier_rules",
    "tier_for_connectivity",
]
