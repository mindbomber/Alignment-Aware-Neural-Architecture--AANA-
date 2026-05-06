"""Shared adapter-runner result assembly helpers."""

try:
    from aix import attach_aix
    import aix as aix_module
except ModuleNotFoundError:  # pragma: no cover - used by script-path imports.
    from eval_pipeline.aix import attach_aix
    from eval_pipeline import aix as aix_module

from .registry import adapter_summary

try:
    from release_adapter_integration import attach_deployment_release_readiness
except ImportError:  # pragma: no cover - package import path fallback
    from eval_pipeline.release_adapter_integration import attach_deployment_release_readiness


def unsupported_result(adapter, prompt, candidate):
    return {
        "adapter": adapter_summary(adapter),
        "prompt": prompt,
        "candidate_answer": candidate,
        "final_answer": candidate,
        "recommended_action": "defer",
        "gate_decision": "needs_adapter_implementation",
        "constraint_results": [
            {
                "id": c.get("id", ""),
                "layer": c.get("layer"),
                "hard": bool(c.get("hard")),
                "status": "unknown",
                "description": c.get("description", ""),
                "violations": [],
            }
            for c in adapter.get("constraints", [])
        ],
        "tool_report": None,
        "caveats": [
            "This adapter contract loaded successfully, but no deterministic runner is implemented for its domain yet."
        ],
    }


def attach_runtime_aix(adapter, result, constraint_results_func):
    candidate_constraints = None
    candidate_report = result.get("candidate_tool_report") if isinstance(result, dict) else None
    if isinstance(candidate_report, dict):
        candidate_constraints = constraint_results_func(adapter, candidate_report)
    assembled = attach_aix(
        result,
        adapter=adapter,
        candidate_constraint_results=candidate_constraints,
    )
    assembled["audit_summary"] = audit_safe_summary(assembled)
    return attach_deployment_release_readiness(None, assembled)


def violation_codes(violations):
    return [
        violation.get("code")
        for violation in violations or []
        if isinstance(violation, dict) and violation.get("code")
    ]


def report_violations(result):
    if not isinstance(result, dict):
        return []
    report = result.get("candidate_tool_report") or result.get("tool_report") or {}
    if not isinstance(report, dict):
        return []
    violations = report.get("violations", [])
    return violations if isinstance(violations, list) else []


def aix_summary(result, key="aix"):
    if not isinstance(result, dict):
        return None
    block = result.get(key)
    if not isinstance(block, dict):
        return None
    return {
        "score": block.get("score"),
        "decision": block.get("decision"),
        "components": block.get("components", {}),
        "beta": block.get("beta"),
        "thresholds": block.get("thresholds", {}),
        "hard_blockers": block.get("hard_blockers", []),
    }


def audit_safe_summary(result):
    result = result if isinstance(result, dict) else {}
    violations = result.get("violations")
    if not isinstance(violations, list):
        violations = report_violations(result)
    return {
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "aix": aix_summary(result),
        "candidate_aix": aix_summary(result, key="candidate_aix"),
        "violation_count": len(violations),
        "violation_codes": violation_codes(violations),
    }


def assemble_agent_check_result(event, adapter_id, entry, adapter_result, agent_event_version):
    violations = report_violations(adapter_result)
    result = {
        "agent_check_version": agent_event_version,
        "agent": event.get("agent", "unknown") if isinstance(event, dict) else "unknown",
        "adapter_id": adapter_id,
        "workflow": entry.get("title") if isinstance(entry, dict) else None,
        "event_id": event.get("event_id") if isinstance(event, dict) else None,
        "gate_decision": adapter_result.get("gate_decision"),
        "recommended_action": adapter_result.get("recommended_action"),
        "candidate_gate": adapter_result.get("candidate_gate"),
        "aix": adapter_result.get("aix"),
        "candidate_aix": adapter_result.get("candidate_aix"),
        "violations": violations,
        "safe_response": adapter_result.get("final_answer"),
        "adapter_result": adapter_result,
    }
    result["audit_summary"] = audit_safe_summary(result)
    return result


def assemble_workflow_result(
    workflow_request,
    agent_result,
    *,
    contract_version,
    recommended_action=None,
    violations=None,
    aix=None,
):
    result = {
        "contract_version": contract_version,
        "workflow_id": workflow_request.get("workflow_id") if isinstance(workflow_request, dict) else None,
        "adapter": agent_result.get("adapter_id"),
        "workflow": agent_result.get("workflow"),
        "gate_decision": agent_result.get("gate_decision"),
        "recommended_action": recommended_action if recommended_action is not None else agent_result.get("recommended_action"),
        "candidate_gate": agent_result.get("candidate_gate"),
        "aix": aix if aix is not None else agent_result.get("aix"),
        "candidate_aix": agent_result.get("candidate_aix"),
        "violations": violations if violations is not None else list(agent_result.get("violations", [])),
        "output": agent_result.get("safe_response"),
        "raw_result": agent_result,
    }
    result["audit_summary"] = audit_safe_summary(result)
    return attach_deployment_release_readiness(workflow_request if isinstance(workflow_request, dict) else None, result)


def assemble_workflow_failure_result(
    workflow_request,
    error,
    *,
    contract_version,
    recommended_action,
    action_violation=None,
    workflow_id=None,
):
    item = workflow_request if isinstance(workflow_request, dict) else {}
    violation = {
        "code": "workflow_item_error",
        "severity": "high",
        "message": str(error),
    }
    violations = [violation]
    hard_blockers = [violation["code"]]
    if action_violation:
        violations.append(action_violation)
        hard_blockers.append(action_violation["code"])
    result = {
        "contract_version": contract_version,
        "workflow_id": workflow_id or item.get("workflow_id"),
        "adapter": item.get("adapter"),
        "workflow": None,
        "gate_decision": "fail",
        "recommended_action": recommended_action,
        "candidate_gate": "block",
        "aix": {
            "aix_version": aix_module.AIX_VERSION,
            "score": 0.0,
            "components": {},
            "base_score": 0.0,
            "penalty": 1.0,
            "beta": 1.0,
            "thresholds": dict(aix_module.DEFAULT_THRESHOLDS),
            "decision": "refuse",
            "hard_blockers": sorted(set(hard_blockers)),
            "notes": ["Workflow batch item failed before adapter completion; direct accept is blocked."],
        },
        "candidate_aix": None,
        "violations": violations,
        "output": None,
        "raw_result": {
            "error": {
                "type": error.__class__.__name__,
                "message": str(error),
            }
        },
    }
    result["audit_summary"] = audit_safe_summary(result)
    return result


def workflow_batch_summary(results):
    gate_decisions = {}
    recommended_actions = {}
    for result in results:
        gate_decision = result.get("gate_decision")
        recommended_action = result.get("recommended_action")
        gate_decisions[gate_decision] = gate_decisions.get(gate_decision, 0) + 1
        recommended_actions[recommended_action] = recommended_actions.get(recommended_action, 0) + 1
    failed = sum(1 for result in results if result.get("gate_decision") != "pass")
    return {
        "total": len(results),
        "passed": len(results) - failed,
        "failed": failed,
        "gate_decisions": gate_decisions,
        "recommended_actions": recommended_actions,
    }


def assemble_workflow_batch_result(batch_request, results, *, contract_version):
    return {
        "contract_version": contract_version,
        "batch_id": batch_request.get("batch_id") if isinstance(batch_request, dict) else None,
        "summary": workflow_batch_summary(results),
        "results": results,
    }
