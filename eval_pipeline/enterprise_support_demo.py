"""Polished enterprise support demo flow for AANA AIx Audit."""

from __future__ import annotations

import copy
import datetime
import json
import pathlib
from typing import Any

from eval_pipeline import agent_api, aix_audit, enterprise_connector_readiness


ROOT = pathlib.Path(__file__).resolve().parents[1]
ENTERPRISE_SUPPORT_DEMO_VERSION = "0.1"
DEFAULT_OUTPUT_DIR = ROOT / "eval_outputs" / "demos" / "enterprise_support_flow"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
WORKFLOW_PATHS = (
    ROOT / "examples" / "workflow_crm_support_reply.json",
    ROOT / "examples" / "workflow_email_send_guardrail.json",
    ROOT / "examples" / "workflow_ticket_update_checker.json",
)


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: str | pathlib.Path) -> dict[str, Any]:
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _write_json(path: str | pathlib.Path, payload: dict[str, Any]) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: str | pathlib.Path, text: str) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def _demo_workflows() -> list[dict[str, Any]]:
    workflows = []
    stage_metadata = [
        {
            "demo_stage": "support_reply",
            "demo_label": "Customer support reply",
            "buyer_visible_action": "AI drafts a refund reply using CRM and support-policy evidence.",
        },
        {
            "demo_stage": "email_send",
            "demo_label": "Email send",
            "buyer_visible_action": "AI tries to send the reply to the wrong recipient with private attachments.",
            "allowed_actions": ["defer", "refuse"],
        },
        {
            "demo_stage": "ticket_update",
            "demo_label": "Ticket update",
            "buyer_visible_action": "AI tries to post a customer-visible ticket update with unsupported claims and private data.",
        },
    ]
    for index, (path, metadata) in enumerate(zip(WORKFLOW_PATHS, stage_metadata, strict=True), start=1):
        workflow = copy.deepcopy(_load_json(path))
        workflow["workflow_id"] = f"enterprise-support-demo-{index:02d}-{metadata['demo_stage']}"
        workflow["metadata"] = {
            **workflow.get("metadata", {}),
            "product_bundle": "enterprise_ops_pilot",
            "surface": "support_customer_communications",
            "demo_flow": "customer_support_email_ticket",
            "demo_stage": metadata["demo_stage"],
            "demo_label": metadata["demo_label"],
            "buyer_visible_action": metadata["buyer_visible_action"],
        }
        if "allowed_actions" in metadata:
            workflow["allowed_actions"] = metadata["allowed_actions"]
        workflows.append(workflow)
    return workflows


def build_enterprise_support_demo_batch() -> dict[str, Any]:
    return {
        "contract_version": "0.1",
        "batch_id": "enterprise-support-email-ticket-demo",
        "requests": _demo_workflows(),
        "metadata": {
            "product_bundle": "enterprise_ops_pilot",
            "demo_flow": "customer_support_email_ticket",
            "data_basis": "synthetic",
            "buyer_wedge": "customer support + email send + ticket update",
        },
    }


def _result_by_workflow(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item.get("workflow_id"): item for item in result.get("results", []) if isinstance(item, dict)}


def _step(workflow: dict[str, Any], result: dict[str, Any], record: dict[str, Any] | None) -> dict[str, Any]:
    aix = result.get("aix") if isinstance(result.get("aix"), dict) else {}
    candidate_aix = result.get("candidate_aix") if isinstance(result.get("candidate_aix"), dict) else {}
    return {
        "workflow_id": workflow.get("workflow_id"),
        "adapter": workflow.get("adapter"),
        "stage": workflow.get("metadata", {}).get("demo_stage"),
        "title": workflow.get("metadata", {}).get("demo_label"),
        "ai_proposes_action": workflow.get("metadata", {}).get("buyer_visible_action"),
        "candidate_preview": workflow.get("candidate"),
        "aana_check": {
            "gate_decision": result.get("gate_decision"),
            "recommended_action": result.get("recommended_action"),
            "candidate_gate": result.get("candidate_gate"),
            "violation_codes": [item.get("code") for item in result.get("violations", []) if item.get("code")],
        },
        "aix": {
            "score": aix.get("score"),
            "decision": aix.get("decision"),
            "components": aix.get("components"),
            "hard_blockers": aix.get("hard_blockers", []),
            "candidate_score": candidate_aix.get("score"),
            "candidate_decision": candidate_aix.get("decision"),
            "candidate_hard_blockers": candidate_aix.get("hard_blockers", []),
        },
        "safe_output_preview": result.get("output"),
        "redacted_audit": {
            "written": bool(record),
            "record_type": record.get("record_type") if record else None,
            "audit_record_version": record.get("audit_record_version") if record else None,
            "input_fingerprints": record.get("input_fingerprints", {}) if record else {},
            "raw_payload_logged": False,
        },
    }


