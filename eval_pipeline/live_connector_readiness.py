"""Live connector readiness planning for the local AANA MI release candidate."""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline.mi_release_bundle import DEFAULT_MI_RELEASE_BUNDLE_DIR


LIVE_CONNECTOR_READINESS_VERSION = "0.1"
LIVE_CONNECTOR_READINESS_PLAN_TYPE = "aana_mi_live_connector_readiness_plan"
DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH = DEFAULT_MI_RELEASE_BUNDLE_DIR / "live_connector_readiness_plan.json"
DEFAULT_REQUIRED_CONTROLS = (
    "production_mi_readiness_pass",
    "release_bundle_verification_pass",
    "approved_human_signoff",
    "connector_specific_auth_review",
    "connector_specific_rate_limit_review",
    "connector_specific_redaction_review",
    "connector_specific_rollback_review",
    "immutable_audit_storage_configured",
    "pre_execution_hook_allow",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _auth(requirement: str, scopes: list[str]) -> dict[str, Any]:
    return {
        "mode": requirement,
        "least_privilege_scopes": scopes,
        "secret_handling": "no_tokens_or_secrets_in_audit_dashboard_review_or_bundle_artifacts",
        "rotation_required": True,
        "approval_required": True,
    }


def _rate_limits(requests_per_minute: int, burst: int = 1) -> dict[str, Any]:
    return {
        "requests_per_minute": requests_per_minute,
        "burst": burst,
        "retry_policy": "bounded_exponential_backoff_with_jitter",
        "idempotency_key_required": True,
        "rate_limit_violations_route": "defer",
    }


def _redaction(content_policy: str) -> dict[str, Any]:
    return {
        "raw_private_content_allowed": False,
        "audit_policy": "redacted_metadata_only",
        "evidence_policy": "structured_evidence_metadata_only",
        "content_policy": content_policy,
        "fingerprint_required": True,
    }


def _rollback(strategy: str, irreversible: bool = False) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "dry_run_required": True,
        "rollback_owner_required": True,
        "irreversible_action": irreversible,
        "irreversible_route": "defer" if irreversible else "revise",
    }


def _connector(
    connector_id: str,
    family: str,
    auth: dict[str, Any],
    rate_limits: dict[str, Any],
    redaction: dict[str, Any],
    rollback: dict[str, Any],
    required_before_enablement: list[str],
) -> dict[str, Any]:
    return {
        "connector_id": connector_id,
        "family": family,
        "scope_status": "out_of_scope_for_local_rc",
        "live_execution_enabled": False,
        "default_route": "defer",
        "auth_requirements": auth,
        "rate_limits": rate_limits,
        "redaction": redaction,
        "rollback": rollback,
        "mi_gate_requirements": list(DEFAULT_REQUIRED_CONTROLS),
        "required_before_enablement": required_before_enablement,
    }


