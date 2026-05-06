"""Reusable pre-execution hook for high-risk AANA actions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from eval_pipeline.connectivity_risk import DEFAULT_RISK_TIER_RULES
from eval_pipeline.production_readiness import production_mi_readiness_gate


PRE_EXECUTION_HOOK_VERSION = "0.1"
PRE_EXECUTION_DECISIONS = ("allow", "block", "retrieve", "revise", "ask", "defer", "refuse")


def _as_batch(handoff_batch: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(handoff_batch, dict):
        return {}
    if isinstance(handoff_batch.get("mi_batch"), dict):
        return deepcopy(handoff_batch["mi_batch"])
    return deepcopy(handoff_batch)


def _evidence_items(evidence: Any) -> list[dict[str, Any]]:
    if isinstance(evidence, dict):
        return [deepcopy(evidence)]
    if isinstance(evidence, list):
        return [deepcopy(item) for item in evidence if isinstance(item, dict)]
    return []


def _apply_evidence(batch: dict[str, Any], evidence: Any) -> int:
    items = _evidence_items(evidence)
    if not items:
        return 0

    results = batch.get("results")
    if not isinstance(results, list):
        return len(items)

    for result in results:
        if not isinstance(result, dict):
            continue
        summary = result.get("evidence_summary")
        raw = result.get("evidence")
        if not summary and not raw:
            result["evidence_summary"] = deepcopy(items)
    return len(items)


def _apply_risk_tier(batch: dict[str, Any], risk_tier: str | None) -> str | None:
    if risk_tier is None:
        global_aix = batch.get("global_aix") if isinstance(batch.get("global_aix"), dict) else {}
        return global_aix.get("risk_tier") if isinstance(global_aix.get("risk_tier"), str) else None

    batch.setdefault("global_aix", {})
    if not isinstance(batch["global_aix"], dict):
        batch["global_aix"] = {}
    batch["global_aix"]["risk_tier"] = risk_tier

    rules = DEFAULT_RISK_TIER_RULES.get(risk_tier)
    if not isinstance(rules, dict):
        return risk_tier
    thresholds = rules.get("thresholds") if isinstance(rules.get("thresholds"), dict) else {}
    global_thresholds = batch["global_aix"].setdefault("thresholds", {})
    if not isinstance(global_thresholds, dict):
        global_thresholds = {}
        batch["global_aix"]["thresholds"] = global_thresholds
    for key, value in thresholds.items():
        current = global_thresholds.get(key)
        if isinstance(current, (int, float)) and isinstance(value, (int, float)):
            global_thresholds[key] = max(float(current), float(value))
        else:
            global_thresholds.setdefault(key, value)
    return risk_tier


def _decision_from_readiness(readiness: dict[str, Any]) -> str:
    if readiness.get("can_execute_directly"):
        return "allow"

    blockers = set(readiness.get("blockers") if isinstance(readiness.get("blockers"), list) else [])
    if "evidence-present" in blockers:
        return "retrieve"
    if "propagation-resolved" in blockers:
        return "revise"
    if "no-hard-blockers" in blockers:
        return "block"
    if "global-aix-threshold" in blockers:
        action = readiness.get("recommended_action")
        return action if action in {"revise", "ask", "defer", "refuse"} else "defer"
    if "mi-checks-present" in blockers:
        return "defer"
    return "defer"


def pre_execution_hook(
    *,
    action_type: str,
    handoff_batch: dict[str, Any] | None = None,
    evidence: Any = None,
    risk_tier: str | None = None,
    high_risk_action: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gate a high-risk action before execution by reusing MI readiness checks.

    Agents, tools, plugins, and workflow steps should call this hook before
    sending, writing, deploying, exporting, deleting, or otherwise executing a
    consequential action. The hook accepts a checked MI handoff batch plus
    optional evidence/risk inputs and returns the execution route.
    """

    batch = _as_batch(handoff_batch)
    evidence_count = _apply_evidence(batch, evidence)
    selected_risk_tier = _apply_risk_tier(batch, risk_tier)
    readiness = production_mi_readiness_gate(batch, high_risk_action=high_risk_action)
    decision = _decision_from_readiness(readiness)

    return {
        "pre_execution_hook_version": PRE_EXECUTION_HOOK_VERSION,
        "gate": "pre_execution_hook",
        "action_type": action_type,
        "risk_tier": selected_risk_tier,
        "decision": decision,
        "allowed": decision == "allow",
        "recommended_action": readiness.get("recommended_action"),
        "blockers": readiness.get("blockers", []),
        "hard_blockers": readiness.get("hard_blockers", []),
        "missing_evidence_handoff_ids": readiness.get("missing_evidence_handoff_ids", []),
        "evidence_count": evidence_count,
        "production_mi_readiness": readiness,
        "metadata": dict(metadata) if isinstance(metadata, dict) else {},
    }


__all__ = [
    "PRE_EXECUTION_DECISIONS",
    "PRE_EXECUTION_HOOK_VERSION",
    "pre_execution_hook",
]
