"""Enterprise-ops live connector readiness layer for AANA AIx Audit."""

from __future__ import annotations

import datetime
import json
import pathlib
from typing import Any

from eval_pipeline import evidence_integrations


ROOT = pathlib.Path(__file__).resolve().parents[1]
ENTERPRISE_CONNECTOR_READINESS_VERSION = "0.1"
ENTERPRISE_CONNECTOR_READINESS_TYPE = "aana_enterprise_ops_connector_readiness"
DEFAULT_ENTERPRISE_CONNECTOR_READINESS_PATH = ROOT / "examples" / "enterprise_ops_connector_readiness.json"

REQUIRED_CONNECTOR_IDS = (
    "crm_support",
    "ticketing",
    "email_send",
    "iam",
    "ci",
    "deployment",
    "data_export",
)

REQUIRED_CONNECTOR_FIELDS = (
    "connector_id",
    "display_name",
    "pilot_surface",
    "integration_id",
    "adapter_ids",
    "source_system_examples",
    "required_evidence",
    "auth_requirements",
    "redaction_requirements",
    "freshness_requirements",
    "rate_limits",
    "setup_steps",
    "smoke_tests",
    "failure_routes",
    "shadow_mode_requirements",
    "go_live_blockers",
)


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _connector(
    *,
    connector_id: str,
    display_name: str,
    pilot_surface: str,
    adapter_ids: list[str],
    source_system_examples: list[str],
    required_evidence: list[str],
    scopes: list[str],
    freshness_slo_minutes: int,
    rpm: int,
    setup_steps: list[str],
    smoke_tests: list[str],
    go_live_blockers: list[str],
    write_capable: bool = False,
    irreversible: bool = False,
) -> dict[str, Any]:
    return {
        "connector_id": connector_id,
        "display_name": display_name,
        "pilot_surface": pilot_surface,
        "integration_id": connector_id,
        "adapter_ids": adapter_ids,
        "source_system_examples": source_system_examples,
        "live_execution_enabled": False,
        "write_capable": write_capable,
        "irreversible_action_risk": irreversible,
        "default_runtime_route_before_approval": "defer",
        "required_evidence": required_evidence,
        "auth_requirements": {
            "mode": "customer_managed_oauth_or_service_account",
            "least_privilege_scopes": scopes,
            "credential_storage": "customer_secret_manager_or_vault",
            "tokens_in_audit_logs": False,
            "rotation_required": True,
            "owner_approval_required": True,
        },
        "redaction_requirements": {
            "raw_private_content_allowed_in_audit": False,
            "raw_prompt_candidate_output_allowed_in_audit": False,
            "audit_payload": "metadata_ids_hashes_counts_and_status_only",
            "evidence_text_policy": "redacted_summary_or_fingerprint_only",
            "fingerprint_required": True,
        },
        "freshness_requirements": {
            "slo_minutes": freshness_slo_minutes,
            "retrieved_at_required": True,
            "stale_evidence_route": "retrieve",
            "unavailable_connector_route": "defer",
        },
        "rate_limits": {
            "requests_per_minute": rpm,
            "burst": max(1, min(5, rpm // 10 or 1)),
            "retry_policy": "bounded_exponential_backoff_with_jitter",
            "rate_limit_route": "defer",
        },
        "setup_steps": setup_steps,
        "smoke_tests": smoke_tests,
        "failure_routes": {
            "missing_evidence": "retrieve",
            "unknown_source": "defer",
            "unauthorized": "defer",
            "stale_evidence": "retrieve",
            "unredacted_evidence": "defer",
            "connector_unavailable": "defer",
            "write_attempt_in_shadow_mode": "defer",
        },
        "shadow_mode_requirements": {
            "write_operations_disabled": True,
            "sample_before_enforcement": True,
            "minimum_records": 100,
            "minimum_days": 14,
            "dashboard_metrics_required": True,
        },
        "go_live_blockers": go_live_blockers,
    }


def default_enterprise_connectors() -> list[dict[str, Any]]:
    """Return concrete connector readiness specs for the enterprise-ops pilot."""

    return [
        _connector(
            connector_id="crm_support",
            display_name="CRM/support",
            pilot_surface="support_customer_communications",
            adapter_ids=["support_reply", "crm_support_reply"],
            source_system_examples=["Salesforce Service Cloud", "Zendesk Sell", "HubSpot Service Hub", "custom CRM"],
            required_evidence=["customer account summary", "case context", "order/refund state", "support policy reference"],
            scopes=["crm.account.read_minimal", "crm.case.read", "crm.policy.read"],
            freshness_slo_minutes=30,
            rpm=60,
            setup_steps=[
                "Create least-privilege read-only service account or OAuth app.",
                "Map customer/account/case identifiers to redacted evidence source IDs.",
                "Enable PII minimization before evidence enters AANA.",
                "Run synthetic and shadow-mode support reply checks before enforcement.",
            ],
            smoke_tests=[
                "Fetch redacted account facts for a known test case.",
                "Verify no payment details or internal notes appear in audit JSONL.",
                "Confirm stale or missing CRM evidence routes to retrieve/defer.",
            ],
            go_live_blockers=["missing CRM owner approval", "unredacted account records", "no refund/order evidence mapping"],
        ),
        _connector(
            connector_id="ticketing",
            display_name="Ticketing",
            pilot_surface="support_customer_communications",
            adapter_ids=["ticket_update_checker", "incident_response_update"],
            source_system_examples=["Zendesk", "Jira Service Management", "ServiceNow", "Linear"],
            required_evidence=["ticket history", "public/private comment status", "linked issue state", "SLA or escalation state"],
            scopes=["ticket.read", "ticket.comment.read", "ticket.status.read"],
            freshness_slo_minutes=15,
            rpm=60,
            setup_steps=[
                "Create read-only ticketing connector for shadow mode.",
                "Classify public versus internal comments before evidence export.",
                "Map ticket state and customer-visible fields to structured evidence.",
            ],
            smoke_tests=[
                "Fetch one redacted ticket history record.",
                "Confirm private comments are summarized or omitted.",
                "Verify unsupported ETA/status claims trigger revise/defer.",
            ],
            go_live_blockers=["private comment leakage", "unmapped public/private field boundary", "no ticket owner signoff"],
        ),
        _connector(
            connector_id="email_send",
            display_name="Email send",
            pilot_surface="support_customer_communications",
            adapter_ids=["email_send_guardrail"],
            source_system_examples=["Gmail", "Microsoft Graph/Outlook", "SendGrid", "customer SMTP relay"],
            required_evidence=["recipient metadata", "draft summary", "attachment manifest", "send approval state", "DLP labels"],
            scopes=["mail.read_metadata", "mail.draft.read", "mail.send_disabled_in_shadow"],
            freshness_slo_minutes=5,
            rpm=30,
            write_capable=True,
            irreversible=True,
            setup_steps=[
                "Start with draft/read metadata only; disable live send in shadow mode.",
                "Map recipient, attachment, approval, and DLP state to redacted evidence.",
                "Require explicit send approval and recipient verification before any enforcement path.",
            ],
            smoke_tests=[
                "Check wrong-recipient fixture routes to revise/refuse.",
                "Confirm attachments are represented by metadata/fingerprint only.",
                "Verify any live-send attempt in shadow mode routes to defer.",
            ],
            go_live_blockers=["live send enabled before shadow approval", "missing recipient verification", "attachment body exposed"],
        ),
        _connector(
            connector_id="iam",
            display_name="IAM/access",
            pilot_surface="data_access_controls",
            adapter_ids=["access_permission_change"],
            source_system_examples=["Okta", "Entra ID", "AWS IAM", "Google Cloud IAM", "custom RBAC"],
            required_evidence=["requester identity", "target principal", "resource owner", "role catalog", "approval record", "expiration"],
            scopes=["iam.request.read", "iam.role.read", "iam.approval.read"],
            freshness_slo_minutes=10,
            rpm=20,
            write_capable=True,
            irreversible=True,
            setup_steps=[
                "Use read-only policy simulation and approval-state retrieval for shadow mode.",
                "Map owner/admin/wildcard changes to strict risk tier.",
                "Require security-owner approval before any permission-changing connector is enabled.",
            ],
            smoke_tests=[
                "Verify wildcard/admin request triggers defer/refuse.",
                "Confirm missing approval routes to ask/defer.",
                "Confirm principal IDs are redacted or fingerprinted in audit records.",
            ],
            go_live_blockers=["write scope enabled in shadow mode", "missing security-owner approval", "no revocation rollback path"],
        ),
        _connector(
            connector_id="ci",
            display_name="CI/CD",
            pilot_surface="devops_release_controls",
            adapter_ids=["code_change_review", "deployment_readiness"],
            source_system_examples=["GitHub Actions", "GitLab CI", "CircleCI", "Buildkite", "Jenkins"],
            required_evidence=["CI status", "test output summary", "secret scan status", "artifact attestations", "required checks"],
            scopes=["ci.status.read", "ci.logs.summary.read", "security.scan.read"],
            freshness_slo_minutes=10,
            rpm=60,
            setup_steps=[
                "Expose status summaries rather than raw logs by default.",
                "Map required checks, failed tests, and secret-scan outcomes to structured evidence.",
                "Keep build secrets and full logs out of audit artifacts.",
            ],
            smoke_tests=[
                "Fetch redacted CI status for a test branch.",
                "Confirm failed tests or unknown CI status trigger revise/defer.",
                "Verify secret-like values are not persisted in audit logs.",
            ],
            go_live_blockers=["raw CI logs in audit", "missing required-check mapping", "secret scan unavailable"],
        ),
        _connector(
            connector_id="deployment",
            display_name="Deployment",
            pilot_surface="devops_release_controls",
            adapter_ids=["deployment_readiness", "incident_response_update"],
            source_system_examples=["Argo CD", "Spinnaker", "GitHub Deployments", "Kubernetes", "custom release system"],
            required_evidence=["deployment manifest", "environment", "rollback plan", "health checks", "migration plan", "observability policy"],
            scopes=["deploy.manifest.read", "deploy.status.read", "release.rollback.read"],
            freshness_slo_minutes=5,
            rpm=20,
            write_capable=True,
            irreversible=True,
            setup_steps=[
                "Start with manifest/status read-only evidence.",
                "Require rollback, health check, migration, and observability evidence before any accept route.",
                "Keep direct deploy execution disabled until controlled enforcement is approved.",
            ],
            smoke_tests=[
                "Verify missing rollback or health checks trigger revise/defer.",
                "Confirm secret-like manifest values are blocked from audit output.",
                "Confirm production deploy attempts route to defer in shadow mode.",
            ],
            go_live_blockers=["no rollback runbook", "observability policy missing", "write deploy scope enabled before approval"],
        ),
        _connector(
            connector_id="data_export",
            display_name="Data export",
            pilot_surface="data_access_controls",
            adapter_ids=["data_export_guardrail"],
            source_system_examples=["Snowflake", "BigQuery", "Databricks", "Redshift", "S3/GCS export service"],
            required_evidence=["data classification", "field list", "requester authorization", "recipient/destination approval", "retention policy", "legal hold"],
            scopes=["dataset.metadata.read", "classification.read", "export.request.read"],
            freshness_slo_minutes=10,
            rpm=15,
            write_capable=True,
            irreversible=True,
            setup_steps=[
                "Expose metadata/classification only during shadow mode, not raw rows.",
                "Map export destination, retention, approval, and legal-hold state to structured evidence.",
                "Require data-owner approval before any export execution connector is enabled.",
            ],
            smoke_tests=[
                "Verify PII export to external destination triggers defer/refuse.",
                "Confirm raw rows and query text do not appear in audit logs.",
                "Confirm missing retention or destination approval routes to retrieve/defer.",
            ],
            go_live_blockers=["raw rows exposed", "missing data-owner approval", "legal-hold state unavailable"],
        ),
    ]


def enterprise_connector_readiness_plan(
    connectors: list[dict[str, Any]] | None = None,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    connector_list = connectors if connectors is not None else default_enterprise_connectors()
    return {
        "enterprise_connector_readiness_version": ENTERPRISE_CONNECTOR_READINESS_VERSION,
        "plan_type": ENTERPRISE_CONNECTOR_READINESS_TYPE,
        "created_at": created_at or _utc_now(),
        "product_bundle": "enterprise_ops_pilot",
        "summary": {
            "connector_count": len(connector_list),
            "required_connector_ids": list(REQUIRED_CONNECTOR_IDS),
            "live_execution_enabled_count": sum(1 for connector in connector_list if connector.get("live_execution_enabled") is True),
            "write_capable_connector_count": sum(1 for connector in connector_list if connector.get("write_capable") is True),
            "shadow_mode_default": True,
        },
        "common_controls": {
            "shadow_mode_first": True,
            "redacted_audit_only": True,
            "customer_secret_manager_required": True,
            "domain_owner_signoff_required": True,
            "security_review_required": True,
            "human_review_operations_required": True,
            "immutable_audit_retention_required_for_production": True,
        },
        "connectors": connector_list,
    }


def validate_enterprise_connector_readiness_plan(plan: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(plan, dict):
        return {"valid": False, "errors": 1, "warnings": 0, "issues": [{"level": "error", "path": "$", "message": "Plan must be an object."}]}
    if plan.get("enterprise_connector_readiness_version") != ENTERPRISE_CONNECTOR_READINESS_VERSION:
        issues.append({"level": "error", "path": "$.enterprise_connector_readiness_version", "message": f"Must be {ENTERPRISE_CONNECTOR_READINESS_VERSION}."})
    if plan.get("plan_type") != ENTERPRISE_CONNECTOR_READINESS_TYPE:
        issues.append({"level": "error", "path": "$.plan_type", "message": f"Must be {ENTERPRISE_CONNECTOR_READINESS_TYPE}."})
    connectors = plan.get("connectors")
    if not isinstance(connectors, list) or not connectors:
        issues.append({"level": "error", "path": "$.connectors", "message": "At least one connector is required."})
        connectors = []

    seen = set()
    for index, connector in enumerate(connectors):
        path = f"$.connectors[{index}]"
        if not isinstance(connector, dict):
            issues.append({"level": "error", "path": path, "message": "Connector must be an object."})
            continue
        for field in REQUIRED_CONNECTOR_FIELDS:
            if connector.get(field) in (None, "", [], {}):
                issues.append({"level": "error", "path": f"{path}.{field}", "message": f"Missing connector readiness field: {field}."})
        connector_id = connector.get("connector_id")
        if isinstance(connector_id, str):
            seen.add(connector_id)
            try:
                evidence_integrations.find_integration_stub(connector.get("integration_id") or connector_id)
            except Exception:
                issues.append({"level": "error", "path": f"{path}.integration_id", "message": "Connector must map to a known evidence integration stub."})
        if connector.get("live_execution_enabled") is not False:
            issues.append({"level": "error", "path": f"{path}.live_execution_enabled", "message": "Live execution must remain disabled until customer approval."})
        if connector.get("default_runtime_route_before_approval") != "defer":
            issues.append({"level": "error", "path": f"{path}.default_runtime_route_before_approval", "message": "Unapproved live connector usage must defer."})
        auth = connector.get("auth_requirements") if isinstance(connector.get("auth_requirements"), dict) else {}
        if auth.get("tokens_in_audit_logs") is not False:
            issues.append({"level": "error", "path": f"{path}.auth_requirements.tokens_in_audit_logs", "message": "Tokens must not enter audit logs."})
        redaction = connector.get("redaction_requirements") if isinstance(connector.get("redaction_requirements"), dict) else {}
        if redaction.get("raw_private_content_allowed_in_audit") is not False:
            issues.append({"level": "error", "path": f"{path}.redaction_requirements.raw_private_content_allowed_in_audit", "message": "Raw private content must not enter audit logs."})
        shadow = connector.get("shadow_mode_requirements") if isinstance(connector.get("shadow_mode_requirements"), dict) else {}
        if shadow.get("write_operations_disabled") is not True:
            issues.append({"level": "error", "path": f"{path}.shadow_mode_requirements.write_operations_disabled", "message": "Write operations must be disabled in shadow mode."})

    missing = sorted(set(REQUIRED_CONNECTOR_IDS) - seen)
    if missing:
        issues.append({"level": "error", "path": "$.connectors", "message": f"Missing required enterprise connectors: {missing}."})
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    if summary.get("live_execution_enabled_count") != 0:
        issues.append({"level": "error", "path": "$.summary.live_execution_enabled_count", "message": "Live execution enabled count must be zero before customer approval."})

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "connector_count": len(connectors),
        "issues": issues,
    }


def write_enterprise_connector_readiness_plan(
    path: str | pathlib.Path = DEFAULT_ENTERPRISE_CONNECTOR_READINESS_PATH,
    *,
    connectors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    plan = enterprise_connector_readiness_plan(connectors)
    validation = validate_enterprise_connector_readiness_plan(plan)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(output), "plan": plan, "validation": validation, "bytes": output.stat().st_size}


__all__ = [
    "DEFAULT_ENTERPRISE_CONNECTOR_READINESS_PATH",
    "ENTERPRISE_CONNECTOR_READINESS_TYPE",
    "ENTERPRISE_CONNECTOR_READINESS_VERSION",
    "REQUIRED_CONNECTOR_IDS",
    "default_enterprise_connectors",
    "enterprise_connector_readiness_plan",
    "validate_enterprise_connector_readiness_plan",
    "write_enterprise_connector_readiness_plan",
]