def default_live_connectors() -> list[dict[str, Any]]:
    """Return the live connector boundaries that remain outside this local RC."""

    return [
        _connector(
            "email_send",
            "email_calendar",
            _auth("oauth_user_or_service_account", ["mail.read_metadata", "mail.send_draft_or_send"]),
            _rate_limits(30, burst=3),
            _redaction("message_subject_body_recipients_and_attachments_must_be_redacted_or_fingerprinted"),
            _rollback("draft_then_send; delete_or_follow_up_only_when_provider_supports_it", irreversible=True),
            ["domain_owner_send_policy", "recipient_allowlist", "attachment_scanner", "send_dry_run"],
        ),
        _connector(
            "calendar_write",
            "email_calendar",
            _auth("oauth_user_or_service_account", ["calendar.read", "calendar.events.write"]),
            _rate_limits(60, burst=5),
            _redaction("attendee_identity_location_notes_and_descriptions_must_be_redacted"),
            _rollback("cancel_or_restore_previous_event_snapshot"),
            ["calendar_conflict_policy", "attendee_confirmation_policy", "timezone_validation"],
        ),
        _connector(
            "deployment_release",
            "deployment_release",
            _auth("ci_cd_service_account", ["deploy.read", "deploy.execute", "release.rollback"]),
            _rate_limits(5, burst=1),
            _redaction("commit_messages_logs_env_names_and_incident_context_must_be_redacted"),
            _rollback("previous_release_redeploy_or_feature_flag_disable", irreversible=True),
            ["environment_approval", "rollback_runbook", "change_window", "artifact_attestation"],
        ),
        _connector(
            "workspace_file_write",
            "file_edit",
            _auth("local_workspace_identity", ["workspace.read", "workspace.write_with_path_scope"]),
            _rate_limits(120, burst=10),
            _redaction("file_paths_may_be_logged_but_raw_file_content_requires_fingerprint_only"),
            _rollback("copy_before_write_or_patch_reversal"),
            ["path_allowlist", "diff_preview", "backup_or_vcs_checkpoint", "destructive_operation_block"],
        ),
        _connector(
            "remote_code_repository",
            "code_repository",
            _auth("repository_app_or_fine_grained_token", ["contents.read", "pull_requests.write", "checks.read"]),
            _rate_limits(60, burst=5),
            _redaction("branch_names_pr_titles_and_review_summaries_only_no_raw_secrets"),
            _rollback("revert_commit_or_close_pull_request", irreversible=True),
            ["branch_protection_review", "required_checks_policy", "secret_scan_gate"],
        ),
        _connector(
            "crm_support",
            "customer_support",
            _auth("service_account", ["customer.read_minimal", "case.read", "case.comment_draft"]),
            _rate_limits(60, burst=5),
            _redaction("customer_identifiers_case_notes_and_private_records_must_be_redacted"),
            _rollback("draft_only_until_human_approval"),
            ["customer_data_policy", "case_scope_contract", "pii_redaction_test"],
        ),
        _connector(
            "ticketing",
            "customer_support",
            _auth("service_account", ["ticket.read", "ticket.comment_draft", "ticket.status_write"]),
            _rate_limits(45, burst=5),
            _redaction("ticket_body_comments_reporter_and_internal_notes_must_be_redacted"),
            _rollback("status_restore_or_comment_correction"),
            ["ticket_status_policy", "queue_owner_signoff", "private_comment_filter"],
        ),
        _connector(
            "billing_payment",
            "financial",
            _auth("payment_service_account", ["billing.read", "refund.draft"]),
            _rate_limits(10, burst=1),
            _redaction("payment_identifiers_amounts_customer_records_and_dispute_notes_must_be_redacted"),
            _rollback("void_or_refund_only_under_payment_provider_rules", irreversible=True),
            ["finance_owner_approval", "amount_thresholds", "fraud_policy", "audit_retention_policy"],
        ),
        _connector(
            "data_export",
            "data_governance",
            _auth("export_service_account", ["dataset.read", "export.create_draft"]),
            _rate_limits(10, burst=1),
            _redaction("dataset_rows_private_columns_and_query_text_must_not_enter_mi_logs"),
            _rollback("delete_export_package_before_delivery", irreversible=True),
            ["data_classification", "recipient_approval", "retention_policy", "egress_review"],
        ),
        _connector(
            "iam_permissions",
            "security",
            _auth("privileged_service_account", ["iam.read", "iam.change_request"]),
            _rate_limits(5, burst=1),
            _redaction("principal_ids_groups_roles_and_policy_documents_must_be_redacted_or_fingerprinted"),
            _rollback("permission_revoke_or_policy_restore", irreversible=True),
            ["security_owner_approval", "break_glass_policy", "least_privilege_diff", "mfa_policy"],
        ),
        _connector(
            "chat_slack_teams",
            "collaboration",
            _auth("bot_or_workspace_app", ["channels.read_metadata", "messages.write_draft"]),
            _rate_limits(60, burst=5),
            _redaction("channel_names_user_mentions_and_message_body_require_redaction"),
            _rollback("delete_message_or_post_correction_when_allowed"),
            ["workspace_admin_approval", "channel_allowlist", "mention_suppression_policy"],
        ),
        _connector(
            "web_publish",
            "publishing",
            _auth("publisher_service_account", ["content.read", "content.publish_draft"]),
            _rate_limits(15, burst=2),
            _redaction("draft_content_urls_metadata_and_private_assets_must_be_redacted"),
            _rollback("unpublish_or_restore_previous_revision", irreversible=True),
            ["editorial_approval", "citation_review", "asset_license_review", "cache_purge_plan"],
        ),
    ]


