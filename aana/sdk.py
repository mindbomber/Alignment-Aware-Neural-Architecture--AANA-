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

from aana.canonical_ids import (
    AUTHORIZATION_STATES as CANONICAL_AUTHORIZATION_STATES,
    REDACTION_STATUSES,
    RISK_DOMAINS as CANONICAL_RISK_DOMAINS,
    ROUTE_TABLE as CANONICAL_ROUTE_TABLE,
    RUNTIME_MODES,
    TOOL_CATEGORIES as CANONICAL_TOOL_CATEGORIES,
    TOOL_EVIDENCE_TYPES,
    TOOL_PRECHECK_ROUTES as CANONICAL_TOOL_PRECHECK_ROUTES,
    TRUST_TIERS,
    route_allows_execution,
)
from aana.bundles import bundle_adapter_aliases
from eval_pipeline import agent_api, agent_contract, workflow_contract
from eval_pipeline.evidence_safety import analyze_tool_evidence_refs, grounded_qa_evidence_coverage
from eval_pipeline.pre_tool_call_gate import gate_pre_tool_call, gate_pre_tool_call_v2, validate_event as validate_tool_precheck_event


PUBLIC_ARCHITECTURE_CLAIM = "AANA is an architecture for making agents more auditable, safer, more grounded, and more controllable."
TOOL_PRECHECK_SCHEMA_VERSION = "aana.agent_tool_precheck.v1"
TOOL_CATEGORIES = set(CANONICAL_TOOL_CATEGORIES)
AUTHORIZATION_STATES = set(CANONICAL_AUTHORIZATION_STATES)
TOOL_PRECHECK_ROUTES = set(CANONICAL_TOOL_PRECHECK_ROUTES)
ROUTE_TABLE = CANONICAL_ROUTE_TABLE
EXECUTION_MODES = set(RUNTIME_MODES)
RISK_DOMAINS = set(CANONICAL_RISK_DOMAINS)


class AANAClientError(RuntimeError):
    """Raised when a bridge request fails or a helper receives invalid input."""


FAMILY_ADAPTER_ALIASES = {
    "enterprise": bundle_adapter_aliases("enterprise"),
    "support": bundle_adapter_aliases("enterprise"),
    "personal_productivity": bundle_adapter_aliases("personal_productivity"),
    "government_civic": bundle_adapter_aliases("government_civic"),
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
    citation_url=None,
    retrieval_url=None,
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
                if citation_url:
                    payload["citation_url"] = citation_url
                if retrieval_url:
                    payload["retrieval_url"] = retrieval_url
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
        if citation_url and not payload.get("citation_url"):
            payload["citation_url"] = citation_url
        if retrieval_url and not payload.get("retrieval_url"):
            payload["retrieval_url"] = retrieval_url
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
    citation_url=None,
    retrieval_url=None,
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
        citation_url=citation_url,
        retrieval_url=retrieval_url,
        metadata=metadata,
        raw_record_id=raw_record_id,
    )[0]


def tool_evidence_ref(
    *,
    source_id,
    kind,
    trust_tier="unknown",
    redaction_status="unknown",
    summary=None,
    retrieved_at=None,
    citation_url=None,
    retrieval_url=None,
    provenance=None,
    supports=None,
    contradicts=None,
):
    """Build one redacted evidence reference for a pre-tool-call event."""

    if not isinstance(source_id, str) or not source_id.strip():
        raise AANAClientError("Tool evidence ref requires a non-empty source_id.")
    if kind not in TOOL_EVIDENCE_TYPES:
        raise AANAClientError(f"Unsupported tool evidence kind: {kind!r}.")
    if trust_tier not in TRUST_TIERS:
        raise AANAClientError(f"Unsupported evidence trust tier: {trust_tier!r}.")
    if redaction_status not in REDACTION_STATUSES:
        raise AANAClientError(f"Unsupported evidence redaction status: {redaction_status!r}.")
    ref = {
        "source_id": source_id,
        "kind": kind,
        "trust_tier": trust_tier,
        "redaction_status": redaction_status,
    }
    if summary is not None:
        ref["summary"] = str(summary)
    if retrieved_at is not None:
        ref["retrieved_at"] = str(retrieved_at)
    if citation_url is not None:
        ref["citation_url"] = str(citation_url)
    if retrieval_url is not None:
        ref["retrieval_url"] = str(retrieval_url)
    if provenance is not None:
        ref["provenance"] = str(provenance)
    if supports is not None:
        ref["supports"] = list(supports)
    if contradicts is not None:
        ref["contradicts"] = list(contradicts)
    return ref