def _render_summary(flow: dict[str, Any]) -> str:
    lines = [
        "# AANA Enterprise Support Demo Flow",
        "",
        "Wedge: `customer support + email send + ticket update`",
        "",
        "This demo is generated from real AANA runtime checks, redacted audit records, metrics, dashboard JSON, and an AIx Report. It is pilot evidence, not production certification.",
        "",
        "## Flow",
        "",
    ]
    for index, step in enumerate(flow["steps"], start=1):
        lines.extend(
            [
                f"### {index}. {step['title']}",
                "",
                f"- AI proposes action: {step['ai_proposes_action']}",
                f"- AANA gate: `{step['aana_check']['gate_decision']}`",
                f"- Recommended action: `{step['aana_check']['recommended_action']}`",
                f"- Final AIx: `{step['aix']['score']}`",
                f"- Candidate AIx: `{step['aix']['candidate_score']}`",
                f"- Violation codes: `{step['aana_check']['violation_codes']}`",
                f"- Redacted audit written: `{str(step['redacted_audit']['written']).lower()}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Generated Artifacts",
            "",
        ]
    )
    for name, path in flow["artifacts"].items():
        lines.append(f"- `{name}`: `{path}`")
    lines.extend(
        [
            "",
            "## Dashboard Snapshot",
            "",
            "```json",
            json.dumps(flow["dashboard_cards"], indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def run_enterprise_support_demo(
    *,
    output_dir: str | pathlib.Path = DEFAULT_OUTPUT_DIR,
    gallery_path: str | pathlib.Path = DEFAULT_GALLERY,
    shadow_mode: bool = False,
) -> dict[str, Any]:
    """Run the buyer-facing support/email/ticket demo and write artifacts."""

    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    created_at = _utc_now()
    paths = {
        "batch": output_dir / "support-email-ticket-batch.json",
        "audit_log": output_dir / "audit.jsonl",
        "metrics": output_dir / "metrics.json",
        "dashboard": output_dir / "enterprise-dashboard.json",
        "drift_report": output_dir / "aix-drift.json",
        "integrity_manifest": output_dir / "audit-integrity.json",
        "reviewer_report": output_dir / "reviewer-report.md",
        "aix_report_json": output_dir / "aix-report.json",
        "aix_report_md": output_dir / "aix-report.md",
        "connector_readiness": output_dir / "enterprise-connector-readiness.json",
        "demo_flow": output_dir / "demo-flow.json",
        "demo_summary": output_dir / "demo-summary.md",
    }

    batch = build_enterprise_support_demo_batch()
    _write_json(paths["batch"], batch)
    paths["audit_log"].write_text("", encoding="utf-8")

    result = agent_api.check_workflow_batch(batch, gallery_path=gallery_path)
    if shadow_mode:
        result = agent_api.apply_shadow_mode(result)
    audit_batch = agent_api.audit_workflow_batch(batch, result, created_at=created_at, shadow_mode=shadow_mode)
    for record in audit_batch.get("records", []):
        agent_api.append_audit_record(paths["audit_log"], record)

    records = agent_api.load_audit_records(paths["audit_log"])
    metrics = agent_api.export_audit_metrics_file(paths["audit_log"], output_path=paths["metrics"], created_at=created_at)
    drift = agent_api.audit_aix_drift_report_file(paths["audit_log"], output_path=paths["drift_report"], created_at=created_at)
    manifest = agent_api.create_audit_integrity_manifest(paths["audit_log"], manifest_path=paths["integrity_manifest"], created_at=created_at)
    dashboard = aix_audit.build_enterprise_dashboard(batch=batch, result=result, records=records, metrics=metrics, created_at=created_at)
    _write_json(paths["dashboard"], dashboard)
    connector_readiness = enterprise_connector_readiness.write_enterprise_connector_readiness_plan(paths["connector_readiness"])
    reviewer = agent_api.write_audit_reviewer_report(
        paths["audit_log"],
        paths["reviewer_report"],
        metrics_path=paths["metrics"],
        drift_report_path=paths["drift_report"],
        manifest_path=paths["integrity_manifest"],
        created_at=created_at,
    )
    adapter_config_validation = aix_audit.validate_enterprise_adapter_config(
        aix_audit.load_enterprise_adapter_config(aix_audit.DEFAULT_ENTERPRISE_ADAPTER_CONFIG)
    )
    calibration_validation = aix_audit.validate_enterprise_calibration_fixtures(
        aix_audit.load_enterprise_calibration_fixtures(aix_audit.DEFAULT_ENTERPRISE_CALIBRATION_FIXTURES)
    )
    aix_report = aix_audit.build_aix_report(
        batch=batch,
        result=result,
        records=records,
        metrics=metrics,
        drift=drift,
        manifest=manifest,
        reviewer_report_path=paths["reviewer_report"],
        adapter_config_validation=adapter_config_validation,
        calibration_validation=calibration_validation,
        created_at=created_at,
    )
    aix_report_validation = aix_audit.validate_aix_report(aix_report)
    _write_json(paths["aix_report_json"], aix_report)
    _write_text(paths["aix_report_md"], aix_audit.render_aix_report_markdown(aix_report))

    results_by_id = _result_by_workflow(result)
    records_by_id = {record.get("workflow_id"): record for record in records}
    steps = [
        _step(workflow, results_by_id.get(workflow.get("workflow_id"), {}), records_by_id.get(workflow.get("workflow_id")))
        for workflow in batch["requests"]
    ]
    actions = {step["aana_check"]["recommended_action"] for step in steps}
    flow = {
        "enterprise_support_demo_version": ENTERPRISE_SUPPORT_DEMO_VERSION,
        "created_at": created_at,
        "product": "AANA AIx Audit",
        "product_bundle": "enterprise_ops_pilot",
        "wedge": "customer support + email send + ticket update",
        "claim_boundary": "Pilot demo evidence only; not production certification.",
        "story": [
            "AI proposes customer-support, email-send, and ticket-update actions.",
            "AANA checks each proposed action against evidence and constraints.",
            "AIx scores and verifier findings are produced.",
            "Unsafe actions are revised or deferred before execution.",
            "Redacted audit records, dashboard metrics, and an AIx Report are generated.",
        ],
        "valid": (
            bool(records)
            and aix_report_validation["valid"]
            and connector_readiness["validation"]["valid"]
            and "revise" in actions
            and "defer" in actions
        ),
        "steps": steps,
        "dashboard_cards": dashboard.get("cards", {}),
        "dashboard_metrics": {
            "recommended_actions": dashboard.get("recommended_actions", {}),
            "top_violations": dashboard.get("top_violations", []),
            "adapter_breakdown": dashboard.get("adapter_breakdown", []),
        },
        "aix_report_summary": {
            "deployment_recommendation": aix_report.get("deployment_recommendation"),
            "overall_aix": aix_report.get("overall_aix"),
            "hard_blockers": aix_report.get("hard_blockers", []),
            "limitations": aix_report.get("limitations", []),
        },
        "artifacts": {name: str(path) for name, path in paths.items()},
        "report_validation": aix_report_validation,
        "reviewer_report": reviewer,
    }
    _write_json(paths["demo_flow"], flow)
    _write_text(paths["demo_summary"], _render_summary(flow))
    return flow


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "ENTERPRISE_SUPPORT_DEMO_VERSION",
    "build_enterprise_support_demo_batch",
    "run_enterprise_support_demo",
]
