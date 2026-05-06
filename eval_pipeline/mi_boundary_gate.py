"""Mechanistic interoperability boundary gate.

The boundary gate is the reusable entry point for communication edges:

- agent-to-agent
- agent-to-tool
- tool-to-agent
- plugin-to-agent
- workflow-step-to-workflow-step

It validates the communication boundary, then delegates recipient-relative
constraint coherence to `handoff_gate`.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from eval_pipeline import aix
from eval_pipeline.agent_contract import ALLOWED_ACTIONS
from eval_pipeline.handoff_aix import calculate_handoff_aix
from eval_pipeline.handoff_gate import HANDOFF_CONTRACT_VERSION, handoff_gate
from eval_pipeline.mi_audit import mi_audit_records
from eval_pipeline.mi_contract_registry import supported_boundaries, validate_mi_contract_compatibility
from eval_pipeline.propagated_risk import track_propagated_risk
from eval_pipeline.shared_correction import shared_correction_policy
from eval_pipeline.workflow_aix import calculate_workflow_aix


MI_BOUNDARY_GATE_VERSION = "0.1"
SUPPORTED_BOUNDARIES = supported_boundaries()
DEFAULT_BOUNDARY_ALLOWED_ACTIONS = ["accept", "revise", "retrieve", "ask", "defer", "refuse"]


def _allowed_actions(handoff: dict[str, Any]) -> list[str]:
    actions = handoff.get("allowed_actions")
    if not isinstance(actions, list) or not actions:
        return list(DEFAULT_BOUNDARY_ALLOWED_ACTIONS)
    normalized = [action for action in actions if action in ALLOWED_ACTIONS]
    return normalized or list(DEFAULT_BOUNDARY_ALLOWED_ACTIONS)


def _select_action(allowed_actions: list[str], preferred: list[str]) -> str:
    for action in preferred:
        if action in allowed_actions:
            return action
    return allowed_actions[0] if allowed_actions else "defer"


def _endpoint_type(handoff: dict[str, Any], key: str) -> str | None:
    endpoint = handoff.get(key)
    if not isinstance(endpoint, dict):
        return None
    value = endpoint.get("type")
    return value if isinstance(value, str) and value.strip() else None


def infer_boundary_type(handoff: dict[str, Any]) -> str | None:
    """Infer a supported MI boundary type from sender and recipient endpoint types."""

    sender_type = _endpoint_type(handoff, "sender")
    recipient_type = _endpoint_type(handoff, "recipient")
    if not sender_type or not recipient_type:
        return None

    for boundary_type, (sender_types, recipient_types) in SUPPORTED_BOUNDARIES.items():
        if sender_type in sender_types and recipient_type in recipient_types:
            return boundary_type
    return None


def _metadata_boundary_type(handoff: dict[str, Any]) -> str | None:
    metadata = handoff.get("metadata")
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("boundary_type")
    return value if isinstance(value, str) and value.strip() else None


def _boundary_violation(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "id": code,
        "layer": "MI",
        "severity": "high",
        "message": message,
        "hard": True,
    }


def _validate_boundary(handoff: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]], dict[str, Any]]:
    report = validate_mi_contract_compatibility(handoff)
    return report.get("boundary_type"), report.get("violations", []), report


def _apply_boundary_failure(
    result: dict[str, Any],
    *,
    handoff: dict[str, Any],
    boundary_type: str | None,
    boundary_violations: list[dict[str, Any]],
    compatibility_report: dict[str, Any],
) -> dict[str, Any]:
    allowed_actions = _allowed_actions(handoff)
    recommended_action = _select_action(allowed_actions, ["defer", "ask", "refuse", "revise"])
    violations = list(result.get("violations", [])) + boundary_violations
    hard_blockers = sorted(
        set(result.get("aix", {}).get("hard_blockers", []))
        | {violation["code"] for violation in boundary_violations}
    )

    aix_score = aix.calculate_aix(
        adapter={"aix": handoff.get("metadata", {}).get("aix", {})} if isinstance(handoff.get("metadata"), dict) else {},
        constraint_results=result.get("constraint_results", []),
        tool_report={"violations": violations},
        gate_decision="fail",
        recommended_action=recommended_action,
    )

    updated = dict(result)
    updated["mi_boundary_gate_version"] = MI_BOUNDARY_GATE_VERSION
    updated["boundary_type"] = boundary_type
    updated["boundary_supported"] = False
    updated["mi_contract_compatibility"] = compatibility_report
    updated["gate_decision"] = "fail"
    updated["candidate_gate"] = "block"
    updated["recommended_action"] = recommended_action
    updated["violations"] = violations
    updated["aix"] = {**aix_score, "hard_blockers": hard_blockers}
    updated["handoff_aix"] = {
        **calculate_handoff_aix(
            handoff,
            constraint_results=result.get("constraint_results", []),
            violations=violations,
            gate_decision="fail",
            recommended_action=recommended_action,
        ),
        "hard_blockers": hard_blockers,
    }

    audit_summary = dict(updated.get("audit_summary", {}))
    audit_summary.update(
        {
            "boundary_type": boundary_type,
            "boundary_supported": False,
            "mi_contract_registry_version": compatibility_report.get("mi_contract_registry_version"),
            "contract_version_compatible": compatibility_report.get("version_compatible"),
            "gate_decision": "fail",
            "recommended_action": recommended_action,
            "aix_score": aix_score.get("score"),
            "aix_decision": aix_score.get("decision"),
            "handoff_aix_score": updated["handoff_aix"].get("score"),
            "handoff_aix_decision": updated["handoff_aix"].get("decision"),
            "hard_blockers": hard_blockers,
            "violation_codes": [violation.get("code") for violation in violations],
        }
    )
    updated["audit_summary"] = audit_summary
    return updated


def _apply_boundary_success(result: dict[str, Any], *, boundary_type: str, compatibility_report: dict[str, Any]) -> dict[str, Any]:
    updated = dict(result)
    updated["mi_boundary_gate_version"] = MI_BOUNDARY_GATE_VERSION
    updated["boundary_type"] = boundary_type
    updated["boundary_supported"] = True
    updated["mi_contract_compatibility"] = compatibility_report

    audit_summary = dict(updated.get("audit_summary", {}))
    audit_summary.update(
        {
            "boundary_type": boundary_type,
            "boundary_supported": True,
            "mi_contract_registry_version": compatibility_report.get("mi_contract_registry_version"),
            "contract_version_compatible": compatibility_report.get("version_compatible"),
        }
    )
    updated["audit_summary"] = audit_summary
    return updated


def mi_boundary_gate(handoff: dict[str, Any]) -> dict[str, Any]:
    """Run the reusable MI boundary gate for one communication handoff."""

    payload = deepcopy(handoff) if isinstance(handoff, dict) else handoff
    boundary_type, boundary_violations, compatibility_report = _validate_boundary(payload if isinstance(payload, dict) else {})
    result = handoff_gate(payload)

    if boundary_violations:
        return _apply_boundary_failure(
            result,
            handoff=payload if isinstance(payload, dict) else {},
            boundary_type=boundary_type,
            boundary_violations=boundary_violations,
            compatibility_report=compatibility_report,
        )

    return _apply_boundary_success(result, boundary_type=boundary_type or "unknown", compatibility_report=compatibility_report)


def mi_boundary_batch(handoffs: list[dict[str, Any]]) -> dict[str, Any]:
    """Run `mi_boundary_gate` over a list of handoffs and summarize routes."""

    results = [mi_boundary_gate(handoff) for handoff in handoffs]
    route_counts = {}
    gate_counts = {}
    boundary_counts = {}
    for result in results:
        route_counts[result.get("recommended_action")] = route_counts.get(result.get("recommended_action"), 0) + 1
        gate_counts[result.get("gate_decision")] = gate_counts.get(result.get("gate_decision"), 0) + 1
        boundary_counts[result.get("boundary_type")] = boundary_counts.get(result.get("boundary_type"), 0) + 1
    workflow_id = None
    if handoffs and isinstance(handoffs[0], dict):
        metadata = handoffs[0].get("metadata") if isinstance(handoffs[0].get("metadata"), dict) else {}
        workflow_id = handoffs[0].get("correlation_id") or metadata.get("workflow_id")
    workflow_aix = calculate_workflow_aix(results, workflow_id=workflow_id)
    propagated_risk = track_propagated_risk(results)
    shared_correction = shared_correction_policy(
        {
            "results": results,
            "workflow_aix": workflow_aix,
            "propagated_risk": propagated_risk,
        }
    )
    audit_records = mi_audit_records(results, workflow_id=workflow_id)

    return {
        "contract_version": HANDOFF_CONTRACT_VERSION,
        "mi_boundary_gate_version": MI_BOUNDARY_GATE_VERSION,
        "results": results,
        "workflow_aix": workflow_aix,
        "global_aix": workflow_aix,
        "propagated_risk": propagated_risk,
        "shared_correction": shared_correction,
        "mi_audit_records": audit_records,
        "summary": {
            "total": len(results),
            "gate_decisions": gate_counts,
            "recommended_actions": route_counts,
            "boundary_types": boundary_counts,
            "accepted": route_counts.get("accept", 0),
            "blocked": len([result for result in results if result.get("gate_decision") != "pass"]),
            "workflow_aix_score": workflow_aix.get("score"),
            "workflow_aix_decision": workflow_aix.get("decision"),
            "workflow_drift_detected": workflow_aix.get("drift_detected"),
            "risk_tier": workflow_aix.get("risk_tier"),
            "capacity_sufficient": workflow_aix.get("connectivity_risk", {}).get("capacity_sufficient")
            if isinstance(workflow_aix.get("connectivity_risk"), dict)
            else None,
            "propagated_risk_count": propagated_risk.get("risk_count"),
            "propagation_count": propagated_risk.get("propagation_count"),
            "has_propagated_risk": propagated_risk.get("has_propagated_risk"),
            "shared_correction_action_count": shared_correction.get("action_count"),
            "has_network_correction": shared_correction.get("summary", {}).get("has_network_correction")
            if isinstance(shared_correction.get("summary"), dict)
            else None,
            "mi_audit_record_count": len(audit_records),
        },
    }


__all__ = [
    "MI_BOUNDARY_GATE_VERSION",
    "SUPPORTED_BOUNDARIES",
    "infer_boundary_type",
    "mi_boundary_batch",
    "mi_boundary_gate",
]