def normalize_tool_evidence_refs(evidence_refs=None):
    """Normalize public quickstart evidence refs into pre-tool-call refs.

    Strings such as ``"draft_id:123"`` are accepted for quickstarts and become
    redacted ``other`` refs. Strict schema validation still requires the
    structured form after normalization.
    """

    refs = []
    for index, ref in enumerate(_list(evidence_refs), start=1):
        if isinstance(ref, str):
            if not ref.strip():
                raise AANAClientError("Tool evidence ref strings must be non-empty.")
            refs.append(
                tool_evidence_ref(
                    source_id=ref.strip(),
                    kind="other",
                    trust_tier="runtime",
                    redaction_status="redacted",
                    summary="Quickstart evidence reference supplied by the agent runtime.",
                )
            )
            continue
        if not isinstance(ref, dict):
            raise AANAClientError(f"Tool evidence ref at index {index} must be a string or object.")
        payload = dict(ref)
        payload.setdefault("kind", "other")
        payload.setdefault("trust_tier", "unknown")
        payload.setdefault("redaction_status", "unknown")
        refs.append(tool_evidence_ref(**payload))
    return refs


def _normalize_public_tool_route(tool_category, authorization_state, recommended_route):
    """Keep public helper inputs schema-valid without weakening the contract."""

    if recommended_route != "accept":
        return recommended_route
    if tool_category == "write" and authorization_state not in {"validated", "confirmed"}:
        return "ask"
    if tool_category == "private_read" and authorization_state not in {"authenticated", "validated", "confirmed"}:
        return "ask"
    if tool_category == "unknown":
        return "defer"
    return recommended_route


def build_tool_precheck_event(
    *,
    tool_name,
    tool_category,
    authorization_state,
    evidence_refs,
    risk_domain,
    proposed_arguments,
    recommended_route="accept",
    request_id=None,
    agent_id=None,
    user_intent=None,
    authorization_subject=None,
):
    """Build an AANA Agent Tool Precheck Contract event.

    This is the small contract an agent runtime emits immediately before a tool
    call. Use `check_tool_precheck` to validate and gate it locally.
    """

    if tool_category not in TOOL_CATEGORIES:
        raise AANAClientError(f"Unsupported tool_category: {tool_category!r}.")
    if authorization_state not in AUTHORIZATION_STATES:
        raise AANAClientError(f"Unsupported authorization_state: {authorization_state!r}.")
    if recommended_route not in TOOL_PRECHECK_ROUTES:
        raise AANAClientError(f"Unsupported recommended_route: {recommended_route!r}.")
    if risk_domain not in RISK_DOMAINS:
        raise AANAClientError(f"Unsupported risk_domain: {risk_domain!r}.")
    if not isinstance(proposed_arguments, dict):
        raise AANAClientError("proposed_arguments must be a dictionary.")

    event = {
        "schema_version": TOOL_PRECHECK_SCHEMA_VERSION,
        "tool_name": str(tool_name),
        "tool_category": tool_category,
        "authorization_state": authorization_state,
        "evidence_refs": normalize_tool_evidence_refs(evidence_refs),
        "risk_domain": risk_domain,
        "proposed_arguments": dict(proposed_arguments),
        "recommended_route": recommended_route,
    }
    if request_id:
        event["request_id"] = str(request_id)
    if agent_id:
        event["agent_id"] = str(agent_id)
    if user_intent:
        event["user_intent"] = str(user_intent)
    if authorization_subject is not None:
        event["authorization_subject"] = dict(authorization_subject)
    return event


