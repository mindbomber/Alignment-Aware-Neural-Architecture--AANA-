"""Production evidence integration stubs for AANA adapters.

These stubs do not connect to external systems. They define the source IDs,
auth boundary, redaction expectations, and structured evidence shape that a
real connector must satisfy before an adapter can rely on production evidence.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field


INTEGRATION_STUB_VERSION = "0.1"


@dataclass(frozen=True)
class EvidenceIntegrationStub:
    integration_id: str
    title: str
    system_type: str
    adapter_ids: tuple[str, ...]
    required_source_ids: tuple[str, ...]
    optional_source_ids: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    auth_boundary: str = "Use service-owned credentials, least privilege, and explicit tenant scoping."
    redaction_policy: str = "Return redacted summaries by default; keep raw records in the source system."
    freshness_slo: str = "Connector must stamp retrieved_at and enforce the source freshness SLO."
    failure_mode: str = "If evidence is missing, stale, unauthorized, or unredacted, route to retrieve, ask, or defer."

    def to_dict(self):
        return {
            "integration_id": self.integration_id,
            "title": self.title,
            "system_type": self.system_type,
            "adapter_ids": list(self.adapter_ids),
            "required_source_ids": list(self.required_source_ids),
            "optional_source_ids": list(self.optional_source_ids),
            "operations": list(self.operations),
            "auth_boundary": self.auth_boundary,
            "redaction_policy": self.redaction_policy,
            "freshness_slo": self.freshness_slo,
            "failure_mode": self.failure_mode,
        }

    def evidence_template(self, source_id=None, now=None):
        source = source_id or self.required_source_ids[0]
        if source not in set(self.required_source_ids) | set(self.optional_source_ids):
            raise ValueError(f"Unknown source_id {source!r} for integration {self.integration_id!r}.")
        timestamp = now or datetime.datetime.now(datetime.timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
        return {
            "source_id": source,
            "retrieved_at": timestamp.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "trust_tier": "verified",
            "redaction_status": "redacted",
            "text": f"Redacted {self.title} evidence from {source}. Replace with connector output.",
            "metadata": {
                "integration_id": self.integration_id,
                "system_type": self.system_type,
                "stub": True,
            },
        }

    def fetch_evidence(self, *args, **kwargs):
        raise NotImplementedError(
            f"{self.integration_id} is a production evidence integration stub. "
            "Implement connector-specific authentication, retrieval, redaction, freshness checks, and audit logging."
        )


INTEGRATION_STUBS = (
    EvidenceIntegrationStub(
        integration_id="crm_support",
        title="CRM and Support Account Evidence",
        system_type="crm",
        adapter_ids=("crm_support_reply", "support_reply", "customer_success_renewal", "sales_proposal_checker"),
        required_source_ids=("crm-record", "support-policy", "order-system"),
        optional_source_ids=("crm", "crm-opportunity", "account-health", "contract", "price-book"),
        operations=("read_account_facts", "read_order_status", "read_support_policy", "read_renewal_context"),
        auth_boundary="Use support/revenue service credentials scoped to the current customer account and case.",
        redaction_policy="Return account facts and eligibility summaries without payment details, internal notes, or raw CRM records.",
    ),
    EvidenceIntegrationStub(
        integration_id="ticketing",
        title="Ticketing and Sprint Evidence",
        system_type="ticketing",
        adapter_ids=("ticket_update_checker", "incident_response_update", "product_requirements_checker"),
        required_source_ids=("ticket-history", "sprint-status", "support-policy"),
        optional_source_ids=("roadmap", "prd", "policy-checklist"),
        operations=("read_ticket_history", "read_sprint_status", "read_customer_visible_policy"),
        auth_boundary="Use project-scoped credentials and preserve customer/internal visibility boundaries.",
        redaction_policy="Return status summaries; do not expose internal-only comments in customer-visible evidence.",
    ),
    EvidenceIntegrationStub(
        integration_id="email_send",
        title="Email Draft and Recipient Evidence",
        system_type="email",
        adapter_ids=("email_send_guardrail", "publication_check"),
        required_source_ids=("draft-email", "recipient-metadata", "user-approval"),
        optional_source_ids=("publication-approval-policy",),
        operations=("read_draft", "read_recipient_metadata", "read_user_approval"),
        auth_boundary="Use mailbox-scoped credentials and require explicit user approval before irreversible send actions.",
        redaction_policy="Return recipient class, attachment summary, approval state, and private-data flags instead of full mailbox content.",
    ),
    EvidenceIntegrationStub(
        integration_id="calendar",
        title="Calendar Availability Evidence",
        system_type="calendar",
        adapter_ids=("calendar_scheduling",),
        required_source_ids=("calendar-freebusy", "attendee-list", "user-instruction"),
        optional_source_ids=(),
        operations=("read_freebusy", "read_attendees", "read_scheduling_instruction"),
        auth_boundary="Use calendar-scoped credentials; do not send or update invites without user consent.",
        redaction_policy="Return availability windows and attendee metadata without unrelated event details.",
    ),
    EvidenceIntegrationStub(
        integration_id="iam",
        title="Identity and Access Evidence",
        system_type="iam",
        adapter_ids=("access_permission_change", "data_export_guardrail"),
        required_source_ids=("iam-request", "role-catalog", "approval-record"),
        optional_source_ids=("access-grants",),
        operations=("read_access_request", "read_role_catalog", "read_approval_record"),
        auth_boundary="Use IAM read-only credentials for checks; write permissions must remain outside the evidence connector.",
        redaction_policy="Return requester authority, requested scope, expiry, and approval state without broad directory dumps.",
    ),
    EvidenceIntegrationStub(
        integration_id="ci",
        title="CI and Code Review Evidence",
        system_type="ci",
        adapter_ids=("code_change_review", "api_contract_change", "model_evaluation_release"),
        required_source_ids=("git-diff", "test-output", "ci-status"),
        optional_source_ids=("openapi-diff", "consumer-list", "eval-results", "model-card"),
        operations=("read_diff", "read_test_output", "read_ci_status", "read_contract_diff"),
        auth_boundary="Use repository-scoped read credentials; never expose secrets from logs or diffs.",
        redaction_policy="Return diff/test summaries and secret-scan status, with raw logs stored in CI.",
    ),
    EvidenceIntegrationStub(
        integration_id="deployment",
        title="Deployment and Release Evidence",
        system_type="deployment",
        adapter_ids=("deployment_readiness", "feature_flag_rollout", "infrastructure_change_guardrail"),
        required_source_ids=("deployment-manifest", "ci-result", "release-notes"),
        optional_source_ids=("flag-config", "metrics", "iac-diff", "plan-output", "infrastructure-policy"),
        operations=("read_deployment_manifest", "read_ci_result", "read_release_notes", "read_rollout_plan"),
        auth_boundary="Use deployment read credentials; deploy/promote actions require a separate approved executor.",
        redaction_policy="Return release readiness and rollback summaries without leaking secrets or private incident data.",
    ),
    EvidenceIntegrationStub(
        integration_id="billing",
        title="Billing and Payment Evidence",
        system_type="billing",
        adapter_ids=("invoice_billing_reply", "booking_purchase_guardrail"),
        required_source_ids=("invoice", "billing-policy", "payment-metadata"),
        optional_source_ids=("live-quote", "cart", "payment-policy"),
        operations=("read_invoice", "read_billing_policy", "read_payment_metadata", "read_cart_or_quote"),
        auth_boundary="Use billing read credentials scoped to the customer/account and payment intent.",
        redaction_policy="Return balances, credit eligibility, and payment state without card, bank, or tax-sensitive raw fields.",
    ),
    EvidenceIntegrationStub(
        integration_id="data_export",
        title="Data Export Authorization Evidence",
        system_type="data_export",
        adapter_ids=("data_export_guardrail", "data_pipeline_change"),
        required_source_ids=("data-classification", "access-grants", "export-request"),
        optional_source_ids=("schema-registry", "lineage-graph", "dag-metadata"),
        operations=("read_data_classification", "read_access_grants", "read_export_request", "read_retention_policy"),
        auth_boundary="Use data-governance read credentials; actual export execution must require separate authorization.",
        redaction_policy="Return classification, scope, destination, grants, and retention status without exporting the dataset.",
    ),
    EvidenceIntegrationStub(
        integration_id="workspace_files",
        title="Workspace File Operation Evidence",
        system_type="filesystem",
        adapter_ids=("file_operation_guardrail",),
        required_source_ids=("file-metadata", "requested-action", "diff-preview", "backup-status", "user-confirmation"),
        optional_source_ids=(),
        operations=("read_file_metadata", "read_requested_action", "read_diff_preview", "read_backup_status"),
        auth_boundary="Use workspace-scoped read access; write/move/delete execution must remain in a separate confirmed path.",
        redaction_policy="Return path scope, operation preview, and backup status without unnecessary file contents.",
    ),
    EvidenceIntegrationStub(
        integration_id="security",
        title="Security Advisory and Scanner Evidence",
        system_type="security",
        adapter_ids=("security_vulnerability_disclosure",),
        required_source_ids=("security-advisory", "scanner-output", "release-notes"),
        optional_source_ids=("ci-status",),
        operations=("read_security_advisory", "read_scanner_output", "read_security_release_notes"),
        auth_boundary="Use security-read credentials and respect disclosure embargoes.",
        redaction_policy="Return CVE facts, affected versions, exploitability, remediation, and disclosure timing without embargo leakage.",
    ),
)


def all_integration_stubs():
    return list(INTEGRATION_STUBS)


def integration_stub_map():
    return {stub.integration_id: stub for stub in INTEGRATION_STUBS}


def find_integration_stub(integration_id):
    try:
        return integration_stub_map()[integration_id]
    except KeyError as exc:
        available = ", ".join(sorted(integration_stub_map()))
        raise ValueError(f"Unknown evidence integration: {integration_id}. Available integrations: {available}.") from exc


def source_ids_from_registry(registry):
    sources = registry.get("sources", []) if isinstance(registry, dict) else []
    if not isinstance(sources, list):
        return set()
    return {source.get("source_id") for source in sources if isinstance(source, dict) and source.get("source_id")}


def integration_coverage_report(registry=None):
    source_ids = source_ids_from_registry(registry or {})
    integrations = []
    missing_total = 0
    for stub in all_integration_stubs():
        required = set(stub.required_source_ids)
        missing = sorted(required - source_ids) if registry is not None else []
        missing_total += len(missing)
        integrations.append(
            {
                **stub.to_dict(),
                "registry_covered": registry is not None and not missing,
                "missing_source_ids": missing,
                "evidence_template": stub.evidence_template(now=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)),
            }
        )
    return {
        "integration_stub_version": INTEGRATION_STUB_VERSION,
        "valid": missing_total == 0,
        "registry_checked": registry is not None,
        "integration_count": len(integrations),
        "missing_source_id_count": missing_total,
        "integrations": integrations,
    }
