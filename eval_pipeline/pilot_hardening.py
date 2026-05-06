"""Guarded live-mode hardening for the research/citation MI pilot."""

from __future__ import annotations

import copy
import json
import pathlib
from typing import Any

from eval_pipeline.human_review_queue import (
    append_human_review_queue_jsonl,
    human_review_packet,
    validate_human_review_packets,
)
from eval_pipeline.mi_pilot import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RESEARCH_WORKFLOW,
    run_research_citation_mi_pilot,
    write_research_citation_mi_pilot,
)
from eval_pipeline.production_readiness import production_mi_readiness_gate


PILOT_HARDENING_VERSION = "0.1"
GUARDED_LIVE_PILOT_ID = "research_citation_guarded_live"


def guarded_pilot_execution_decision(
    readiness: dict[str, Any],
    *,
    allow_direct_execution: bool = False,
) -> dict[str, Any]:
    """Decide whether a guarded pilot may execute a direct external action."""

    readiness = readiness if isinstance(readiness, dict) else {}
    readiness_passed = bool(readiness.get("can_execute_directly") and readiness.get("release_status") == "ready")
    direct_execution_allowed = bool(allow_direct_execution and readiness_passed)
    if direct_execution_allowed:
        execution_state = "ready_for_direct_execution"
    elif readiness_passed:
        execution_state = "readiness_passed_direct_execution_not_requested"
    else:
        execution_state = "blocked_not_executed"
    return {
        "readiness_passed": readiness_passed,
        "direct_execution_requested": bool(allow_direct_execution),
        "direct_execution_allowed": direct_execution_allowed,
        "execution_state": execution_state,
        "recommended_action": readiness.get("recommended_action") or "defer",
    }


def guarded_pilot_rollback_plan(
    readiness: dict[str, Any],
    execution_decision: dict[str, Any],
) -> dict[str, Any]:
    """Return rollback/defer behavior for a guarded live pilot run."""

    blocked = execution_decision.get("execution_state") == "blocked_not_executed"
    return {
        "rollback_required": bool(blocked),
        "external_action_taken": False,
        "rollback_action": "no_external_action_taken" if blocked else "none",
        "defer_to_human_review": bool(blocked),
        "blocked_execution_state": execution_decision.get("execution_state"),
        "blockers": list(readiness.get("blockers", [])) if isinstance(readiness.get("blockers"), list) else [],
        "recommended_action": readiness.get("recommended_action") or execution_decision.get("recommended_action"),
    }


def _readiness_review_result(
    pilot_result: dict[str, Any],
    readiness: dict[str, Any],
    rollback: dict[str, Any],
) -> dict[str, Any]:
    batch = pilot_result.get("mi_batch") if isinstance(pilot_result.get("mi_batch"), dict) else {}
    workflow_aix = batch.get("workflow_aix") if isinstance(batch.get("workflow_aix"), dict) else {}
    return {
        "workflow_id": pilot_result.get("workflow_id"),
        "handoff_id": f"{pilot_result.get('workflow_id') or 'research-citation'}:guarded-live-readiness",
        "sender": {"id": "pilot_hardening_guard", "type": "guard", "trust_tier": "system"},
        "recipient": {"id": "human_review_queue", "type": "queue", "trust_tier": "system"},
        "gate_decision": "block",
        "recommended_action": "defer",
        "blockers": list(readiness.get("blockers", [])) if isinstance(readiness.get("blockers"), list) else [],
        "hard_blockers": list(readiness.get("hard_blockers", [])) if isinstance(readiness.get("hard_blockers"), list) else [],
        "global_aix": copy.deepcopy(workflow_aix),
        "workflow_aix": copy.deepcopy(workflow_aix),
        "propagated_risk": copy.deepcopy(batch.get("propagated_risk") if isinstance(batch.get("propagated_risk"), dict) else {}),
        "production_mi_readiness": copy.deepcopy(readiness),
        "rollback": copy.deepcopy(rollback),
        "audit_summary": {
            "workflow_id": pilot_result.get("workflow_id"),
            "handoff_id": f"{pilot_result.get('workflow_id') or 'research-citation'}:guarded-live-readiness",
        },
    }