def normalize_tool_call_event(event=None, **kwargs):
    """Normalize a public agent-action contract into the strict precheck event.

    This accepts the quickstart shape used by developers:
    ``tool_name``, ``tool_category``, ``authorization_state``, string or object
    ``evidence_refs``, ``risk_domain``, ``proposed_arguments``, and
    ``recommended_route``. It adds the schema version and normalizes evidence.
    """

    if event is None:
        payload = dict(kwargs)
    else:
        if not isinstance(event, dict):
            raise AANAClientError("Tool call event must be a dictionary.")
        payload = dict(event)
        payload.update(kwargs)
        if payload.get("schema_version") == TOOL_PRECHECK_SCHEMA_VERSION:
            return payload
    payload.setdefault("schema_version", TOOL_PRECHECK_SCHEMA_VERSION)
    recommended_route = _normalize_public_tool_route(
        payload.get("tool_category"),
        payload.get("authorization_state"),
        payload.get("recommended_route", "accept"),
    )
    return build_tool_precheck_event(
        request_id=payload.get("request_id"),
        agent_id=payload.get("agent_id"),
        tool_name=payload.get("tool_name"),
        tool_category=payload.get("tool_category"),
        authorization_state=payload.get("authorization_state"),
        evidence_refs=payload.get("evidence_refs", []),
        risk_domain=payload.get("risk_domain", "unknown"),
        proposed_arguments=payload.get("proposed_arguments", {}),
        recommended_route=recommended_route,
        user_intent=payload.get("user_intent"),
        authorization_subject=payload.get("authorization_subject"),
    )


def check_tool_precheck(event=None, **kwargs):
    """Run the local schema-based AANA pre-tool-call gate."""

    payload = event or build_tool_precheck_event(**kwargs)
    return gate_pre_tool_call(payload)


def check_tool_precheck_v2(event=None, **kwargs):
    """Run the local τ²-calibrated AANA v2 pre-tool-call gate."""

    payload = event or build_tool_precheck_event(**kwargs)
    return gate_pre_tool_call_v2(payload)


def _hard_blockers(result):
    if not isinstance(result, dict):
        return []
    blockers = result.get("hard_blockers")
    if not blockers and isinstance(result.get("aix"), dict):
        blockers = result["aix"].get("hard_blockers")
    return list(blockers or [])


def _evidence_ref_ids(event):
    if not isinstance(event, dict):
        return []
    refs = event.get("evidence_refs")
    if isinstance(refs, list):
        return [
            str(ref.get("source_id") or ref.get("id") or ref.get("kind") or f"evidence_ref:{index}")
            for index, ref in enumerate(refs, start=1)
            if isinstance(ref, dict)
        ]
    evidence = event.get("available_evidence") or event.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        return []
    output = []
    for index, item in enumerate(evidence, start=1):
        if isinstance(item, dict):
            output.append(str(item.get("source_id") or item.get("raw_record_id") or f"evidence:{index}"))
        elif isinstance(item, str) and item.strip():
            output.append(f"evidence:{index}")
    return output


def _missing_evidence_markers(result):
    blockers = _hard_blockers(result)
    missing = [
        blocker
        for blocker in blockers
        if any(marker in str(blocker) for marker in ("missing", "evidence", "authorization", "citation", "source"))
    ]
    for violation in (result.get("violations") if isinstance(result, dict) else []) or []:
        if not isinstance(violation, dict):
            continue
        code = str(violation.get("code") or "")
        message = str(violation.get("message") or "")
        if any(marker in f"{code} {message}".lower() for marker in ("missing", "evidence", "authorization", "citation", "source", "unsupported")):
            missing.append(code or message)
    return list(dict.fromkeys(item for item in missing if item))


def _contradictory_evidence_markers(result):
    if not isinstance(result, dict):
        return []
    integrity = result.get("evidence_integrity") if isinstance(result.get("evidence_integrity"), dict) else {}
    markers = list(integrity.get("contradictory_evidence_source_ids") or [])
    for blocker in _hard_blockers(result):
        if "contradict" in str(blocker):
            markers.append(str(blocker))
    return list(dict.fromkeys(item for item in markers if item))


