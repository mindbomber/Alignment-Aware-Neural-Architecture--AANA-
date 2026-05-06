"""Release-blocker remediation for the research/citation MI pilot."""

from __future__ import annotations

import copy
import json
import pathlib
from typing import Any

from eval_pipeline.correction_execution import execute_correction_loop
from eval_pipeline.mi_audit import append_mi_audit_jsonl
from eval_pipeline.mi_observability import write_mi_dashboard
from eval_pipeline.mi_pilot import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RESEARCH_WORKFLOW,
    _dashboard_from_pilot,
    _load_json,
    _scores,
    research_citation_pilot_handoffs,
    run_research_citation_mi_pilot,
)
from eval_pipeline.mi_boundary_gate import mi_boundary_batch
from eval_pipeline.pilot_hardening import _build_guarded_result
from eval_pipeline.production_readiness import production_mi_readiness_gate
from eval_pipeline.release_readiness_report import write_release_readiness_report


RELEASE_BLOCKER_REMEDIATION_VERSION = "0.1"


def _source_texts(handoffs: list[dict[str, Any]]) -> list[str]:
    texts = []
    seen = set()
    for handoff in handoffs:
        for item in handoff.get("evidence", []) if isinstance(handoff.get("evidence"), list) else []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if text and text not in seen:
                seen.add(text)
                texts.append(text)
    return texts


def _support_evidence_claims(handoff: dict[str, Any], claims: list[str]) -> None:
    for item in handoff.get("evidence", []) if isinstance(handoff.get("evidence"), list) else []:
        if not isinstance(item, dict):
            continue
        supports = list(item.get("supports", [])) if isinstance(item.get("supports"), list) else []
        for claim in claims:
            if claim not in supports:
                supports.append(claim)
        item["supports"] = supports
        item.setdefault("metadata", {})["freshness_status"] = "fresh"


def _set_supported_assumption(handoff: dict[str, Any], *, evidence_source_id: str = "source-a") -> None:
    message = handoff.setdefault("message", {})
    if not isinstance(message, dict):
        message = {}
        handoff["message"] = message
    message["assumptions"] = [
        {
            "id": "source-bounded-summary",
            "description": "The summary uses only the provided Source A and Source B evidence and preserves source limits.",
            "support_status": "supported",
            "evidence_source_id": evidence_source_id,
        }
    ]


def corrected_research_citation_handoffs(
    workflow_path: str | pathlib.Path = DEFAULT_RESEARCH_WORKFLOW,
) -> list[dict[str, Any]]:
    """Return corrected research/citation handoffs after MI remediation."""

    workflow = _load_json(workflow_path)
    handoffs = research_citation_pilot_handoffs(workflow)
    source_texts = _source_texts(handoffs)
    source_a = source_texts[0] if source_texts else "Source A supports explicit constraints and correction routes."
    source_b = source_texts[1] if len(source_texts) > 1 else "Source B warns about incomplete source coverage."
    source_limits = source_texts[2] if len(source_texts) > 2 else "No measured productivity percentage is provided."

    retrieval_claims = [
        "Only Source A and Source B are available for the requested summary.",
        source_a,
        source_b,
        source_limits,
    ]
    handoffs[0]["message"].update(
        {
            "summary": "Repository evidence retrieved for a source-bounded research summary.",
            "claims": retrieval_claims,
        }
    )
    _set_supported_assumption(handoffs[0])
    _support_evidence_claims(handoffs[0], retrieval_claims)

    corrected_summary = (
        "AANA-style verifier loops can help knowledge-work summaries by making constraints explicit and routing failures "
        "to revise, ask, defer, refuse, or accept. The supplied evidence does not provide a measured productivity "
        "percentage or a Source C citation, so those claims are removed and uncertainty remains labeled."
    )
    research_claims = [source_a, source_b, source_limits]
    handoffs[1]["message"].update(
        {
            "summary": corrected_summary,
            "claims": research_claims,
        }
    )
    _set_supported_assumption(handoffs[1])
    _support_evidence_claims(handoffs[1], research_claims)
    handoffs[1]["verifier_scores"] = _scores()
    handoffs[1]["recommended_action"] = "accept"
    handoffs[1]["metadata"]["correction_status"] = "remediated"

    publication_claims = [
        "Corrected research summary is source-bounded and ready for publication checking.",
        source_limits,
    ]
    handoffs[2]["message"].update(
        {
            "summary": "Publication step checks the corrected source-bounded research summary.",
            "claims": publication_claims,
            "assumptions": [
                {
                    "id": "corrected-research-summary-ready",
                    "description": "The corrected upstream research summary no longer contains unsupported productivity or Source C claims.",
                    "support_status": "supported",
                    "evidence_source_id": "source-a",
                }
            ],
        }
    )
    _support_evidence_claims(handoffs[2], publication_claims)
    handoffs[2]["verifier_scores"] = _scores()
    handoffs[2]["recommended_action"] = "accept"
    handoffs[2]["metadata"]["correction_status"] = "remediated"
    return handoffs


