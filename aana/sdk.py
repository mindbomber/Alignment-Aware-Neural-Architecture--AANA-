"""Application integration SDK for AANA clients.

This module gives app developers small helpers for building Agent Event and
Workflow Contract payloads without hand-assembling JSON. It can call either the
local in-process Python runtime or a running AANA HTTP bridge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import urllib.error
import urllib.request
from urllib.parse import urlencode

from eval_pipeline import agent_api, agent_contract, workflow_contract


class AANAClientError(RuntimeError):
    """Raised when a bridge request fails or a helper receives invalid input."""


FAMILY_ADAPTER_ALIASES = {
    "support": {
        "draft": "support_reply",
        "crm": "crm_support_reply",
        "email": "email_send_guardrail",
        "ticket": "ticket_update_checker",
        "billing": "invoice_billing_reply",
    },
    "enterprise": {
        "access": "access_permission_change",
        "code_review": "code_change_review",
        "crm_support": "crm_support_reply",
        "data_export": "data_export_guardrail",
        "deployment": "deployment_readiness",
        "email": "email_send_guardrail",
        "incident": "incident_response_update",
        "ticket": "ticket_update_checker",
    },
    "personal_productivity": {
        "booking": "booking_purchase_guardrail",
        "calendar": "calendar_scheduling",
        "email": "email_send_guardrail",
        "file": "file_operation_guardrail",
        "meeting": "meeting_summary_checker",
        "publication": "publication_check",
        "research": "research_answer_grounding",
    },
    "government_civic": {
        "casework": "casework_response_checker",
        "foia": "foia_public_records_response_checker",
        "grant": "grant_application_review",
        "insurance": "insurance_claim_triage",
        "policy_memo": "policy_memo_grounding",
        "procurement": "procurement_vendor_risk",
        "publication": "publication_check",
        "records": "public_records_privacy_redaction",
    },
}


def _list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def normalize_evidence(
    evidence=None,
    *,
    source_id=None,
    retrieved_at=None,
    trust_tier="verified",
    redaction_status="redacted",
    metadata=None,
    raw_record_id=None,
):
    """Normalize evidence into Workflow/Agent structured evidence objects.

    Strings become structured evidence when `source_id` is supplied; otherwise
    they remain strings for prototype workflows. Dictionaries must include
    non-empty `text`.
    """

    items = []
    for item in _list(evidence):
        if isinstance(item, str):
            if not item.strip():
                raise AANAClientError("Evidence text must be non-empty.")
            if source_id:
                payload = {
                    "source_id": source_id,
                    "text": item,
                    "trust_tier": trust_tier,
                    "redaction_status": redaction_status,
                }
                if retrieved_at:
                    payload["retrieved_at"] = retrieved_at
                if metadata:
                    payload["metadata"] = dict(metadata)
                if raw_record_id:
                    payload["raw_record_id"] = raw_record_id
                items.append(payload)
            else:
                items.append(item)
            continue
        if not isinstance(item, dict):
            raise AANAClientError("Evidence item must be a string or object.")
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            raise AANAClientError("Structured evidence must include non-empty text.")
        payload = dict(item)
        if source_id and not payload.get("source_id"):
            payload["source_id"] = source_id
        if retrieved_at and not payload.get("retrieved_at"):
            payload["retrieved_at"] = retrieved_at
        payload.setdefault("trust_tier", trust_tier)
        payload.setdefault("redaction_status", redaction_status)
        if metadata:
            payload["metadata"] = {**payload.get("metadata", {}), **dict(metadata)}
        if raw_record_id and not payload.get("raw_record_id"):
            payload["raw_record_id"] = raw_record_id
        items.append(payload)
    return items


def evidence_object(
    text,
    *,
    source_id,
    retrieved_at=None,
    trust_tier="verified",
    redaction_status="redacted",
    metadata=None,
    raw_record_id=None,
):
    """Build one structured evidence object for Workflow or Agent payloads."""

    return normalize_evidence(
        text,
        source_id=source_id,
        retrieved_at=retrieved_at,
        trust_tier=trust_tier,
        redaction_status=redaction_status,
        metadata=metadata,
        raw_record_id=raw_record_id,
    )[0]


def build_family_workflow_request(family, **kwargs):
    """Build a Workflow Contract request with family metadata attached."""

    metadata = dict(kwargs.pop("metadata", {}) or {})
    metadata.setdefault("aana_family", family)
    return build_workflow_request(metadata=metadata, **kwargs)


def build_workflow_request(
    *,
    adapter,
    request,
    candidate=None,
    evidence=None,
    constraints=None,
    allowed_actions=None,
    metadata=None,
    workflow_id=None,
):
    """Build a valid Workflow Contract request dictionary."""

    return workflow_contract.normalize_workflow_request(
        adapter=adapter,
        request=request,
        candidate=candidate,
        evidence=normalize_evidence(evidence),
        constraints=constraints,
        allowed_actions=allowed_actions,
        metadata=metadata,
        workflow_id=workflow_id,
    )


def build_agent_event(
    *,
    user_request,
    adapter_id=None,
    workflow=None,
    candidate_action=None,
    candidate_answer=None,
    draft_response=None,
    available_evidence=None,
    allowed_actions=None,
    metadata=None,
    agent="app",
    event_id=None,
):
    """Build an Agent Event Contract dictionary."""

    if not adapter_id and not workflow:
        raise AANAClientError("Agent event requires adapter_id or workflow.")
    event = {
        "event_version": agent_contract.AGENT_EVENT_VERSION,
        "agent": agent,
        "user_request": user_request,
        "available_evidence": normalize_evidence(available_evidence),
    }
    if event_id:
        event["event_id"] = event_id
    if adapter_id:
        event["adapter_id"] = adapter_id
    if workflow:
        event["workflow"] = workflow
    if candidate_action is not None:
        event["candidate_action"] = candidate_action
    if candidate_answer is not None:
        event["candidate_answer"] = candidate_answer
    if draft_response is not None:
        event["draft_response"] = draft_response
    if allowed_actions is not None:
        event["allowed_actions"] = list(allowed_actions)
    if metadata is not None:
        event["metadata"] = dict(metadata)
    return event


@dataclass
class AANAClient:
    """Small client for local AANA checks or HTTP bridge checks."""

    base_url: str | None = None
    token: str | None = None
    timeout: float = 10.0
    gallery_path: str | None = None
    shadow_mode: bool = False
    default_headers: dict[str, str] = field(default_factory=dict)

    @property
    def uses_bridge(self):
        return bool(self.base_url)

    def evidence(self, evidence=None, **kwargs):
        return normalize_evidence(evidence, **kwargs)

    def workflow_request(self, **kwargs):
        return build_workflow_request(**kwargs)

    def agent_event(self, **kwargs):
        return build_agent_event(**kwargs)

    def validate_workflow(self, workflow_request):
        if self.uses_bridge:
            return self._post("/validate-workflow", workflow_request)
        return agent_api.validate_workflow_request(workflow_request)

    def validate_event(self, event):
        if self.uses_bridge:
            return self._post("/validate-event", event)
        return agent_api.validate_event(event)

    def workflow_check(self, workflow_request=None, **kwargs):
        request = workflow_request or self.workflow_request(**kwargs)
        if self.uses_bridge:
            return self._post("/workflow-check", request, shadow_mode=self.shadow_mode)
        result = agent_api.check_workflow_request(request, gallery_path=self.gallery_path or agent_api.DEFAULT_GALLERY)
        return agent_api.apply_shadow_mode(result) if self.shadow_mode else result

    def agent_check(self, event=None, **kwargs):
        payload = event or self.agent_event(**kwargs)
        if self.uses_bridge:
            return self._post("/agent-check", payload, shadow_mode=self.shadow_mode)
        result = agent_api.check_event(payload, gallery_path=self.gallery_path or agent_api.DEFAULT_GALLERY)
        return agent_api.apply_shadow_mode(result) if self.shadow_mode else result

    def workflow_batch(self, requests, batch_id=None):
        payload = {
            "contract_version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "requests": [
                item.to_dict() if hasattr(item, "to_dict") else item
                for item in requests
            ],
        }
        if batch_id:
            payload["batch_id"] = batch_id
        if self.uses_bridge:
            return self._post("/workflow-batch", payload, shadow_mode=self.shadow_mode)
        result = agent_api.check_workflow_batch(payload, gallery_path=self.gallery_path or agent_api.DEFAULT_GALLERY)
        return agent_api.apply_shadow_mode(result) if self.shadow_mode else result

    def ready(self):
        if not self.uses_bridge:
            return agent_api.schema_catalog()
        return self._get("/ready")

    def _url(self, path, *, shadow_mode=False):
        base = (self.base_url or "").rstrip("/")
        if not base:
            raise AANAClientError("base_url is required for HTTP bridge calls.")
        query = {"shadow_mode": "true"} if shadow_mode else None
        return f"{base}{path}" + (f"?{urlencode(query)}" if query else "")

    def _headers(self):
        headers = {"content-type": "application/json", **self.default_headers}
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
        return headers

    def _post(self, path, payload, *, shadow_mode=False):
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(self._url(path, shadow_mode=shadow_mode), data=body, method="POST")
        for key, value in self._headers().items():
            request.add_header(key, value)
        return self._open(request)

    def _get(self, path):
        request = urllib.request.Request(self._url(path), method="GET")
        return self._open(request)

    def _open(self, request):
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {"error": exc.reason}
            raise AANAClientError(f"AANA bridge HTTP {exc.code}: {payload}") from exc
        except urllib.error.URLError as exc:
            raise AANAClientError(f"AANA bridge request failed: {exc.reason}") from exc
        return json.loads(text) if text else {}


@dataclass
class FamilyAANAClient(AANAClient):
    """AANA client with a default adapter family and short adapter aliases."""

    family_id: str = "custom"
    adapter_aliases: dict[str, str] = field(default_factory=dict)

    def resolve_adapter(self, adapter):
        return self.adapter_aliases.get(adapter, adapter)

    def _family_metadata(self, metadata=None):
        payload = dict(metadata or {})
        payload.setdefault("aana_family", self.family_id)
        return payload

    def workflow_request(self, **kwargs):
        if "adapter" in kwargs:
            kwargs["adapter"] = self.resolve_adapter(kwargs["adapter"])
        kwargs["metadata"] = self._family_metadata(kwargs.get("metadata"))
        return build_workflow_request(**kwargs)

    def agent_event(self, **kwargs):
        if "adapter_id" in kwargs and kwargs["adapter_id"]:
            kwargs["adapter_id"] = self.resolve_adapter(kwargs["adapter_id"])
        kwargs["metadata"] = self._family_metadata(kwargs.get("metadata"))
        return build_agent_event(**kwargs)

    def family_workflow_request(self, **kwargs):
        return self.workflow_request(**kwargs)

    def evidence_object(self, text, *, source_id, **kwargs):
        return evidence_object(text, source_id=source_id, **kwargs)


class EnterpriseAANAClient(FamilyAANAClient):
    def __init__(self, **kwargs):
        super().__init__(family_id="enterprise", adapter_aliases=FAMILY_ADAPTER_ALIASES["enterprise"], **kwargs)


class SupportAANAClient(FamilyAANAClient):
    def __init__(self, **kwargs):
        super().__init__(family_id="support", adapter_aliases=FAMILY_ADAPTER_ALIASES["support"], **kwargs)


class PersonalAANAClient(FamilyAANAClient):
    def __init__(self, **kwargs):
        super().__init__(
            family_id="personal_productivity",
            adapter_aliases=FAMILY_ADAPTER_ALIASES["personal_productivity"],
            **kwargs,
        )


class CivicAANAClient(FamilyAANAClient):
    def __init__(self, **kwargs):
        super().__init__(family_id="government_civic", adapter_aliases=FAMILY_ADAPTER_ALIASES["government_civic"], **kwargs)


def client(**kwargs):
    """Create an AANAClient."""

    return AANAClient(**kwargs)