def audit_safe_decision_event(result, event=None, *, latency_ms=None):
    """Build metadata-only audit event for one AANA decision.

    The event intentionally excludes raw prompts, candidate text, evidence text,
    safe responses, and proposed argument values.
    """

    result = result if isinstance(result, dict) else {}
    event = event if isinstance(event, dict) else {}
    aix = result.get("aix") if isinstance(result.get("aix"), dict) else {}
    route = result.get("recommended_action") or aix.get("decision") or "defer"
    metadata = result.get("audit_metadata") if isinstance(result.get("audit_metadata"), dict) else {}
    observed_latency = latency_ms if latency_ms is not None else metadata.get("latency_ms") or result.get("latency_ms")
    proposed_args = event.get("proposed_arguments") if isinstance(event.get("proposed_arguments"), dict) else {}
    return {
        "audit_event_version": "aana.audit_safe_decision.v1",
        "route": route,
        "gate_decision": result.get("gate_decision"),
        "candidate_gate": result.get("candidate_gate"),
        "aix_score": aix.get("score"),
        "aix_decision": aix.get("decision"),
        "hard_blockers": _hard_blockers(result),
        "missing_evidence": _missing_evidence_markers(result),
        "evidence_refs": {
            "used": _evidence_ref_ids(event),
            "missing": _missing_evidence_markers(result),
            "contradictory": _contradictory_evidence_markers(result),
        },
        "authorization_state": event.get("authorization_state")
        or (event.get("metadata") or {}).get("authorization_state")
        if isinstance(event.get("metadata"), dict)
        else event.get("authorization_state") or "not_declared",
        "authorization_report": result.get("authorization_report"),
        "tool_name": event.get("tool_name") or result.get("tool_name"),
        "tool_category": event.get("tool_category") or result.get("tool_category"),
        "risk_domain": event.get("risk_domain") or result.get("risk_domain"),
        "proposed_argument_keys": sorted(str(key) for key in proposed_args.keys()),
        "latency_ms": round(float(observed_latency), 3) if isinstance(observed_latency, (int, float)) and observed_latency >= 0 else None,
        "raw_payload_logged": False,
    }


def _correction_recovery_suggestion(route, result):
    safe_response = result.get("safe_response") if isinstance(result, dict) else None
    if route == "accept":
        return ROUTE_TABLE["accept"]["description"] + " Append the audit-safe decision event."
    if route == "revise":
        return "Use the corrected safe response, then recheck before execution." if safe_response else "Revise the candidate against blockers, then recheck."
    if route == "retrieve":
        return "Retrieve missing grounding or policy evidence, then recheck before execution."
    if route == "ask":
        return "Ask the user or runtime for the missing authorization, confirmation, or evidence before execution."
    if route == "defer":
        return "Defer to stronger evidence retrieval, a domain owner, or human review before execution."
    if route == "refuse":
        return "Refuse the proposed action or answer because a hard blocker prevents safe execution."
    return "Route is unknown; do not execute until a supported AANA route is produced."


def architecture_decision(result, event=None, *, audit_record=None):
    """Return the public AANA decision surface for agents and tool calls.

    The envelope makes the architecture explicit: route, AIx, blockers,
    evidence/authorization state, correction path, and audit-safe metadata.
    """

    result = result if isinstance(result, dict) else {}
    event = event if isinstance(event, dict) else {}
    aix = result.get("aix") if isinstance(result.get("aix"), dict) else {}
    route = result.get("recommended_action") or aix.get("decision") or "defer"
    audit_safe_log_event = audit_safe_decision_event(result, event)
    if isinstance(audit_record, dict):
        audit_safe_log_event["audit_record_type"] = audit_record.get("record_type")
        audit_safe_log_event["audit_record_version"] = audit_record.get("audit_record_version")
        audit_safe_log_event["audit_record_created_at"] = audit_record.get("created_at")
    elif isinstance(result.get("audit_summary"), dict):
        audit_safe_log_event["audit_summary"] = result["audit_summary"]
    return {
        "architecture_claim": PUBLIC_ARCHITECTURE_CLAIM,
        "route": route,
        "gate_decision": result.get("gate_decision"),
        "candidate_gate": result.get("candidate_gate"),
        "aix_score": aix.get("score"),
        "aix_decision": aix.get("decision"),
        "hard_blockers": _hard_blockers(result),
        "evidence_refs": {
            "used": _evidence_ref_ids(event),
            "missing": _missing_evidence_markers(result),
            "contradictory": _contradictory_evidence_markers(result),
        },
        "evidence_integrity": result.get("evidence_integrity"),
        "authorization_state": event.get("authorization_state")
        or (event.get("metadata") or {}).get("authorization_state")
        if isinstance(event.get("metadata"), dict)
        else event.get("authorization_state") or "not_declared",
        "authorization_report": result.get("authorization_report"),
        "tool_name": event.get("tool_name") or result.get("tool_name"),
        "tool_category": event.get("tool_category") or result.get("tool_category"),
        "risk_domain": event.get("risk_domain") or result.get("risk_domain"),
        "correction_recovery_suggestion": _correction_recovery_suggestion(route, result),
        "audit_safe_log_event": audit_safe_log_event,
    }