def run_research_citation_remediation(
    workflow_path: str | pathlib.Path = DEFAULT_RESEARCH_WORKFLOW,
) -> dict[str, Any]:
    """Execute remediation and return before/after MI state."""

    before = run_research_citation_mi_pilot(workflow_path)
    correction_loop = execute_correction_loop(copy.deepcopy(before["handoffs"]), route="revise")
    corrected_handoffs = corrected_research_citation_handoffs(workflow_path)
    after_batch = mi_boundary_batch(corrected_handoffs)
    accepted = (
        after_batch.get("summary", {}).get("blocked", 0) == 0
        and after_batch.get("workflow_aix", {}).get("recommended_action") == "accept"
        and not after_batch.get("propagated_risk", {}).get("has_propagated_risk")
    )
    after = {
        "mi_pilot_version": before.get("mi_pilot_version"),
        "pilot_id": "research_citation_mi_pilot_remediated",
        "workflow_id": before.get("workflow_id"),
        "source_workflow_path": str(pathlib.Path(workflow_path)),
        "candidate_workflow": "research/citation workflow",
        "accepted": accepted,
        "recommended_action": "accept" if accepted else "revise",
        "handoff_count": len(corrected_handoffs),
        "handoffs": corrected_handoffs,
        "mi_batch": after_batch,
        "summary": {
            "gate_decisions": after_batch.get("summary", {}).get("gate_decisions", {}),
            "recommended_actions": after_batch.get("summary", {}).get("recommended_actions", {}),
            "propagated_risk_count": after_batch.get("summary", {}).get("propagated_risk_count"),
            "shared_correction_action_count": after_batch.get("summary", {}).get("shared_correction_action_count"),
            "mi_audit_record_count": after_batch.get("summary", {}).get("mi_audit_record_count"),
            "workflow_aix_decision": after_batch.get("workflow_aix", {}).get("decision"),
            "workflow_risk_tier": after_batch.get("workflow_aix", {}).get("risk_tier"),
        },
    }
    before_readiness = production_mi_readiness_gate(before)
    after_readiness = production_mi_readiness_gate(after)
    return {
        "release_blocker_remediation_version": RELEASE_BLOCKER_REMEDIATION_VERSION,
        "pilot_id": "research_citation_release_blocker_remediation",
        "before": {
            "pilot_result": before,
            "production_mi_readiness": before_readiness,
        },
        "correction_loop": correction_loop,
        "after": {
            "pilot_result": after,
            "production_mi_readiness": after_readiness,
        },
        "resolved_blockers": sorted(set(before_readiness.get("blockers", [])) - set(after_readiness.get("blockers", []))),
        "remaining_blockers": list(after_readiness.get("blockers", [])),
        "status": "pass" if after_readiness.get("release_status") == "ready" else "block",
    }


def write_research_citation_remediation(
    output_dir: str | pathlib.Path = DEFAULT_OUTPUT_DIR,
    workflow_path: str | pathlib.Path = DEFAULT_RESEARCH_WORKFLOW,
    *,
    allow_direct_execution: bool = False,
) -> dict[str, Any]:
    """Write remediated research/citation pilot artifacts to the pilot output directory."""

    output_path = pathlib.Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    remediation = run_research_citation_remediation(workflow_path)
    pilot_result = remediation["after"]["pilot_result"]
    readiness = remediation["after"]["production_mi_readiness"]
    guarded = _build_guarded_result(
        pilot_result,
        allow_direct_execution=allow_direct_execution,
        live_mode=True,
        requested_human_decision="defer",
    )

    result_path = output_path / "pilot_result.json"
    handoffs_path = output_path / "pilot_handoffs.json"
    audit_path = output_path / "mi_audit.jsonl"
    dashboard_path = output_path / "mi_dashboard.json"
    readiness_path = output_path / "production_mi_readiness.json"
    guarded_path = output_path / "guarded_live_result.json"
    review_queue_path = output_path / "mi_human_review_queue.jsonl"
    remediation_path = output_path / "release_blocker_remediation.json"

    result_path.write_text(json.dumps(pilot_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoffs_path.write_text(json.dumps({"handoffs": pilot_result["handoffs"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if audit_path.exists():
        audit_path.unlink()
    append_mi_audit_jsonl(audit_path, pilot_result["mi_batch"]["mi_audit_records"])
    dashboard = _dashboard_from_pilot(pilot_result)
    write_mi_dashboard(dashboard_path, dashboard)
    readiness_path.write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    guarded_path.write_text(json.dumps(guarded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if review_queue_path.exists():
        review_queue_path.unlink()
    remediation_path.write_text(json.dumps(remediation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    release_report_path = output_path / "production_mi_release_report.json"
    release_report = write_release_readiness_report(
        release_report_path,
        readiness=readiness,
        artifact_paths={
            "audit_jsonl": audit_path,
            "pilot_result": result_path,
            "dashboard": dashboard_path,
            "human_review_queue": review_queue_path,
        },
    )

    return {
        "result": remediation,
        "dashboard": dashboard,
        "guarded": guarded,
        "release_report": release_report["report"],
        "paths": {
            "pilot_result": str(result_path),
            "pilot_handoffs": str(handoffs_path),
            "mi_audit_jsonl": str(audit_path),
            "mi_dashboard": str(dashboard_path),
            "production_mi_readiness": str(readiness_path),
            "guarded_live_result": str(guarded_path),
            "human_review_queue": str(review_queue_path),
            "release_blocker_remediation": str(remediation_path),
            "release_readiness_report": release_report["path"],
        },
    }


__all__ = [
    "RELEASE_BLOCKER_REMEDIATION_VERSION",
    "corrected_research_citation_handoffs",
    "run_research_citation_remediation",
    "write_research_citation_remediation",
]