def _build_guarded_result(
    pilot_result: dict[str, Any],
    *,
    allow_direct_execution: bool,
    live_mode: bool,
    requested_human_decision: str,
) -> dict[str, Any]:
    readiness = production_mi_readiness_gate(pilot_result, high_risk_action=True)
    execution_decision = guarded_pilot_execution_decision(
        readiness,
        allow_direct_execution=allow_direct_execution,
    )
    rollback = guarded_pilot_rollback_plan(readiness, execution_decision)
    review_packets = []
    if rollback["defer_to_human_review"]:
        review_packets = [
            human_review_packet(
                _readiness_review_result(pilot_result, readiness, rollback),
                workflow_id=pilot_result.get("workflow_id"),
                requested_human_decision=requested_human_decision,
                reason="Guarded live pilot was blocked by production MI readiness.",
            )
        ]
    validation = validate_human_review_packets(review_packets)
    return {
        "pilot_hardening_version": PILOT_HARDENING_VERSION,
        "pilot_id": GUARDED_LIVE_PILOT_ID,
        "source_pilot_id": pilot_result.get("pilot_id"),
        "pilot_mode": "guarded_live" if live_mode else "guarded_fixture",
        "direct_execution": execution_decision,
        "production_mi_readiness": readiness,
        "rollback": rollback,
        "human_review_queue": {
            "packet_count": len(review_packets),
            "validation": validation,
            "packets": review_packets,
        },
        "pilot_result": pilot_result,
    }


def run_guarded_research_citation_pilot(
    workflow_path: str | pathlib.Path = DEFAULT_RESEARCH_WORKFLOW,
    *,
    allow_direct_execution: bool = False,
    live_mode: bool = True,
    requested_human_decision: str = "defer",
) -> dict[str, Any]:
    """Run the research/citation pilot in guarded live mode.

    The wrapper performs no external action. Direct execution is allowed only
    when production MI readiness passes and the caller explicitly enables it.
    """

    pilot_result = run_research_citation_mi_pilot(workflow_path)
    return _build_guarded_result(
        pilot_result,
        allow_direct_execution=allow_direct_execution,
        live_mode=live_mode,
        requested_human_decision=requested_human_decision,
    )


def write_guarded_research_citation_pilot(
    output_dir: str | pathlib.Path = DEFAULT_OUTPUT_DIR,
    workflow_path: str | pathlib.Path = DEFAULT_RESEARCH_WORKFLOW,
    *,
    allow_direct_execution: bool = False,
    live_mode: bool = True,
    requested_human_decision: str = "defer",
) -> dict[str, Any]:
    """Write guarded live-mode pilot artifacts."""

    output_path = pathlib.Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    base_payload = write_research_citation_mi_pilot(output_path, workflow_path)
    guarded = _build_guarded_result(
        base_payload["result"],
        allow_direct_execution=allow_direct_execution,
        live_mode=live_mode,
        requested_human_decision=requested_human_decision,
    )
    guarded_path = output_path / "guarded_live_result.json"
    readiness_path = output_path / "production_mi_readiness.json"
    review_queue_path = output_path / "mi_human_review_queue.jsonl"
    guarded_path.write_text(json.dumps(guarded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readiness_path.write_text(
        json.dumps(guarded["production_mi_readiness"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if review_queue_path.exists():
        review_queue_path.unlink()
    packets = guarded["human_review_queue"]["packets"]
    if packets:
        append_human_review_queue_jsonl(review_queue_path, packets)
    paths = dict(base_payload["paths"])
    paths.update(
        {
            "guarded_live_result": str(guarded_path),
            "production_mi_readiness": str(readiness_path),
            "human_review_queue": str(review_queue_path),
        }
    )
    return {
        "result": guarded,
        "paths": paths,
    }


__all__ = [
    "GUARDED_LIVE_PILOT_ID",
    "PILOT_HARDENING_VERSION",
    "guarded_pilot_execution_decision",
    "guarded_pilot_rollback_plan",
    "run_guarded_research_citation_pilot",
    "write_guarded_research_citation_pilot",
]
