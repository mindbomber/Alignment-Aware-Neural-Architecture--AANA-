"""Production evidence integration stubs for AANA adapters.

These stubs do not connect to external systems. They define the source IDs,
auth boundary, redaction expectations, and structured evidence shape that a
real connector must satisfy before an adapter can rely on production evidence.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace


ROOT = pathlib.Path(__file__).resolve().parents[1]
INTEGRATION_STUB_VERSION = "0.1"
CONNECTOR_CONTRACT_VERSION = "0.1"
CONNECTOR_MARKETPLACE_VERSION = "0.1"
DEFAULT_MOCK_FIXTURES_PATH = ROOT / "examples" / "evidence_mock_connector_fixtures.json"
CORE_CONNECTOR_CONTRACT_IDS = (
    "crm_support",
    "ticketing",
    "email_send",
    "calendar",
    "iam",
    "ci",
    "deployment",
    "billing",
    "data_export",
    "workspace_files",
)
PERSONAL_CONNECTOR_CONTRACT_IDS = (
    "workspace_files",
    "email_send",
    "calendar",
    "browser_cart_quote",
    "citation_source_registry",
    "local_approval",
)
CIVIC_CONNECTOR_CONTRACT_IDS = (
    "civic_program_rules",
    "civic_vendor_profiles",
    "public_law_policy_sources",
    "redaction_classification_registry",
    "civic_case_history",
    "benefits_claims",
    "civic_source_registry",
)
SUPPORT_CONNECTOR_CONTRACT_IDS = (
    "crm_customer_account",
    "order_history",
    "refund_policy",
    "internal_notes_classifier",
    "support_ticket_history",
    "email_recipient_verification",
    "attachment_metadata",
    "account_verification_status",
    "billing_payment_redaction",
    "support_policy_registry",
)
SUPPORT_ADAPTER_IDS = (
    "support_reply",
    "crm_support_reply",
    "email_send_guardrail",
    "ticket_update_checker",
    "invoice_billing_reply",
)


class EvidenceConnectorError(RuntimeError):
    """Raised when a mock or production evidence connector cannot satisfy its contract."""


@dataclass(frozen=True)
class EvidenceAuthContext:
    """Caller authorization context for a connector read.

    This object intentionally models retrieval authorization only. Production
    systems should keep action execution credentials outside evidence
    connectors so AANA can inspect proposed actions without gaining write power.
    """

    scopes: tuple[str, ...]
    tenant_id: str = "synthetic-tenant"
    principal_id: str = "synthetic-principal"
    purpose: str = "aana.evidence.read"
    credential_ref: str | None = None
    request_id: str | None = None

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        if value is None:
            return cls(scopes=())
        if isinstance(value, dict):
            scopes = value.get("scopes") or ()
            if isinstance(scopes, str):
                scopes = (scopes,)
            return cls(
                scopes=tuple(scopes),
                tenant_id=value.get("tenant_id") or "synthetic-tenant",
                principal_id=value.get("principal_id") or "synthetic-principal",
                purpose=value.get("purpose") or "aana.evidence.read",
                credential_ref=value.get("credential_ref"),
                request_id=value.get("request_id"),
            )
        if isinstance(value, str):
            return cls(scopes=(value,))
        return cls(scopes=tuple(value or ()))

    def to_dict(self):
        return {
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "purpose": self.purpose,
            "credential_ref": self.credential_ref,
            "request_id": self.request_id,
            "scopes": list(self.scopes),
        }


@dataclass(frozen=True)
class EvidenceFetchRequest:
    """Connector request object for adapter evidence retrieval."""

    integration_id: str
    source_ids: tuple[str, ...] = ()
    operation: str | None = None
    auth: EvidenceAuthContext = field(default_factory=lambda: EvidenceAuthContext(scopes=()))
    adapter_id: str | None = None
    subject_ref: str | None = None
    reason: str = "AANA adapter evidence check"
    now: datetime.datetime | str | None = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_value(cls, value, *, integration_id=None, source_ids=None, auth=None, now=None):
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls(
                integration_id=value.get("integration_id") or integration_id,
                source_ids=tuple(value.get("source_ids") or source_ids or ()),
                operation=value.get("operation"),
                auth=EvidenceAuthContext.from_value(value.get("auth") or auth),
                adapter_id=value.get("adapter_id"),
                subject_ref=value.get("subject_ref"),
                reason=value.get("reason") or "AANA adapter evidence check",
                now=value.get("now", now),
                metadata=dict(value.get("metadata") or {}),
            )
        return cls(
            integration_id=integration_id,
            source_ids=tuple(source_ids or ()),
            auth=EvidenceAuthContext.from_value(auth),
            now=now,
        )

    def to_dict(self):
        return {
            "integration_id": self.integration_id,
            "source_ids": list(self.source_ids),
            "operation": self.operation,
            "auth": self.auth.to_dict(),
            "adapter_id": self.adapter_id,
            "subject_ref": self.subject_ref,
            "reason": self.reason,
            "now": _iso_utc(self.now) if self.now is not None else None,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class EvidenceConnectorFailure:
    code: str
    source_id: str | None
    message: str
    retryable: bool = False
    route: str = "defer"

    def to_dict(self):
        return {
            "code": self.code,
            "source_id": self.source_id,
            "message": self.message,
            "retryable": self.retryable,
            "route": self.route,
        }


@dataclass(frozen=True)
class EvidenceConnectorResult:
    integration_id: str
    requested_source_ids: tuple[str, ...]
    required_source_ids: tuple[str, ...]
    evidence: tuple[dict, ...] = ()
    failures: tuple[EvidenceConnectorFailure, ...] = ()
    request: EvidenceFetchRequest | None = None

    @property
    def valid(self):
        return not self.failures

    def to_dict(self):
        return {
            "valid": self.valid,
            "integration_id": self.integration_id,
            "connector_contract_version": CONNECTOR_CONTRACT_VERSION,
            "required_source_ids": list(self.required_source_ids),
            "requested_source_ids": list(self.requested_source_ids),
            "request": self.request.to_dict() if self.request else None,
            "checks": {
                "auth_scopes": "pass" if not any(f.code == "unauthorized" for f in self.failures) else "fail",
                "source_scope": "pass" if not any(f.code in {"missing_source", "unknown_source"} for f in self.failures) else "fail",
                "freshness": "pass" if not any(f.code == "stale_evidence" for f in self.failures) else "fail",
                "redaction": "pass" if not any(f.code == "unredacted_evidence" for f in self.failures) else "fail",
                "shape": "pass" if not any(f.code == "invalid_shape" for f in self.failures) else "fail",
            },
            "evidence": list(self.evidence),
            "failures": [failure.to_dict() for failure in self.failures],
        }


FAILURE_ROUTES = {
    "missing_evidence": {"route": "retrieve", "retryable": True},
    "missing_source": {"route": "retrieve", "retryable": True},
    "unknown_source": {"route": "defer", "retryable": False},
    "unauthorized": {"route": "defer", "retryable": False},
    "stale_evidence": {"route": "retrieve", "retryable": True},
    "unredacted_evidence": {"route": "defer", "retryable": False},
    "invalid_shape": {"route": "defer", "retryable": False},
    "connector_unavailable": {"route": "defer", "retryable": True},
}


def _failure(code, source_id, message):
    route = FAILURE_ROUTES.get(code, {"route": "defer", "retryable": False})
    return EvidenceConnectorFailure(
        code=code,
        source_id=source_id,
        message=message,
        retryable=route["retryable"],
        route=route["route"],
    )


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
    required_auth_scopes: tuple[str, ...] = ()
    freshness_slo_hours: int | None = 24
    allowed_trust_tiers: tuple[str, ...] = ("verified", "repository_fixture")
    allowed_redaction_statuses: tuple[str, ...] = ("redacted",)
    failure_modes: tuple[str, ...] = (
        "missing_evidence",
        "missing_source",
        "unauthorized",
        "stale_evidence",
        "unredacted_evidence",
        "invalid_shape",
        "connector_unavailable",
        "unknown_source",
    )

    def to_dict(self):
        return {
            "connector_contract_version": CONNECTOR_CONTRACT_VERSION,
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
            "required_auth_scopes": list(self.required_auth_scopes),
            "freshness_slo_hours": self.freshness_slo_hours,
            "allowed_trust_tiers": list(self.allowed_trust_tiers),
            "allowed_redaction_statuses": list(self.allowed_redaction_statuses),
            "failure_modes": list(self.failure_modes),
            "contract": self.connector_contract(),
        }

    def connector_contract(self):
        return {
            "contract_id": f"{self.integration_id}.evidence.v{CONNECTOR_CONTRACT_VERSION}",
            "integration_id": self.integration_id,
            "system_type": self.system_type,
            "adapter_ids": list(self.adapter_ids),
            "operations": list(self.operations),
            "source_scope": {
                "required_source_ids": list(self.required_source_ids),
                "optional_source_ids": list(self.optional_source_ids),
                "unknown_source_behavior": "fail_closed",
            },
            "auth": {
                "mode": "read_only_scoped_service_or_user_delegated",
                "required_scopes": list(self.required_auth_scopes),
                "requires_tenant_scope": True,
                "requires_principal": True,
                "action_execution_allowed": False,
                "boundary": self.auth_boundary,
            },
            "freshness": {
                "requires_retrieved_at": True,
                "freshness_slo_hours": self.freshness_slo_hours,
                "stale_behavior": "fail_closed_route_to_retrieve_or_defer",
            },
            "redaction": {
                "allowed_redaction_statuses": list(self.allowed_redaction_statuses),
                "raw_records_allowed_in_aana": False,
                "policy": self.redaction_policy,
            },
            "trust": {
                "allowed_trust_tiers": list(self.allowed_trust_tiers),
            },
            "failure_routing": {
                code: {
                    "route": FAILURE_ROUTES.get(code, {"route": "defer"})["route"],
                    "retryable": FAILURE_ROUTES.get(code, {"retryable": False})["retryable"],
                }
                for code in self.failure_modes
            },
            "output_shape": {
                "required_fields": ["source_id", "retrieved_at", "trust_tier", "redaction_status", "text", "metadata"],
                "metadata_required_fields": ["connector_contract_version", "integration_id", "system_type", "normalized"],
            },
        }

    def fetch_request(self, *, source_ids=None, auth=None, now=None, operation=None, adapter_id=None, subject_ref=None, reason=None, metadata=None):
        return EvidenceFetchRequest(
            integration_id=self.integration_id,
            source_ids=tuple(source_ids or self.required_source_ids),
            operation=operation,
            auth=EvidenceAuthContext.from_value(auth),
            adapter_id=adapter_id,
            subject_ref=subject_ref,
            reason=reason or "AANA adapter evidence check",
            now=now,
            metadata=dict(metadata or {}),
        )

    def validate_auth_context(self, auth):
        auth_context = EvidenceAuthContext.from_value(auth)
        granted = set(auth_context.scopes or ())
        required = set(self.required_auth_scopes)
        missing = sorted(required - granted)
        failures = []
        if missing:
            failures.append(
                _failure(
                    "unauthorized",
                    None,
                    f"Missing auth scopes for {self.integration_id}: {', '.join(missing)}",
                )
            )
        if not auth_context.tenant_id:
            failures.append(_failure("unauthorized", None, f"{self.integration_id} requires tenant scoping."))
        if not auth_context.principal_id:
            failures.append(_failure("unauthorized", None, f"{self.integration_id} requires a principal."))
        return failures

    def validate_requested_sources(self, source_ids):
        known = _source_ids(self)
        failures = []
        for source_id in source_ids:
            if source_id not in known:
                failures.append(
                    _failure(
                        "unknown_source",
                        source_id,
                        f"source_id {source_id!r} is not declared for integration {self.integration_id!r}.",
                    )
                )
        return failures

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
                "connector_contract_version": CONNECTOR_CONTRACT_VERSION,
                "integration_id": self.integration_id,
                "system_type": self.system_type,
                "stub": True,
                "freshness_slo_hours": self.freshness_slo_hours,
            },
        }

    def fetch_evidence(self, *args, **kwargs):
        raise NotImplementedError(
            f"{self.integration_id} is a production evidence integration stub. "
            "Implement connector-specific authentication, retrieval, redaction, freshness checks, and audit logging."
        )

    def normalize_evidence(
        self,
        *,
        source_id,
        text,
        retrieved_at=None,
        trust_tier="verified",
        redaction_status="redacted",
        metadata=None,
        raw_record_id=None,
    ):
        return normalize_evidence_object(
            self,
            source_id=source_id,
            text=text,
            retrieved_at=retrieved_at,
            trust_tier=trust_tier,
            redaction_status=redaction_status,
            metadata=metadata,
            raw_record_id=raw_record_id,
        )


@dataclass(frozen=True)
class LiveEvidenceConnectorManifest:
    """Deployment-owned manifest for a live, read-only evidence connector."""

    connector_id: str
    endpoint_url: str
    environment: str
    owner: str
    auth_token_env: str | None = None
    approval_status: str = "pending"
    source_mode: str = "live"
    timeout_seconds: int = 10

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise EvidenceConnectorError("Live connector manifest must be an object.")
        connector_id = value.get("connector_id") or value.get("integration_id")
        endpoint_url = value.get("endpoint_url") or value.get("manifest_uri")
        environment = value.get("environment")
        owner = value.get("owner")
        if not isinstance(connector_id, str) or not connector_id.strip():
            raise EvidenceConnectorError("Live connector manifest requires connector_id.")
        if not isinstance(endpoint_url, str) or not endpoint_url.strip():
            raise EvidenceConnectorError(f"Live connector manifest for {connector_id!r} requires endpoint_url.")
        if not endpoint_url.startswith("https://"):
            raise EvidenceConnectorError(f"Live connector {connector_id!r} must use an HTTPS endpoint_url.")
        if not isinstance(environment, str) or not environment.strip():
            raise EvidenceConnectorError(f"Live connector {connector_id!r} requires environment.")
        if not isinstance(owner, str) or not owner.strip():
            raise EvidenceConnectorError(f"Live connector {connector_id!r} requires owner.")
        return cls(
            connector_id=connector_id.strip(),
            endpoint_url=endpoint_url.strip(),
            environment=environment.strip(),
            owner=owner.strip(),
            auth_token_env=value.get("auth_token_env"),
            approval_status=value.get("approval_status") or "pending",
            source_mode=value.get("source_mode") or "live",
            timeout_seconds=int(value.get("timeout_seconds") or 10),
        )

    @property
    def live_approved(self):
        return self.source_mode == "live" and self.approval_status in {"live_approved", "approved"}

    def to_dict(self):
        return {
            "connector_id": self.connector_id,
            "endpoint_url": self.endpoint_url,
            "environment": self.environment,
            "owner": self.owner,
            "auth_token_env": self.auth_token_env,
            "approval_status": self.approval_status,
            "source_mode": self.source_mode,
            "timeout_seconds": self.timeout_seconds,
            "live_approved": self.live_approved,
        }


@dataclass
class LiveHTTPJSONEvidenceConnector:
    """HTTPS JSON connector for production support evidence retrieval.

    The upstream endpoint must return a JSON object with an ``evidence`` array.
    Each evidence item is normalized through the same contract as fixtures.
    """

    stub: EvidenceIntegrationStub
    manifest: LiveEvidenceConnectorManifest
    retriever: object | None = None

    def collect(self, source_ids=None, auth_scopes=None, request=None):
        fetch_request = EvidenceFetchRequest.from_value(
            request,
            integration_id=self.stub.integration_id,
            source_ids=source_ids or self.stub.required_source_ids,
            auth=auth_scopes,
        )
        if fetch_request.integration_id != self.stub.integration_id:
            raise EvidenceConnectorError(
                f"Fetch request integration_id {fetch_request.integration_id!r} does not match connector {self.stub.integration_id!r}."
            )

        failures = []
        failures.extend(self.stub.validate_auth_context(fetch_request.auth))
        requested = list(fetch_request.source_ids or self.stub.required_source_ids)
        failures.extend(self.stub.validate_requested_sources(requested))
        if not self.manifest.live_approved:
            failures.append(
                _failure(
                    "connector_unavailable",
                    None,
                    f"Live connector {self.stub.integration_id!r} is not live-approved.",
                )
            )
        if failures:
            return EvidenceConnectorResult(
                integration_id=self.stub.integration_id,
                requested_source_ids=tuple(requested),
                required_source_ids=tuple(self.stub.required_source_ids),
                failures=tuple(failures),
                request=fetch_request,
            ).to_dict()

        try:
            payload = self._retrieve(fetch_request)
            evidence_items = self._normalize_payload(payload, requested)
        except EvidenceConnectorError as exc:
            return EvidenceConnectorResult(
                integration_id=self.stub.integration_id,
                requested_source_ids=tuple(requested),
                required_source_ids=tuple(self.stub.required_source_ids),
                failures=(_failure("connector_unavailable", None, str(exc)),),
                request=fetch_request,
            ).to_dict()

        return EvidenceConnectorResult(
            integration_id=self.stub.integration_id,
            requested_source_ids=tuple(requested),
            required_source_ids=tuple(self.stub.required_source_ids),
            evidence=tuple(evidence_items),
            request=fetch_request,
        ).to_dict()

    def fetch_evidence(self, source_ids=None, auth_scopes=None, request=None):
        report = self.collect(source_ids=source_ids, auth_scopes=auth_scopes, request=request)
        if not report["valid"]:
            messages = "; ".join(f"{failure['code']}: {failure['message']}" for failure in report["failures"])
            raise EvidenceConnectorError(messages)
        return report["evidence"]

    def _retrieve(self, fetch_request):
        if self.retriever is not None:
            return self.retriever(fetch_request, self.manifest)

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.manifest.auth_token_env:
            token = os.environ.get(self.manifest.auth_token_env)
            if not token:
                raise EvidenceConnectorError(
                    f"Missing auth token environment variable {self.manifest.auth_token_env!r} for {self.stub.integration_id}."
                )
            headers["Authorization"] = f"Bearer {token}"
        body = json.dumps(fetch_request.to_dict()).encode("utf-8")
        request = urllib.request.Request(self.manifest.endpoint_url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.manifest.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise EvidenceConnectorError(f"Live connector request failed for {self.stub.integration_id}: {exc}") from exc

    def _normalize_payload(self, payload, requested):
        if not isinstance(payload, dict) or not isinstance(payload.get("evidence"), list):
            raise EvidenceConnectorError("Live connector response must be an object with an evidence array.")
        evidence_by_source = {}
        for item in payload["evidence"]:
            if not isinstance(item, dict):
                raise EvidenceConnectorError("Live connector evidence items must be objects.")
            source_id = item.get("source_id")
            evidence_by_source[source_id] = self.stub.normalize_evidence(
                source_id=source_id,
                text=item.get("text"),
                retrieved_at=item.get("retrieved_at"),
                trust_tier=item.get("trust_tier", "verified"),
                redaction_status=item.get("redaction_status", "redacted"),
                metadata={
                    **dict(item.get("metadata") or {}),
                    "source_mode": "live",
                    "connector_environment": self.manifest.environment,
                    "connector_owner": self.manifest.owner,
                    "connector_approval_status": self.manifest.approval_status,
                },
                raw_record_id=item.get("record_id") or item.get("raw_record_id"),
            )
        missing = [source_id for source_id in requested if source_id not in evidence_by_source]
        if missing:
            raise EvidenceConnectorError(f"Live connector response missing requested source(s): {', '.join(missing)}.")
        return [evidence_by_source[source_id] for source_id in requested]


INTEGRATION_STUBS = (
    EvidenceIntegrationStub(
        integration_id="crm_customer_account",
        title="CRM Customer Account Record Evidence",
        system_type="crm_account",
        adapter_ids=("support_reply", "crm_support_reply"),
        required_source_ids=("crm-record", "account-verification-status"),
        optional_source_ids=("crm", "account-health"),
        operations=("read_customer_account_record", "read_account_verification_status"),
        auth_boundary="Use support-scoped read credentials for the current customer account only; account mutation remains outside AANA.",
        redaction_policy="Return verified account facts and verification state without raw CRM notes, payment details, authentication secrets, or unrelated account history.",
        required_auth_scopes=("crm.account.read", "support.account_verification.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="order_history",
        title="Order History Evidence",
        system_type="order_history",
        adapter_ids=("support_reply", "crm_support_reply"),
        required_source_ids=("order-system",),
        optional_source_ids=("invoice",),
        operations=("read_order_history", "read_order_status", "read_order_eligibility_context"),
        auth_boundary="Use order-system read credentials scoped to the current customer and case; refunds, credits, shipments, or account actions require separate approval.",
        redaction_policy="Return order status, fulfillment state, and eligibility summaries without full payment instruments, addresses, or unrelated order history.",
        required_auth_scopes=("orders.read",),
    ),
    EvidenceIntegrationStub(
        integration_id="refund_policy",
        title="Refund Policy Evidence",
        system_type="support_policy",
        adapter_ids=("support_reply", "crm_support_reply", "ticket_update_checker", "invoice_billing_reply"),
        required_source_ids=("refund-policy",),
        optional_source_ids=("support-policy", "billing-policy"),
        operations=("read_refund_policy", "read_refund_eligibility_rules"),
        auth_boundary="Use policy-library read credentials; refund execution, credits, and concessions remain outside the evidence connector.",
        redaction_policy="Return policy version, eligibility criteria, approval boundaries, and escalation rules without internal deliberation notes.",
        required_auth_scopes=("support.refund_policy.read",),
    ),
    EvidenceIntegrationStub(
        integration_id="internal_notes_classifier",
        title="Agent-Only and Internal Notes Classifier Evidence",
        system_type="privacy_classifier",
        adapter_ids=("support_reply", "crm_support_reply", "ticket_update_checker", "invoice_billing_reply"),
        required_source_ids=("internal-notes-classification",),
        optional_source_ids=("data-classification",),
        operations=("classify_internal_notes", "classify_agent_only_fields", "classify_customer_visible_text"),
        auth_boundary="Use read-only classifier output; never expose raw internal notes to prompts or customer-visible drafts.",
        redaction_policy="Return classification labels and redaction decisions only; raw internal notes, risk tags, and employee comments stay in source systems.",
        required_auth_scopes=("support.internal_notes.classify",),
    ),
    EvidenceIntegrationStub(
        integration_id="support_ticket_history",
        title="Support Ticket History Evidence",
        system_type="ticketing",
        adapter_ids=("support_reply", "crm_support_reply", "ticket_update_checker"),
        required_source_ids=("ticket-history", "support-policy"),
        optional_source_ids=("sprint-status", "incident-timeline", "status-page-policy"),
        operations=("read_support_ticket_history", "read_customer_visible_updates", "read_ticket_policy_context"),
        auth_boundary="Use ticket-scoped read credentials and preserve internal/customer visibility boundaries; posting updates requires separate authorization.",
        redaction_policy="Return ticket status and customer-visible history summaries without internal-only notes, secrets, private account data, or employee blame.",
        required_auth_scopes=("ticket.history.read", "support.policy.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="email_recipient_verification",
        title="Email Recipient Verification Evidence",
        system_type="directory_email",
        adapter_ids=("email_send_guardrail",),
        required_source_ids=("recipient-metadata", "user-approval"),
        optional_source_ids=("draft-email",),
        operations=("read_recipient_metadata", "verify_recipient_identity", "read_send_approval"),
        auth_boundary="Use directory and approval read credentials; sending email remains outside the evidence connector.",
        redaction_policy="Return recipient identity, domain, alias, distribution-list, and approval summaries without raw mailbox content.",
        required_auth_scopes=("directory.recipient.read", "approval.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="attachment_metadata",
        title="Attachment Metadata Evidence",
        system_type="attachment_manifest",
        adapter_ids=("email_send_guardrail",),
        required_source_ids=("attachment-metadata",),
        optional_source_ids=("draft-email", "data-classification"),
        operations=("read_attachment_manifest", "read_attachment_classification", "read_attachment_approval"),
        auth_boundary="Use attachment metadata and classification read credentials only; file transfer or email send requires separate approval.",
        redaction_policy="Return filename class, MIME type, size, classification, approval, and DLP summary without raw attachment contents.",
        required_auth_scopes=("email.attachment_metadata.read", "data.classification.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="account_verification_status",
        title="Account Verification Status Evidence",
        system_type="identity_verification",
        adapter_ids=("support_reply", "crm_support_reply", "invoice_billing_reply"),
        required_source_ids=("account-verification-status",),
        optional_source_ids=("crm-record",),
        operations=("read_account_verification_status", "read_identity_check_summary"),
        auth_boundary="Use identity-verification read credentials scoped to the current case; authentication or account changes require separate systems.",
        redaction_policy="Return verification status and allowed support action summary without authentication secrets, documents, or identity artifacts.",
        required_auth_scopes=("support.account_verification.read",),
    ),
    EvidenceIntegrationStub(
        integration_id="billing_payment_redaction",
        title="Billing and Payment Redaction Metadata Evidence",
        system_type="billing_payment_privacy",
        adapter_ids=("invoice_billing_reply", "support_reply", "crm_support_reply"),
        required_source_ids=("billing-redaction-metadata", "payment-metadata"),
        optional_source_ids=("invoice", "billing-policy"),
        operations=("read_billing_redaction_metadata", "read_payment_visibility_rules", "read_payment_state_summary"),
        auth_boundary="Use payment metadata read credentials for redaction and visibility only; payment collection, refund, credit, or billing mutation remains outside AANA.",
        redaction_policy="Return redaction labels, visibility decisions, payment state, and secure-portal routing without card, bank, token, CVV, raw processor, or tax identifier data.",
        required_auth_scopes=("billing.redaction.read", "payment.metadata.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="support_policy_registry",
        title="Support Policy Registry Evidence",
        system_type="support_policy_registry",
        adapter_ids=SUPPORT_ADAPTER_IDS,
        required_source_ids=("support-policy-registry", "support-policy"),
        optional_source_ids=("refund-policy", "billing-policy"),
        operations=("read_support_policy_registry", "read_customer_visible_policy", "read_human_review_routing"),
        auth_boundary="Use read-only support policy registry credentials; policy overrides, approvals, and customer actions require domain-owner workflows.",
        redaction_policy="Return active policy versions, allowed customer-visible claims, escalation routes, and human-review requirements without internal deliberation notes.",
        required_auth_scopes=("support.policy_registry.read", "support.policy.read"),
    ),
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
        required_auth_scopes=("crm.account.read", "support.policy.read", "orders.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="ticketing",
        title="Ticketing and Sprint Evidence",
        system_type="ticketing",
        adapter_ids=("ticket_update_checker", "incident_response_update", "product_requirements_checker"),
        required_source_ids=("ticket-history", "sprint-status", "support-policy"),
        optional_source_ids=("incident-timeline", "status-page-policy", "on-call-notes", "roadmap", "prd", "policy-checklist"),
        operations=("read_ticket_history", "read_sprint_status", "read_customer_visible_policy", "read_incident_timeline", "read_on_call_notes"),
        auth_boundary="Use project-scoped credentials and preserve customer/internal visibility boundaries.",
        redaction_policy="Return status summaries; do not expose internal-only comments in customer-visible evidence.",
        required_auth_scopes=("ticket.history.read", "sprint.status.read", "support.policy.read"),
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
        required_auth_scopes=("email.draft.read", "directory.recipient.read", "approval.read"),
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
        required_auth_scopes=("calendar.freebusy.read", "calendar.attendees.read", "user_instruction.read"),
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
        required_auth_scopes=("iam.request.read", "iam.role_catalog.read", "iam.approval.read"),
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
        required_auth_scopes=("repo.diff.read", "ci.logs.read", "ci.status.read"),
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
        required_auth_scopes=("deployment.manifest.read", "ci.result.read", "release_notes.read"),
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
        required_auth_scopes=("billing.invoice.read", "billing.policy.read", "payment.metadata.read"),
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
        required_auth_scopes=("data.classification.read", "iam.access_grants.read", "data.export_request.read"),
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
        required_auth_scopes=("filesystem.metadata.read", "filesystem.diff_preview.read", "approval.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="browser_cart_quote",
        title="Browser Cart and Quote Evidence",
        system_type="browser_checkout",
        adapter_ids=("booking_purchase_guardrail",),
        required_source_ids=("live-quote", "cart", "payment-policy"),
        optional_source_ids=("user-approval",),
        operations=("read_live_quote", "read_cart_summary", "read_payment_policy"),
        auth_boundary="Use local browser read-only extraction or synthetic fixtures; never submit payment or modify the cart from the evidence connector.",
        redaction_policy="Return vendor, total price, refundability, fees, and payment-risk summaries without card, address, or account secrets.",
        required_auth_scopes=("browser.quote.read", "browser.cart.read", "payment.policy.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="citation_source_registry",
        title="Citation and Source Registry Evidence",
        system_type="research_sources",
        adapter_ids=("research_answer_grounding", "publication_check"),
        required_source_ids=("retrieved-documents", "citation-index", "source-registry"),
        optional_source_ids=("publication-source-list", "publication-approval-policy", "evidence-limits"),
        operations=("read_retrieved_documents", "read_citation_index", "read_source_registry"),
        auth_boundary="Use read-only source registry and retrieved-document access scoped to the current answer or draft.",
        redaction_policy="Return source identifiers, approved citation mappings, and evidence limits; do not include private source excerpts unless approved and redacted.",
        required_auth_scopes=("research.documents.read", "research.citation_index.read", "research.source_registry.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="local_approval",
        title="Local User Approval State Evidence",
        system_type="local_approval",
        adapter_ids=(
            "email_send_guardrail",
            "calendar_scheduling",
            "file_operation_guardrail",
            "booking_purchase_guardrail",
            "publication_check",
            "meeting_summary_checker",
        ),
        required_source_ids=("user-approval",),
        optional_source_ids=("user-confirmation", "user-instruction", "publication-approval-policy", "meeting-metadata"),
        operations=("read_local_approval_state", "read_user_confirmation", "read_user_instruction"),
        auth_boundary="Use local approval state scoped to the proposed action; approval evidence may be read but action execution requires a separate explicit confirmation path.",
        redaction_policy="Return approval scope, timestamp, action class, and confirmation state without private prompt history or unrelated local content.",
        required_auth_scopes=("approval.read",),
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
        required_auth_scopes=("security.advisory.read", "scanner.output.read", "release_notes.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="civic_program_rules",
        title="Government Program Rules and Application Evidence",
        system_type="civic_program",
        adapter_ids=("grant_application_review", "casework_response_checker", "insurance_claim_triage"),
        required_source_ids=("program-rules", "submitted-docs", "rubric"),
        optional_source_ids=("grant-rubric", "policy-docs", "triage-policy"),
        operations=("read_program_rules", "read_submitted_documents", "read_scoring_rubric"),
        auth_boundary="Use program-scoped read credentials; eligibility, award, and benefits decisions require separate human adjudication.",
        redaction_policy="Return rule, checklist, and rubric summaries with applicant and constituent private data minimized.",
        required_auth_scopes=("civic.program_rules.read", "civic.submitted_docs.read", "civic.rubric.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="civic_vendor_profiles",
        title="Civic Procurement Vendor Evidence",
        system_type="civic_procurement",
        adapter_ids=("procurement_vendor_risk",),
        required_source_ids=("quote", "vendor-profile", "dpa-security-docs"),
        optional_source_ids=(),
        operations=("read_quote", "read_vendor_profile", "read_security_docs"),
        auth_boundary="Use procurement read credentials; purchase, contract, onboarding, and payment execution stay outside the evidence connector.",
        redaction_policy="Return vendor, quote, DPA, and security-review summaries without banking, tax, or confidential contract raw fields.",
        required_auth_scopes=("procurement.quote.read", "procurement.vendor.read", "procurement.security_docs.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="public_law_policy_sources",
        title="Public Law and Policy Source Evidence",
        system_type="source_law",
        adapter_ids=("legal_safety_router", "policy_memo_grounding", "public_records_privacy_redaction", "foia_public_records_response_checker"),
        required_source_ids=("jurisdiction", "source-law", "policy-limits"),
        optional_source_ids=("source-registry",),
        operations=("read_jurisdiction", "read_source_law", "read_policy_limits"),
        auth_boundary="Use read-only official-source and policy-library access scoped to the jurisdiction and program.",
        redaction_policy="Prefer public source-law excerpts and redacted policy summaries; avoid storing legal work product in AANA payloads.",
        required_auth_scopes=("law.jurisdiction.read", "law.source.read", "policy.limits.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="redaction_classification_registry",
        title="Redaction and Classification Registry Evidence",
        system_type="records_redaction",
        adapter_ids=("public_records_privacy_redaction", "foia_public_records_response_checker", "data_export_guardrail"),
        required_source_ids=("data-classification", "export-request", "access-grants"),
        optional_source_ids=("source-law",),
        operations=("read_data_classification", "read_export_request", "read_access_grants", "read_redaction_registry"),
        auth_boundary="Use read-only classification and redaction policy access; release execution and redaction approval require separate authorization.",
        redaction_policy="Return classification, redaction, exemption, scope, and retention summaries without raw protected records.",
        required_auth_scopes=("records.classification.read", "records.request.read", "records.access_grants.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="civic_case_history",
        title="Civic Case and Ticket History Evidence",
        system_type="case_management",
        adapter_ids=("casework_response_checker", "ticket_update_checker"),
        required_source_ids=("ticket-history", "support-policy", "program-rules"),
        optional_source_ids=("claim-file", "submitted-docs"),
        operations=("read_case_history", "read_program_status", "read_support_policy"),
        auth_boundary="Use case-scoped read credentials with consent and need-to-know boundaries; case actions require separate caseworker approval.",
        redaction_policy="Return verified case facts, consent status, and policy limits without internal notes or raw private case records.",
        required_auth_scopes=("case.history.read", "case.policy.read", "civic.program_rules.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="benefits_claims",
        title="Benefits and Insurance Claim Evidence",
        system_type="benefits_triage",
        adapter_ids=("insurance_claim_triage", "casework_response_checker"),
        required_source_ids=("policy-docs", "claim-file", "triage-policy"),
        optional_source_ids=("jurisdiction", "program-rules"),
        operations=("read_policy_docs", "read_claim_file", "read_triage_policy"),
        auth_boundary="Use claim-scoped read credentials; coverage, eligibility, payment, denial, or appeal decisions require human adjudication.",
        redaction_policy="Return coverage, missing-document, jurisdiction, and escalation summaries without raw medical, financial, or claim records.",
        required_auth_scopes=("benefits.policy.read", "benefits.claim.read", "benefits.triage_policy.read"),
    ),
    EvidenceIntegrationStub(
        integration_id="civic_source_registry",
        title="Civic Citation and Source Registry Evidence",
        system_type="civic_sources",
        adapter_ids=("policy_memo_grounding", "research_answer_grounding", "publication_check"),
        required_source_ids=("retrieved-documents", "citation-index", "source-registry"),
        optional_source_ids=("source-law", "jurisdiction", "publication-source-list"),
        operations=("read_retrieved_documents", "read_citation_index", "read_source_registry"),
        auth_boundary="Use source-registry read credentials scoped to the memo, publication, jurisdiction, and approved source set.",
        redaction_policy="Return source identifiers, approved citation mappings, public-source status, and limits without private source excerpts.",
        required_auth_scopes=("civic.documents.read", "civic.citation_index.read", "civic.source_registry.read"),
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


def _coerce_utc(value):
    if value is None:
        return datetime.datetime.now(datetime.timezone.utc)
    if isinstance(value, datetime.datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise EvidenceConnectorError(f"Invalid retrieved_at timestamp: {value!r}.") from exc
    else:
        raise EvidenceConnectorError("retrieved_at must be an ISO timestamp or datetime.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _iso_utc(value):
    return _coerce_utc(value).isoformat().replace("+00:00", "Z")


def _source_ids(stub):
    return set(stub.required_source_ids) | set(stub.optional_source_ids)


def _connector_families(stub):
    adapter_ids = set(stub.adapter_ids)
    families = set()
    if stub.integration_id in SUPPORT_CONNECTOR_CONTRACT_IDS or adapter_ids & set(SUPPORT_ADAPTER_IDS):
        families.add("support")
    if adapter_ids & {
        "crm_support_reply",
        "support_reply",
        "customer_success_renewal",
        "sales_proposal_checker",
        "ticket_update_checker",
        "incident_response_update",
        "data_export_guardrail",
        "access_permission_change",
        "code_change_review",
        "deployment_readiness",
        "invoice_billing_reply",
    }:
        families.add("enterprise")
    if adapter_ids & {
        "email_send_guardrail",
        "calendar_scheduling",
        "file_operation_guardrail",
        "booking_purchase_guardrail",
        "research_answer_grounding",
        "publication_check",
        "meeting_summary_checker",
    }:
        families.add("personal_productivity")
    if adapter_ids & {
        "casework_response_checker",
        "foia_public_records_response_checker",
        "grant_application_review",
        "insurance_claim_triage",
        "policy_memo_grounding",
        "procurement_vendor_risk",
        "public_records_privacy_redaction",
        "legal_safety_router",
    }:
        families.add("government_civic")
    return sorted(families or {"cross_family"})


def _live_connector_manifests(external_evidence):
    manifests = external_evidence.get("connector_manifests", []) if isinstance(external_evidence, dict) else []
    if not isinstance(manifests, list):
        return {}
    parsed = {}
    for item in manifests:
        if not isinstance(item, dict):
            continue
        connector_id = item.get("connector_id") or item.get("integration_id")
        if not isinstance(connector_id, str) or not connector_id.strip():
            continue
        try:
            parsed[connector_id] = LiveEvidenceConnectorManifest.from_value(item)
        except EvidenceConnectorError:
            parsed[connector_id] = {
                "connector_id": connector_id,
                "live_approved": False,
                "invalid_manifest": True,
            }
    return parsed


def _manifest_connector_ids(external_evidence):
    return set(_live_connector_manifests(external_evidence))


def _live_approved_connector_ids(external_evidence):
    approved = set()
    for connector_id, manifest in _live_connector_manifests(external_evidence).items():
        if isinstance(manifest, LiveEvidenceConnectorManifest) and manifest.live_approved:
            approved.add(connector_id)
    return approved


def _approved_fixture_connector_ids(fixtures):
    if not isinstance(fixtures, dict) or fixtures.get("production_fixtures_approved") is not True:
        return set()
    connectors = fixtures.get("connectors", {})
    if not isinstance(connectors, dict):
        return set()
    approved = set()
    for connector_id, connector in connectors.items():
        if not isinstance(connector, dict):
            continue
        if connector.get("production_fixture_approved") is True or connector.get("fixture_scope") == "approved_production_fixture":
            approved.add(connector_id)
    return approved


def support_evidence_boundary_report(registry=None, external_evidence=None, fixtures=None):
    """Report whether support production evidence exists as live manifests or approved fixtures."""

    registry_sources = source_ids_from_registry(registry or {}) if registry is not None else set()
    live_manifests = _live_connector_manifests(external_evidence)
    live_connector_ids = set(live_manifests)
    live_approved_connector_ids = _live_approved_connector_ids(external_evidence)
    approved_fixture_ids = _approved_fixture_connector_ids(fixtures)
    connector_reports = []
    for connector_id in SUPPORT_CONNECTOR_CONTRACT_IDS:
        stub = find_integration_stub(connector_id)
        required_sources = set(stub.required_source_ids)
        missing_registry_sources = sorted(required_sources - registry_sources) if registry is not None else []
        has_live_connector = connector_id in live_connector_ids
        has_live_approved_connector = connector_id in live_approved_connector_ids
        has_approved_fixture = connector_id in approved_fixture_ids
        connector_reports.append(
            {
                "connector_id": connector_id,
                "title": stub.title,
                "adapter_ids": list(stub.adapter_ids),
                "required_source_ids": list(stub.required_source_ids),
                "missing_registry_source_ids": missing_registry_sources,
                "live_connector_manifest": has_live_connector,
                "live_connector_approved": has_live_approved_connector,
                "approved_production_fixture": has_approved_fixture,
                "source_mode": "live" if has_live_approved_connector else "approved_fixture" if has_approved_fixture else "repository_fixture",
                "production_evidence_available": has_live_approved_connector or has_approved_fixture,
                "status": "pass" if not missing_registry_sources and (has_live_approved_connector or has_approved_fixture) else "fail",
            }
        )
    missing_evidence = [
        item["connector_id"]
        for item in connector_reports
        if not item["production_evidence_available"]
    ]
    missing_registry = {
        item["connector_id"]: item["missing_registry_source_ids"]
        for item in connector_reports
        if item["missing_registry_source_ids"]
    }
    valid = not missing_evidence and not missing_registry
    return {
        "support_evidence_boundary_version": CONNECTOR_CONTRACT_VERSION,
        "valid": valid,
        "production_evidence_ready": valid,
        "production_claim_allowed": valid,
        "support_adapter_ids": list(SUPPORT_ADAPTER_IDS),
        "required_connectors": list(SUPPORT_CONNECTOR_CONTRACT_IDS),
        "summary": {
            "required_connectors": len(SUPPORT_CONNECTOR_CONTRACT_IDS),
            "live_connector_manifests": len(live_connector_ids & set(SUPPORT_CONNECTOR_CONTRACT_IDS)),
            "live_approved_connector_manifests": len(live_approved_connector_ids & set(SUPPORT_CONNECTOR_CONTRACT_IDS)),
            "approved_production_fixtures": len(approved_fixture_ids & set(SUPPORT_CONNECTOR_CONTRACT_IDS)),
            "missing_evidence_connectors": missing_evidence,
            "missing_registry_sources": missing_registry,
        },
        "production_positioning": (
            "Support guardrails are not production-ready until every required support evidence connector "
            "has either a live production connector manifest or an approved production fixture, plus domain "
            "owner signoff, audit retention, observability, and human review paths."
        ),
        "connectors": connector_reports,
    }


def connector_marketplace_card(stub):
    contract = stub.connector_contract()
    return {
        "connector_marketplace_version": CONNECTOR_MARKETPLACE_VERSION,
        "connector_id": stub.integration_id,
        "title": stub.title,
        "system_type": stub.system_type,
        "families": _connector_families(stub),
        "adapter_ids": list(stub.adapter_ids),
        "source_ids": {
            "required": list(stub.required_source_ids),
            "optional": list(stub.optional_source_ids),
        },
        "auth_boundary": {
            "description": stub.auth_boundary,
            "required_scopes": list(stub.required_auth_scopes),
            "action_execution_allowed": False,
        },
        "freshness_slo": {
            "description": stub.freshness_slo,
            "hours": stub.freshness_slo_hours,
            "requires_retrieved_at": True,
        },
        "redaction_behavior": {
            "policy": stub.redaction_policy,
            "allowed_statuses": list(stub.allowed_redaction_statuses),
            "raw_records_allowed_in_aana": False,
        },
        "failure_modes": {
            code: contract["failure_routing"][code]
            for code in stub.failure_modes
            if code in contract["failure_routing"]
        },
        "evidence_normalization": contract["output_shape"],
    }


def connector_marketplace(integration_ids=None):
    ids = integration_ids or [stub.integration_id for stub in all_integration_stubs()]
    connectors = [connector_marketplace_card(find_integration_stub(integration_id)) for integration_id in ids]
    families = sorted({family for connector in connectors for family in connector["families"]})
    return {
        "connector_marketplace_version": CONNECTOR_MARKETPLACE_VERSION,
        "connector_count": len(connectors),
        "families": families,
        "filters": {
            "families": families,
            "system_types": sorted({connector["system_type"] for connector in connectors}),
        },
        "connectors": connectors,
    }


def normalize_evidence_object(
    stub_or_integration_id,
    *,
    source_id,
    text,
    retrieved_at=None,
    trust_tier="verified",
    redaction_status="redacted",
    metadata=None,
    raw_record_id=None,
):
    """Normalize connector output into the structured evidence object contract."""

    stub = find_integration_stub(stub_or_integration_id) if isinstance(stub_or_integration_id, str) else stub_or_integration_id
    if not isinstance(stub, EvidenceIntegrationStub):
        raise EvidenceConnectorError("stub_or_integration_id must be an EvidenceIntegrationStub or known integration id.")
    if source_id not in _source_ids(stub):
        raise EvidenceConnectorError(f"Unknown source_id {source_id!r} for integration {stub.integration_id!r}.")
    if not isinstance(text, str) or not text.strip():
        raise EvidenceConnectorError(f"Evidence text for source_id {source_id!r} must be a non-empty string.")
    if trust_tier not in stub.allowed_trust_tiers:
        raise EvidenceConnectorError(
            f"trust_tier {trust_tier!r} is not allowed for integration {stub.integration_id!r}."
        )
    if redaction_status not in stub.allowed_redaction_statuses:
        raise EvidenceConnectorError(
            f"redaction_status {redaction_status!r} is not allowed for integration {stub.integration_id!r}."
        )

    normalized_metadata = dict(metadata or {})
    normalized_metadata.update(
        {
            "connector_contract_version": CONNECTOR_CONTRACT_VERSION,
            "integration_id": stub.integration_id,
            "system_type": stub.system_type,
            "normalized": True,
            "freshness_slo_hours": stub.freshness_slo_hours,
        }
    )
    if raw_record_id:
        normalized_metadata["raw_record_id"] = raw_record_id

    return {
        "source_id": source_id,
        "retrieved_at": _iso_utc(retrieved_at),
        "trust_tier": trust_tier,
        "redaction_status": redaction_status,
        "text": text.strip(),
        "metadata": normalized_metadata,
    }


def _fixture_records(fixture, integration_id):
    connectors = fixture.get("connectors", {}) if isinstance(fixture, dict) else {}
    connector = connectors.get(integration_id, {}) if isinstance(connectors, dict) else {}
    records = connector.get("records", {}) if isinstance(connector, dict) else {}
    return connector if isinstance(connector, dict) else {}, records if isinstance(records, dict) else {}


def load_mock_connector_fixtures(path=DEFAULT_MOCK_FIXTURES_PATH):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        fixture = json.load(handle)
    if not isinstance(fixture, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return fixture


def live_support_connector_manifests(external_evidence):
    """Return parsed support live connector manifests keyed by connector ID."""

    manifests = _live_connector_manifests(external_evidence)
    return {
        connector_id: manifest
        for connector_id, manifest in manifests.items()
        if connector_id in SUPPORT_CONNECTOR_CONTRACT_IDS and isinstance(manifest, LiveEvidenceConnectorManifest)
    }


def build_live_support_connectors(external_evidence, retrievers=None):
    """Build live HTTPS JSON connectors for the support product line.

    ``retrievers`` is an optional test hook mapping connector_id to a callable
    with ``(fetch_request, manifest) -> {"evidence": [...]}``.
    """

    retrievers = retrievers or {}
    connectors = {}
    for connector_id, manifest in live_support_connector_manifests(external_evidence).items():
        connectors[connector_id] = LiveHTTPJSONEvidenceConnector(
            stub=find_integration_stub(connector_id),
            manifest=manifest,
            retriever=retrievers.get(connector_id),
        )
    return connectors


def run_live_support_connector(integration_id, external_evidence, auth_scopes=None, now=None, source_ids=None, request=None, retriever=None):
    manifests = live_support_connector_manifests(external_evidence)
    manifest = manifests.get(integration_id)
    if manifest is None:
        raise EvidenceConnectorError(f"No live support connector manifest found for {integration_id!r}.")
    stub = find_integration_stub(integration_id)
    connector = LiveHTTPJSONEvidenceConnector(stub=stub, manifest=manifest, retriever=retriever)
    if request is None:
        request = stub.fetch_request(source_ids=source_ids, auth=auth_scopes, now=now)
    return connector.collect(request=request)


@dataclass
class MockEvidenceConnector:
    """Fixture-backed connector that enforces the production evidence contract."""

    stub: EvidenceIntegrationStub
    fixture: dict
    now: datetime.datetime | str | None = None

    def _now(self):
        return _coerce_utc(self.now)

    def check_auth(self, auth):
        failures = self.stub.validate_auth_context(auth)
        if failures:
            messages = "; ".join(failure.message for failure in failures)
            raise EvidenceConnectorError(f"unauthorized: {messages}")

    def collect(self, source_ids=None, auth_scopes=None, request=None):
        fetch_request = request
        explicit_request = request is not None
        if fetch_request is None:
            fetch_request = self.stub.fetch_request(
                source_ids=source_ids or self.stub.required_source_ids,
                auth=auth_scopes,
                now=self.now,
            )
        else:
            fetch_request = EvidenceFetchRequest.from_value(fetch_request, integration_id=self.stub.integration_id)
            if fetch_request.integration_id != self.stub.integration_id:
                raise EvidenceConnectorError(
                    f"Fetch request integration_id {fetch_request.integration_id!r} does not match connector {self.stub.integration_id!r}."
                )
        connector, records = _fixture_records(self.fixture, self.stub.integration_id)
        failures = []
        evidence_items = []

        if not connector:
            return EvidenceConnectorResult(
                integration_id=self.stub.integration_id,
                requested_source_ids=tuple(fetch_request.source_ids or self.stub.required_source_ids),
                required_source_ids=tuple(self.stub.required_source_ids),
                failures=(
                    _failure(
                        "connector_unavailable",
                        None,
                        f"Mock fixture is missing connector {self.stub.integration_id!r}.",
                    ),
                ),
                request=fetch_request,
            ).to_dict()

        try:
            auth_context = fetch_request.auth
            if not explicit_request and not auth_context.scopes and auth_scopes is None:
                auth_context = EvidenceAuthContext.from_value(connector.get("auth_scopes", []))
                fetch_request = replace(fetch_request, auth=auth_context)
            self.check_auth(auth_context)
        except EvidenceConnectorError as exc:
            return EvidenceConnectorResult(
                integration_id=self.stub.integration_id,
                requested_source_ids=tuple(fetch_request.source_ids or self.stub.required_source_ids),
                required_source_ids=tuple(self.stub.required_source_ids),
                failures=(_failure("unauthorized", None, str(exc)),),
                request=fetch_request,
            ).to_dict()

        requested = list(fetch_request.source_ids or self.stub.required_source_ids)
        failures.extend(self.stub.validate_requested_sources(requested))
        for source_id in requested:
            if any(failure.source_id == source_id and failure.code == "unknown_source" for failure in failures):
                continue
            if source_id not in records:
                failures.append(
                    _failure(
                        "missing_source",
                        source_id=source_id,
                        message=f"Mock fixture has no record for source_id {source_id!r}.",
                    )
                )
                continue
            record = records[source_id]
            if not isinstance(record, dict):
                failures.append(
                    _failure("invalid_shape", source_id, "Mock evidence record must be an object.")
                )
                continue
            if not record.get("retrieved_at"):
                failures.append(
                    _failure("invalid_shape", source_id, "Mock evidence record must include retrieved_at.")
                )
                continue
            try:
                retrieved_at = _coerce_utc(record.get("retrieved_at"))
                if self.stub.freshness_slo_hours is not None:
                    max_age = datetime.timedelta(hours=self.stub.freshness_slo_hours)
                    request_now = _coerce_utc(fetch_request.now) if fetch_request.now is not None else self._now()
                    if request_now - retrieved_at > max_age:
                        failures.append(
                            _failure(
                                "stale_evidence",
                                source_id,
                                f"Evidence is older than freshness_slo_hours={self.stub.freshness_slo_hours}.",
                            )
                        )
                        continue
                fixture_scope = connector.get("fixture_scope") or (
                    "approved_production_fixture"
                    if connector.get("production_fixture_approved") is True and self.fixture.get("production_fixtures_approved") is True
                    else "repository_fixture"
                )
                evidence_items.append(
                    self.stub.normalize_evidence(
                        source_id=source_id,
                        text=record.get("text"),
                        retrieved_at=retrieved_at,
                        trust_tier=record.get("trust_tier", "verified"),
                        redaction_status=record.get("redaction_status", "redacted"),
                        metadata={
                            **dict(record.get("metadata", {})),
                            "source_mode": fixture_scope,
                            "fixture_approved": fixture_scope == "approved_production_fixture",
                        },
                        raw_record_id=record.get("record_id"),
                    )
                )
            except EvidenceConnectorError as exc:
                code = "unredacted_evidence" if record.get("redaction_status") not in self.stub.allowed_redaction_statuses else "invalid_shape"
                failures.append(_failure(code, source_id, str(exc)))

        return EvidenceConnectorResult(
            integration_id=self.stub.integration_id,
            requested_source_ids=tuple(requested),
            required_source_ids=tuple(self.stub.required_source_ids),
            evidence=tuple(evidence_items),
            failures=tuple(failures),
            request=fetch_request,
        ).to_dict()

    def fetch_evidence(self, source_ids=None, auth_scopes=None):
        report = self.collect(source_ids=source_ids, auth_scopes=auth_scopes)
        if not report["valid"]:
            messages = "; ".join(f"{failure['code']}: {failure['message']}" for failure in report["failures"])
            raise EvidenceConnectorError(messages)
        return report["evidence"]


def run_mock_connector(integration_id, fixtures=None, auth_scopes=None, now=None, source_ids=None, request=None):
    fixture = fixtures or load_mock_connector_fixtures()
    stub = find_integration_stub(integration_id)
    connector = MockEvidenceConnector(stub=stub, fixture=fixture, now=now)
    return connector.collect(source_ids=source_ids, auth_scopes=auth_scopes, request=request)


def mock_connector_matrix(fixtures=None, integration_ids=None, now=None):
    fixture = fixtures or load_mock_connector_fixtures()
    connector_ids = integration_ids or sorted((fixture.get("connectors") or {}).keys())
    reports = [run_mock_connector(integration_id, fixtures=fixture, now=now) for integration_id in connector_ids]
    return {
        "connector_contract_version": CONNECTOR_CONTRACT_VERSION,
        "valid": all(report["valid"] for report in reports),
        "connector_count": len(reports),
        "reports": reports,
    }


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
