"""Production MI readiness integration for high-risk release adapters."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from production_readiness import production_mi_readiness_gate
except ImportError:  # pragma: no cover - package import path fallback
    from eval_pipeline.production_readiness import production_mi_readiness_gate


RELEASE_ADAPTER_INTEGRATION_VERSION = "0.1"
DEPLOYMENT_RELEASE_ADAPTERS = {"deployment_readiness"}
DEPLOYMENT_RELEASE_ACCEPT_THRESHOLD = 0.93


def _adapter_id_from_result(result: dict[str, Any]) -> str | None:
    adapter = result.get("adapter")
    if isinstance(adapter, str):
        return adapter
    if isinstance(adapter, dict):
        name = adapter.get("id") or adapter.get("name")
        if isinstance(name, str):
            if name.endswith("_aana_adapter"):
                name = name[: -len("_aana_adapter")]
            return name
    raw_result = result.get("raw_result")
    if isinstance(raw_result, dict):
        return _adapter_id_from_result(raw_result)
    return None


def _adapter_id(workflow_request: dict[str, Any] | None, result: dict[str, Any]) -> str | None:
    if isinstance(workflow_request, dict) and isinstance(workflow_request.get("adapter"), str):
        return workflow_request["adapter"]
    return _adapter_id_from_result(result)


def is_deployment_release_adapter(adapter_id: str | None) -> bool:
    return adapter_id in DEPLOYMENT_RELEASE_ADAPTERS


def _evidence(workflow_request: dict[str, Any] | None) -> list[Any]:
    if not isinstance(workflow_request, dict):
        return []
    evidence = workflow_request.get("evidence")
    return deepcopy(evidence) if isinstance(evidence, list) else []


def _workflow_id(workflow_request: dict[str, Any] | None, result: dict[str, Any]) -> str:
    if isinstance(workflow_request, dict) and workflow_request.get("workflow_id"):
        return str(workflow_request["workflow_id"])
    if result.get("workflow_id"):
        return str(result["workflow_id"])
    return "deployment-release-workflow"


def _selected_action_aix(result: dict[str, Any]) -> dict[str, Any]:
    candidate_aix = result.get("candidate_aix")
    if isinstance(candidate_aix, dict):
        return deepcopy(candidate_aix)
    aix = result.get("aix")
    return deepcopy(aix) if isinstance(aix, dict) else {}


def _selected_violations(result: dict[str, Any]) -> list[dict[str, Any]]:
    violations = result.get("violations")
    if isinstance(violations, list) and violations:
        return deepcopy([item for item in violations if isinstance(item, dict)])
    raw_result = result.get("raw_result")
    if isinstance(raw_result, dict):
        candidate_report = raw_result.get("candidate_tool_report")
        if isinstance(candidate_report, dict) and isinstance(candidate_report.get("violations"), list):
            return deepcopy([item for item in candidate_report["violations"] if isinstance(item, dict)])
        tool_report = raw_result.get("tool_report")
        if isinstance(tool_report, dict) and isinstance(tool_report.get("violations"), list):
            return deepcopy([item for item in tool_report["violations"] if isinstance(item, dict)])
    candidate_report = result.get("candidate_tool_report")
    if isinstance(candidate_report, dict) and isinstance(candidate_report.get("violations"), list):
        return deepcopy([item for item in candidate_report["violations"] if isinstance(item, dict)])
    tool_report = result.get("tool_report")
    if isinstance(tool_report, dict) and isinstance(tool_report.get("violations"), list):
        return deepcopy([item for item in tool_report["violations"] if isinstance(item, dict)])
    return []


def _thresholds(action_aix: dict[str, Any]) -> dict[str, float]:
    thresholds = action_aix.get("thresholds") if isinstance(action_aix.get("thresholds"), dict) else {}
    return {
        "accept": max(float(thresholds.get("accept", 0.85)), DEPLOYMENT_RELEASE_ACCEPT_THRESHOLD),
        "revise": float(thresholds.get("revise", 0.65)),
        "defer": float(thresholds.get("defer", 0.5)),
    }


def deployment_release_mi_batch(
    workflow_request: dict[str, Any] | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Build the MI readiness batch for a deployment/release adapter result."""

    result = result if isinstance(result, dict) else {}
    workflow_id = _workflow_id(workflow_request, result)
    adapter_id = _adapter_id(workflow_request, result) or "deployment_readiness"
    action_aix = _selected_action_aix(result)
    thresholds = _thresholds(action_aix)
    hard_blockers = sorted({str(item) for item in action_aix.get("hard_blockers", []) if item})
    score = action_aix.get("score")
    if not isinstance(score, (int, float)):
        score = 0.0
    evidence = _evidence(workflow_request)
    violations = _selected_violations(result)

    recommended_action = "accept"
    if hard_blockers:
        recommended_action = "refuse"
    elif float(score) < thresholds["accept"]:
        recommended_action = "defer"

    handoff_result = {
        "handoff_id": f"{workflow_id}:deployment-release-pre-execution",
        "sender": {"id": "release_agent", "type": "agent", "trust_tier": "system"},
        "recipient": {"id": adapter_id, "type": "adapter", "trust_tier": "system"},
        "boundary_type": "agent_to_tool",
        "boundary_supported": True,
        "gate_decision": "pass" if recommended_action == "accept" else "block",
        "recommended_action": recommended_action,
        "candidate_gate": result.get("candidate_gate"),
        "evidence_summary": evidence,
        "violations": violations,
        "aix": {**action_aix, "thresholds": thresholds, "hard_blockers": hard_blockers},
        "handoff_aix": {**action_aix, "thresholds": thresholds, "hard_blockers": hard_blockers},
    }

    global_aix = {
        "workflow_aix_version": "0.1",
        "workflow_id": workflow_id,
        "score": round(float(score), 4),
        "components": action_aix.get("components", {}),
        "handoff_count": 1,
        "local_all_pass": recommended_action == "accept",
        "drift_detected": False,
        "score_drift": {
            "first_score": round(float(score), 4),
            "last_score": round(float(score), 4),
            "delta": 0.0,
            "max_drop": 0.0,
            "trend": "flat",
        },
        "risk_tier": "high",
        "thresholds": thresholds,
        "decision": action_aix.get("decision") or recommended_action,
        "recommended_action": recommended_action,
        "hard_blockers": hard_blockers,
        "handoff_scores": [
            {
                "handoff_id": handoff_result["handoff_id"],
                "score": round(float(score), 4),
                "decision": action_aix.get("decision"),
                "gate_decision": handoff_result["gate_decision"],
                "recommended_action": recommended_action,
            }
        ],
        "notes": [
            "Deployment/release direct execution is gated by production MI readiness.",
        ],
    }

    return {
        "results": [handoff_result],
        "workflow_aix": global_aix,
        "global_aix": global_aix,
        "propagated_risk": {
            "propagated_risk_version": "0.1",
            "handoff_count": 1,
            "risk_count": 0,
            "propagation_count": 0,
            "risk_counts": {},
            "severity_score": 0,
            "risks": [],
            "propagation_links": [],
            "has_propagated_risk": False,
        },
        "summary": {
            "total": 1,
            "workflow_aix_score": round(float(score), 4),
            "workflow_aix_decision": global_aix["decision"],
            "risk_tier": "high",
        },
    }


def attach_deployment_release_readiness(
    workflow_request: dict[str, Any] | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Attach production MI readiness to deployment/release adapter results."""

    if not isinstance(result, dict):
        return result
    adapter_id = _adapter_id(workflow_request, result)
    if not is_deployment_release_adapter(adapter_id):
        return result

    updated = dict(result)
    mi_batch = deployment_release_mi_batch(workflow_request, updated)
    readiness = production_mi_readiness_gate({"mi_batch": mi_batch}, high_risk_action=True)
    updated["release_adapter_integration_version"] = RELEASE_ADAPTER_INTEGRATION_VERSION
    updated["production_mi_batch"] = mi_batch
    updated["production_mi_readiness"] = readiness
    updated["direct_execution_allowed"] = bool(readiness.get("can_execute_directly"))
    updated["direct_execution_blockers"] = list(readiness.get("blockers", []))
    return updated


__all__ = [
    "DEPLOYMENT_RELEASE_ADAPTERS",
    "RELEASE_ADAPTER_INTEGRATION_VERSION",
    "attach_deployment_release_readiness",
    "deployment_release_mi_batch",
    "is_deployment_release_adapter",
]