def with_architecture_decision(result, event=None, *, audit_record=None):
    """Attach an architecture_decision envelope to a result dictionary."""

    payload = dict(result or {})
    payload["architecture_decision"] = architecture_decision(payload, event, audit_record=audit_record)
    payload.setdefault("route", payload["architecture_decision"]["route"])
    payload["execution_policy"] = execution_policy(payload)
    return payload


def fail_closed_tool_result(message, event=None, *, blocker="contract_normalization_failed"):
    """Build a refusal result for malformed tool-call inputs."""

    hard_blockers = [blocker]
    return with_architecture_decision(
        {
            "contract_version": TOOL_PRECHECK_SCHEMA_VERSION,
            "tool_name": (event or {}).get("tool_name") if isinstance(event, dict) else None,
            "gate_decision": "fail",
            "recommended_action": "refuse",
            "candidate_gate": "fail",
            "aix": {
                "aix_version": "0.1",
                "score": 0.0,
                "components": {"P": 0.0, "F": 0.0, "C": 0.0},
                "decision": "refuse",
                "hard_blockers": hard_blockers,
            },
            "hard_blockers": hard_blockers,
            "reasons": ["fail_closed_runtime_safety", str(message)],
            "validation_errors": [{"path": "event", "message": str(message)}],
        },
        event if isinstance(event, dict) else {},
    )


def check_tool_call(event=None, **kwargs):
    """Check a proposed tool call and return the architecture-shaped decision."""

    try:
        payload = normalize_tool_call_event(event, **kwargs)
    except Exception as exc:
        raw_event = event if isinstance(event, dict) else dict(kwargs)
        return fail_closed_tool_result(exc, raw_event)
    return with_architecture_decision(check_tool_precheck(payload), payload)


def gate_action(event=None, **kwargs):
    """Alias for `check_tool_call` for agent runtimes that gate actions."""

    return check_tool_call(event, **kwargs)


def should_execute_tool(result):
    """Return True only when the AANA pre-tool-call result allows execution."""

    return execution_policy(result, mode="enforce")["aana_allows_execution"]