def live_connector_readiness_plan(
    connectors: list[dict[str, Any]] | None = None,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create the local-RC live connector readiness plan."""

    connector_list = connectors if connectors is not None else default_live_connectors()
    live_enabled = [connector for connector in connector_list if connector.get("live_execution_enabled") is True]
    out_of_scope = [
        connector
        for connector in connector_list
        if connector.get("scope_status") == "out_of_scope_for_local_rc"
    ]
    return {
        "live_connector_readiness_version": LIVE_CONNECTOR_READINESS_VERSION,
        "plan_type": LIVE_CONNECTOR_READINESS_PLAN_TYPE,
        "created_at": created_at or _utc_now(),
        "local_rc_scope": {
            "status": "local_only",
            "direct_live_connector_execution": False,
            "external_production_deployment": False,
            "reason": "This RC verifies MI contracts, gates, audit, bundle integrity, and signoff artifacts without enabling external live connectors.",
        },
        "summary": {
            "connector_count": len(connector_list),
            "out_of_scope_count": len(out_of_scope),
            "live_execution_enabled_count": len(live_enabled),
            "default_route_for_live_requests": "defer",
            "required_common_controls": list(DEFAULT_REQUIRED_CONTROLS),
        },
        "connectors": connector_list,
        "enablement_policy": {
            "status_to_enable": "requires_new_release_candidate",
            "minimum_status": {
                "rc_status": "pass",
                "readiness_status": "ready",
                "bundle_verification": "pass",
                "human_signoff": "approved",
                "unresolved_blocker_count": 0,
            },
            "mi_routes_allowed_before_enablement": ["defer", "ask", "retrieve", "revise", "refuse"],
            "mi_routes_allowed_after_enablement": ["accept", "revise", "retrieve", "ask", "refuse", "defer"],
        },
    }


def validate_live_connector_readiness_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate that the live connector plan keeps this RC local-only."""

    issues: list[dict[str, str]] = []
    if not isinstance(plan, dict):
        return {"valid": False, "issues": [{"path": "$", "message": "Plan must be an object."}]}
    if plan.get("live_connector_readiness_version") != LIVE_CONNECTOR_READINESS_VERSION:
        issues.append({"path": "$.live_connector_readiness_version", "message": f"Must be {LIVE_CONNECTOR_READINESS_VERSION}."})
    if plan.get("plan_type") != LIVE_CONNECTOR_READINESS_PLAN_TYPE:
        issues.append({"path": "$.plan_type", "message": f"Must be {LIVE_CONNECTOR_READINESS_PLAN_TYPE}."})

    local_scope = plan.get("local_rc_scope") if isinstance(plan.get("local_rc_scope"), dict) else {}
    if local_scope.get("direct_live_connector_execution") is not False:
        issues.append({"path": "$.local_rc_scope.direct_live_connector_execution", "message": "Local RC must disable direct live connector execution."})
    if local_scope.get("external_production_deployment") is not False:
        issues.append({"path": "$.local_rc_scope.external_production_deployment", "message": "Local RC must not claim external production deployment."})

    connectors = plan.get("connectors")
    if not isinstance(connectors, list) or not connectors:
        issues.append({"path": "$.connectors", "message": "At least one connector boundary is required."})
        connectors = []
    seen_ids: set[str] = set()
    required_objects = ("auth_requirements", "rate_limits", "redaction", "rollback")
    for index, connector in enumerate(connectors):
        path = f"$.connectors[{index}]"
        if not isinstance(connector, dict):
            issues.append({"path": path, "message": "Connector must be an object."})
            continue
        connector_id = connector.get("connector_id")
        if not isinstance(connector_id, str) or not connector_id.strip():
            issues.append({"path": f"{path}.connector_id", "message": "Connector ID is required."})
        elif connector_id in seen_ids:
            issues.append({"path": f"{path}.connector_id", "message": "Connector ID must be unique."})
        else:
            seen_ids.add(connector_id)
        if connector.get("scope_status") != "out_of_scope_for_local_rc":
            issues.append({"path": f"{path}.scope_status", "message": "Connector must remain out of scope for this local RC."})
        if connector.get("live_execution_enabled") is not False:
            issues.append({"path": f"{path}.live_execution_enabled", "message": "Live execution must be disabled for this local RC."})
        if connector.get("default_route") != "defer":
            issues.append({"path": f"{path}.default_route", "message": "Out-of-scope live connector requests must defer by default."})
        for field in required_objects:
            if not isinstance(connector.get(field), dict):
                issues.append({"path": f"{path}.{field}", "message": f"{field} must be an object."})
        gate_requirements = connector.get("mi_gate_requirements")
        if not isinstance(gate_requirements, list):
            issues.append({"path": f"{path}.mi_gate_requirements", "message": "MI gate requirements must be a list."})
        else:
            missing = [control for control in DEFAULT_REQUIRED_CONTROLS if control not in gate_requirements]
            if missing:
                issues.append({"path": f"{path}.mi_gate_requirements", "message": "Missing required common controls: " + ", ".join(missing)})
        if not isinstance(connector.get("required_before_enablement"), list) or not connector.get("required_before_enablement"):
            issues.append({"path": f"{path}.required_before_enablement", "message": "Connector-specific enablement requirements are required."})

    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    if summary.get("live_execution_enabled_count") != 0:
        issues.append({"path": "$.summary.live_execution_enabled_count", "message": "Live execution count must be zero for the local RC."})
    if summary.get("out_of_scope_count") != len(connectors):
        issues.append({"path": "$.summary.out_of_scope_count", "message": "Every connector must be counted as out of scope."})

    return {"valid": not issues, "issues": issues}


def write_live_connector_readiness_plan(
    path: str | pathlib.Path = DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH,
    *,
    connectors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Write and validate the live connector readiness plan artifact."""

    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    plan = live_connector_readiness_plan(connectors)
    validation = validate_live_connector_readiness_plan(plan)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"plan": plan, "validation": validation, "path": str(output), "bytes": output.stat().st_size}


__all__ = [
    "DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH",
    "DEFAULT_REQUIRED_CONTROLS",
    "LIVE_CONNECTOR_READINESS_PLAN_TYPE",
    "LIVE_CONNECTOR_READINESS_VERSION",
    "default_live_connectors",
    "live_connector_readiness_plan",
    "validate_live_connector_readiness_plan",
    "write_live_connector_readiness_plan",
]
