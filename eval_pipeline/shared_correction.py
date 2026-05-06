"""Shared network-level correction policy for MI workflows."""

from __future__ import annotations

from typing import Any

from eval_pipeline.connectivity_risk import assess_connectivity_risk
from eval_pipeline.propagated_risk import track_propagated_risk


SHARED_CORRECTION_POLICY_VERSION = "0.1"
CORRECTION_ACTIONS = (
    "retrieve_evidence",
    "revise_upstream_output",
    "ask_clarification",
    "defer_human_review",
)


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("results"), list):
        return [item for item in value["results"] if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _handoff_id(item: dict[str, Any], index: int) -> str:
    return str(item.get("handoff_id") or item.get("handoff_aix", {}).get("handoff_id") or f"handoff-{index}")


def _sender_id(item: dict[str, Any]) -> str | None:
    sender = item.get("sender")
    return sender.get("id") if isinstance(sender, dict) else item.get("sender_id")


def _recipient_id(item: dict[str, Any]) -> str | None:
    recipient = item.get("recipient")
    return recipient.get("id") if isinstance(recipient, dict) else item.get("recipient_id")


def _severity_rank(severity: str | None) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}.get(str(severity), 1)


def _add_action(
    actions: list[dict[str, Any]],
    *,
    action: str,
    target_handoff_id: str | None,
    requested_by_handoff_id: str | None,
    target_agent_id: str | None = None,
    requested_by_agent_id: str | None = None,
    reason: str,
    severity: str = "medium",
    source: str | None = None,
    network_scope: str = "handoff",
) -> None:
    if action not in CORRECTION_ACTIONS:
        return
    action_id = f"{action}:{target_handoff_id}:{requested_by_handoff_id}:{source}:{reason}"
    if any(item.get("correction_id") == action_id for item in actions):
        return
    actions.append(
        {
            "correction_id": action_id,
            "action": action,
            "target_handoff_id": target_handoff_id,
            "requested_by_handoff_id": requested_by_handoff_id,
            "target_agent_id": target_agent_id,
            "requested_by_agent_id": requested_by_agent_id,
            "reason": reason,
            "severity": severity,
            "source": source,
            "network_scope": network_scope,
            "status": "pending",
        }
    )


def _risk_action(risk: dict[str, Any]) -> str:
    kind = risk.get("kind")
    if kind == "stale_evidence":
        return "retrieve_evidence"
    if kind in {"unsupported_claim", "accepted_violation"}:
        return "revise_upstream_output"
    if kind == "hidden_assumption":
        return "ask_clarification" if risk.get("severity") in {"medium", "low", "info"} else "revise_upstream_output"
    return "defer_human_review"


def _result_action(item: dict[str, Any]) -> str | None:
    recommended = item.get("recommended_action")
    if recommended == "retrieve":
        return "retrieve_evidence"
    if recommended == "revise":
        return "revise_upstream_output"
    if recommended == "ask":
        return "ask_clarification"
    if recommended == "defer":
        return "defer_human_review"
    return None


def shared_correction_policy(workflow_result: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    """Plan correction intents across a handoff network.

    This policy does not execute corrections. It makes the cross-agent
    correction request explicit so downstream agents can route back to
    upstream producers, evidence retrieval, clarification, or human review.
    """

    results = _items(workflow_result)
    result_by_id = {_handoff_id(item, index): item for index, item in enumerate(results)}
    propagated_risk = (
        workflow_result.get("propagated_risk")
        if isinstance(workflow_result, dict) and isinstance(workflow_result.get("propagated_risk"), dict)
        else track_propagated_risk(results)
    )
    workflow_aix = workflow_result.get("workflow_aix") if isinstance(workflow_result, dict) else None
    connectivity_risk = (
        workflow_aix.get("connectivity_risk")
        if isinstance(workflow_aix, dict) and isinstance(workflow_aix.get("connectivity_risk"), dict)
        else assess_connectivity_risk(results)
    )

    actions: list[dict[str, Any]] = []
    for index, item in enumerate(results):
        action = _result_action(item)
        if not action:
            continue
        handoff_id = _handoff_id(item, index)
        _add_action(
            actions,
            action=action,
            target_handoff_id=handoff_id,
            requested_by_handoff_id=handoff_id,
            target_agent_id=_sender_id(item),
            requested_by_agent_id=_recipient_id(item),
            reason=f"Handoff routed to {item.get('recommended_action')}.",
            severity="high" if item.get("gate_decision") != "pass" else "medium",
            source="boundary_gate",
            network_scope="handoff",
        )

    for risk in propagated_risk.get("risks", []) if isinstance(propagated_risk.get("risks"), list) else []:
        if not isinstance(risk, dict):
            continue
        target_handoff_id = risk.get("handoff_id")
        target = result_by_id.get(str(target_handoff_id), {})
        _add_action(
            actions,
            action=_risk_action(risk),
            target_handoff_id=str(target_handoff_id) if target_handoff_id is not None else None,
            requested_by_handoff_id=str(target_handoff_id) if target_handoff_id is not None else None,
            target_agent_id=_sender_id(target) or risk.get("sender_id"),
            requested_by_agent_id=_recipient_id(target) or risk.get("recipient_id"),
            reason=risk.get("description") or f"Propagated risk: {risk.get('kind')}.",
            severity=risk.get("severity", "medium"),
            source=risk.get("kind"),
            network_scope="upstream" if risk.get("kind") in {"unsupported_claim", "accepted_violation"} else "handoff",
        )

    for link in propagated_risk.get("propagation_links", []) if isinstance(propagated_risk.get("propagation_links"), list) else []:
        if not isinstance(link, dict):
            continue
        source_handoff_id = str(link.get("source_handoff_id"))
        downstream_handoff_id = str(link.get("downstream_handoff_id"))
        source_item = result_by_id.get(source_handoff_id, {})
        downstream_item = result_by_id.get(downstream_handoff_id, {})
        _add_action(
            actions,
            action="revise_upstream_output",
            target_handoff_id=source_handoff_id,
            requested_by_handoff_id=downstream_handoff_id,
            target_agent_id=_sender_id(source_item),
            requested_by_agent_id=_recipient_id(downstream_item),
            reason=link.get("premise") or "Downstream handoff adopted an uncertain upstream output as a premise.",
            severity=link.get("severity", "high"),
            source=link.get("kind"),
            network_scope="upstream",
        )

    if not connectivity_risk.get("capacity_sufficient", True):
        _add_action(
            actions,
            action="defer_human_review",
            target_handoff_id=None,
            requested_by_handoff_id=None,
            reason="Workflow correction capacity is below global demand.",
            severity="high",
            source="connectivity_risk",
            network_scope="workflow",
        )

    action_counts: dict[str, int] = {}
    highest_severity = "info"
    for action in actions:
        action_counts[action["action"]] = action_counts.get(action["action"], 0) + 1
        if _severity_rank(action.get("severity")) > _severity_rank(highest_severity):
            highest_severity = action.get("severity", "unknown")

    return {
        "shared_correction_policy_version": SHARED_CORRECTION_POLICY_VERSION,
        "allowed_triggers": list(CORRECTION_ACTIONS),
        "action_count": len(actions),
        "actions": actions,
        "summary": {
            "action_counts": action_counts,
            "highest_severity": highest_severity,
            "has_network_correction": bool(actions),
            "risk_tier": connectivity_risk.get("risk_tier"),
            "capacity_sufficient": connectivity_risk.get("capacity_sufficient"),
        },
    }


__all__ = ["CORRECTION_ACTIONS", "SHARED_CORRECTION_POLICY_VERSION", "shared_correction_policy"]