def execution_policy(result, *, mode=None):
    """Return the uniform AANA runtime execution policy for tool wrappers.

    Enforcement mode executes only when the AANA route is truly ``accept``:
    gate pass, recommended action accept, architecture route accept, no schema
    errors, and no hard blockers. Shadow mode is observe-only; it may allow the
    host application to continue, but it does not convert a blocked AANA route
    into an enforcement accept.
    """

    result = result if isinstance(result, dict) else {}
    requested_mode = mode or ("shadow" if result.get("shadow_mode") or result.get("execution_mode") == "shadow" else "enforce")
    if requested_mode not in EXECUTION_MODES:
        requested_mode = "enforce"
    aix = result.get("aix") if isinstance(result, dict) else {}
    architecture = result.get("architecture_decision") if isinstance(result.get("architecture_decision"), dict) else {}
    hard_blockers = list(result.get("hard_blockers") or [])
    if isinstance(aix, dict):
        hard_blockers.extend(aix.get("hard_blockers") or [])
    hard_blockers.extend(architecture.get("hard_blockers") or [])
    validation_errors = result.get("validation_errors") or []
    gate_decision = result.get("gate_decision")
    recommended_action = result.get("recommended_action")
    architecture_route = architecture.get("route") or recommended_action
    route_can_execute = route_allows_execution(str(architecture_route or ""))
    aana_allows = (
        gate_decision == "pass"
        and recommended_action == "accept"
        and route_can_execute
        and not hard_blockers
        and not validation_errors
    )
    execution_allowed = aana_allows if requested_mode == "enforce" else True
    if validation_errors:
        reason = "schema_or_contract_validation_failed"
    elif hard_blockers:
        reason = "hard_blockers_present"
    elif not aana_allows:
        reason = "route_not_accept"
    elif requested_mode == "shadow":
        reason = "shadow_mode_observe_only"
    else:
        reason = "enforcement_accept"
    return {
        "mode": requested_mode,
        "aana_allows_execution": aana_allows,
        "execution_allowed": execution_allowed,
        "fail_closed": not aana_allows,
        "reason": reason,
        "required_route": "accept",
        "route_table": ROUTE_TABLE,
        "observed": {
            "gate_decision": gate_decision,
            "recommended_action": recommended_action,
            "architecture_route": architecture_route,
            "hard_blocker_count": len(hard_blockers),
            "validation_error_count": len(validation_errors),
        },
    }


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

    def tool_precheck_event(self, **kwargs):
        return build_tool_precheck_event(**kwargs)

    def validate_workflow(self, workflow_request):
        if self.uses_bridge:
            return self._post("/validate-workflow", workflow_request)
        return agent_api.validate_workflow_request(workflow_request)

    def validate_event(self, event):
        if self.uses_bridge:
            return self._post("/validate-event", event)
        return agent_api.validate_event(event)

    def validate_tool_precheck(self, event):
        if self.uses_bridge:
            return self._post("/validate-tool-precheck", event)
        errors = validate_tool_precheck_event(event)
        return {
            "valid": not errors,
            "errors": errors,
            "schema_version": TOOL_PRECHECK_SCHEMA_VERSION,
        }

    def workflow_check(self, workflow_request=None, **kwargs):
        request = workflow_request or self.workflow_request(**kwargs)
        if self.uses_bridge:
            return self._post("/workflow-check", request, shadow_mode=self.shadow_mode)
        result = agent_api.check_workflow_request(request, gallery_path=self.gallery_path or agent_api.DEFAULT_GALLERY)
        return agent_api.apply_shadow_mode(result) if self.shadow_mode else result

    def agent_check(self, event=None, **kwargs):
        payload = event or self.agent_event(**kwargs)
        if self.uses_bridge:
            return with_architecture_decision(self._post("/agent-check", payload, shadow_mode=self.shadow_mode), payload)
        result = agent_api.check_event(payload, gallery_path=self.gallery_path or agent_api.DEFAULT_GALLERY)
        result = agent_api.apply_shadow_mode(result) if self.shadow_mode else result
        return with_architecture_decision(result, payload)

    def tool_precheck(self, event=None, **kwargs):
        try:
            payload = event or self.tool_precheck_event(**kwargs)
        except Exception as exc:
            return fail_closed_tool_result(exc, event if isinstance(event, dict) else dict(kwargs))
        if self.uses_bridge:
            return with_architecture_decision(self._post("/tool-precheck", payload, shadow_mode=self.shadow_mode), payload)
        result = check_tool_precheck(payload)
        result = agent_api.apply_shadow_mode(result) if self.shadow_mode else result
        return with_architecture_decision(result, payload)

    def tool_precheck_v2(self, event=None, **kwargs):
        payload = event or self.tool_precheck_event(**kwargs)
        if self.uses_bridge:
            raise AANAClientError("tool_precheck_v2 is currently available only in local in-process mode.")
        return with_architecture_decision(check_tool_precheck_v2(payload), payload)

    def check_tool_call(self, event=None, **kwargs):
        return self.tool_precheck(event, **kwargs)

    def gate_action(self, event=None, **kwargs):
        return self.check_tool_call(event, **kwargs)

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
