"""Redacted audit records for AANA gate decisions."""

import datetime
import hashlib
import json
import pathlib
import re

from eval_pipeline import adapter_gallery


AUDIT_RECORD_VERSION = "0.1"
AUDIT_INTEGRITY_MANIFEST_VERSION = "0.1"
AUDIT_METRICS_EXPORT_VERSION = "0.1"
AUDIT_DRIFT_REPORT_VERSION = "0.1"
AUDIT_REVIEWER_REPORT_VERSION = "0.1"
AUDIT_DASHBOARD_VERSION = "0.1"
AUDIT_RECORD_TYPES = {"agent_check", "workflow_check", "workflow_batch_check", "tool_precheck"}
EXECUTION_MODES = {"advisory", "enforce", "shadow"}
SHADOW_ROUTES = {"pass", "revise", "defer", "refuse"}
SHADOW_ACTION_ROUTE = {
    "accept": "pass",
    "revise": "revise",
    "retrieve": "revise",
    "ask": "revise",
    "defer": "defer",
    "refuse": "refuse",
}
PROHIBITED_AUDIT_FIELDS = {
    "prompt",
    "user_request",
    "request",
    "candidate",
    "candidate_action",
    "candidate_answer",
    "draft_response",
    "available_evidence",
    "evidence",
    "constraints",
    "safe_response",
    "output",
    "proposed_arguments",
    "arguments",
    "tool_arguments",
    "full_tool_arguments",
    "raw_tool_arguments",
}
PROHIBITED_AUDIT_KEY_PATTERN = re.compile(
    r"(?i)(^|_)(api[_-]?key|auth[_-]?token|bearer[_-]?token|client[_-]?secret|"
    r"password|private[_-]?account[_-]?id|raw[_-]?token|secret|session[_-]?token)($|_)"
)
PROHIBITED_AUDIT_VALUE_PATTERNS = [
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")),
    ("api_key", re.compile(r"\b(?:sk|sk-or|sk-proj|hf|ghp|github_pat)_[A-Za-z0-9][A-Za-z0-9._-]{12,}")),
    ("credential_assignment", re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^,\s}]{8,}")),
    ("private_account_id", re.compile(r"\b(?:acct|account|customer|user|card|payment)_[A-Za-z0-9]{8,}\b")),
]
SUPPORT_REVIEW_ROUTE_CODES = {
    "missing_account_verification_path": "support_verification_review",
    "wrong_or_unverified_recipient": "support_security_review",
    "broad_or_bcc_recipient": "support_security_review",
    "broad_or_hidden_recipient": "support_security_review",
    "unsafe_attachment": "support_security_review",
    "unsafe_email_attachment": "support_security_review",
    "irreversible_send_without_approval": "support_security_review",
    "private_account_detail": "support_privacy_review",
    "private_payment_data": "support_privacy_review",
    "internal_crm_detail": "support_privacy_review",
    "internal_crm_leakage": "support_privacy_review",
    "unsupported_refund_promise": "support_policy_review",
    "invented_order_id": "support_policy_review",
    "bypass_verification": "support_verification_review",
}
HUMAN_REVIEW_TRIGGER_CODES = {
    "refund_exception": {"refund_exception"},
    "unsupported_refund_promise": {"refund_exception", "policy_ambiguity"},
    "billing_credit_promise_unauthorized": {"refund_exception", "policy_ambiguity"},
    "private_account_detail": {"payment_billing_data_exposure"},
    "private_payment_data": {"payment_billing_data_exposure"},
    "private_email_data": {"payment_billing_data_exposure"},
    "billing_payment_data_exposed": {"payment_billing_data_exposure"},
    "internal_crm_detail": {"internal_fraud_risk_note_exposure"},
    "internal_crm_leakage": {"internal_fraud_risk_note_exposure"},
    "renewal_private_notes_exposed": {"internal_fraud_risk_note_exposure"},
    "legal_jurisdiction_unverified": {"legal_regulatory_request"},
    "legal_policy_limit_erasure": {"legal_regulatory_request", "account_closure_deletion_request"},
    "high_stakes_legal_without_review": {"legal_regulatory_request"},
    "public_records_private_info_exposed": {"legal_regulatory_request"},
    "privacy_public_records_leak": {"legal_regulatory_request"},
    "account_closure_request": {"account_closure_deletion_request"},
    "account_deletion_request": {"account_closure_deletion_request"},
    "data_deletion_request": {"account_closure_deletion_request"},
    "missing_account_verification_path": {"identity_uncertainty"},
    "bypass_verification": {"identity_uncertainty"},
    "wrong_or_unverified_recipient": {"identity_uncertainty"},
    "broad_or_hidden_recipient": {"identity_uncertainty", "policy_ambiguity"},
    "broad_or_bcc_recipient": {"identity_uncertainty", "policy_ambiguity"},
    "irreversible_send_without_approval": {"policy_ambiguity"},
    "unsafe_email_attachment": {"payment_billing_data_exposure"},
    "unsafe_attachment": {"payment_billing_data_exposure"},
    "vendor_identity_unverified": {"identity_uncertainty"},
    "high_value_customer_escalation": {"high_value_customer_escalation"},
    "policy_ambiguity": {"policy_ambiguity"},
    "recommended_action_not_allowed": {"policy_ambiguity"},
}
HUMAN_REVIEW_TRIGGER_PRIORITY = {
    "payment_billing_data_exposure": "critical",
    "internal_fraud_risk_note_exposure": "critical",
    "legal_regulatory_request": "critical",
    "account_closure_deletion_request": "critical",
    "aix_hard_blocker": "critical",
    "recommended_action_defer": "critical",
    "identity_uncertainty": "high",
    "refund_exception": "high",
    "high_value_customer_escalation": "high",
    "policy_ambiguity": "high",
}
ACTION_REVIEW_ROUTES = {
    "accept": ("none", False),
    "revise": ("agent_revision", False),
    "retrieve": ("evidence_retrieval", False),
    "ask": ("human_verification_review", True),
    "defer": ("human_review_queue", True),
    "refuse": ("blocked_action_review", True),
}
SOURCE_ID_PATTERN = re.compile(r"\bsource_id=([A-Za-z0-9_.:-]+)")
SENSITIVE_ARGUMENT_KEY_PATTERN = re.compile(
    r"(?i)(api[_-]?key|auth[_-]?token|bearer[_-]?token|client[_-]?secret|"
    r"password|private[_-]?account[_-]?id|raw[_-]?token|secret|session[_-]?token)"
)


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _fingerprint(value):
    if value is None:
        return None
    text = str(value)
    return {
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "length": len(text),
    }


def _fingerprint_list(values):
    if not values:
        return []
    return [_fingerprint(item) for item in values]


def _audit_safe_identifier(value, fallback):
    text = str(value or "").strip()
    if not text:
        return fallback
    if PROHIBITED_AUDIT_KEY_PATTERN.search(text) or any(pattern.search(text) for _, pattern in PROHIBITED_AUDIT_VALUE_PATTERNS):
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return f"{fallback}:sha256:{digest}"
    return text


def _evidence_source_ids(evidence):
    source_ids = []
    seen = set()
    for item in evidence or []:
        value = None
        if isinstance(item, dict):
            value = item.get("source_id")
        elif isinstance(item, str):
            match = SOURCE_ID_PATTERN.search(item)
            if match:
                value = match.group(1)
        if isinstance(value, str) and value:
            safe_value = _audit_safe_identifier(value, f"evidence:{len(source_ids) + 1}")
            if safe_value not in seen:
                seen.add(safe_value)
                source_ids.append(safe_value)
    return source_ids


def _tool_evidence_source_ids(evidence_refs):
    source_ids = []
    seen = set()
    for index, item in enumerate(evidence_refs or [], start=1):
        value = None
        if isinstance(item, dict):
            value = item.get("source_id") or item.get("id") or item.get("kind")
        elif isinstance(item, str):
            value = item.strip()
        if not value:
            value = f"evidence_ref:{index}"
        value = _audit_safe_identifier(value, f"evidence_ref:{index}")
        if value not in seen:
            seen.add(value)
            source_ids.append(value)
    return source_ids


def _safe_argument_keys(arguments):
    if not isinstance(arguments, dict):
        return []
    keys = []
    for key in arguments:
        key_text = str(key)
        keys.append("[redacted_sensitive_key]" if SENSITIVE_ARGUMENT_KEY_PATTERN.search(key_text) else key_text)
    return sorted(set(keys))


def _violation_codes(violations):
    codes = []
    for violation in violations or []:
        code = violation.get("code") if isinstance(violation, dict) else None
        if code:
            codes.append(code)
    return sorted(set(codes))


def _violation_severities(violations):
    counts = {}
    for violation in violations or []:
        if not isinstance(violation, dict):
            continue
        severity = violation.get("severity", "unknown")
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def _safe_code(value):
    return str(value).strip().replace(" ", "_").replace("/", "_") if value is not None else ""


def _normalized_failure_items(values, default_code="failure"):
    items = []
    for value in values or []:
        if isinstance(value, str):
            code = _safe_code(value)
            if code:
                items.append(code)
            continue
        if not isinstance(value, dict):
            continue
        source = value.get("source_id") or value.get("connector_id") or value.get("id") or "unknown"
        code = value.get("code") or value.get("status") or value.get("failure") or default_code
        normalized = ":".join(part for part in (_safe_code(source), _safe_code(code)) if part)
        if normalized:
            items.append(normalized)
    return sorted(set(items))


def _evidence_observability(evidence):
    connector_failures = []
    freshness_failures = []
    for item in evidence or []:
        if not isinstance(item, dict):
            continue
        source_id = item.get("source_id") or item.get("connector_id") or "unknown"
        connector_status = str(item.get("connector_status") or item.get("status") or "").lower()
        if connector_status in {"fail", "failed", "error", "unavailable", "unauthorized"}:
            connector_failures.append({"source_id": source_id, "code": connector_status})
        freshness_status = str(item.get("freshness_status") or item.get("freshness") or "").lower()
        if freshness_status in {"fail", "failed", "stale", "expired"}:
            freshness_failures.append({"source_id": source_id, "code": freshness_status})
    return {
        "connector_failures": _normalized_failure_items(connector_failures, default_code="connector_failure"),
        "evidence_freshness_failures": _normalized_failure_items(freshness_failures, default_code="stale_evidence"),
    }


def _operational_metadata(result, evidence=None):
    result = result if isinstance(result, dict) else {}
    metadata = {}
    for key in ("audit_metadata", "observability", "runtime_metadata"):
        value = result.get(key)
        if isinstance(value, dict):
            metadata.update(value)
    evidence_metadata = _evidence_observability(evidence)

    latency_ms = metadata.get("latency_ms")
    if not isinstance(latency_ms, (int, float)):
        latency_ms = result.get("latency_ms")
    adapter_version = metadata.get("adapter_version") or result.get("adapter_version")
    connector_failures = []
    connector_failures.extend(metadata.get("connector_failures", []) or [])
    connector_failures.extend(result.get("connector_failures", []) or [])
    connector_failures.extend(evidence_metadata["connector_failures"])
    freshness_failures = []
    freshness_failures.extend(metadata.get("evidence_freshness_failures", []) or [])
    freshness_failures.extend(metadata.get("freshness_failures", []) or [])
    freshness_failures.extend(result.get("evidence_freshness_failures", []) or [])
    freshness_failures.extend(evidence_metadata["evidence_freshness_failures"])

    return {
        "latency_ms": round(float(latency_ms), 3) if isinstance(latency_ms, (int, float)) and latency_ms >= 0 else None,
        "adapter_version": str(adapter_version) if adapter_version else None,
        "connector_failures": _normalized_failure_items(connector_failures, default_code="connector_failure"),
        "evidence_freshness_failures": _normalized_failure_items(freshness_failures, default_code="stale_evidence"),
    }


def _review_triggers(result):
    result = result if isinstance(result, dict) else {}
    triggers = set()
    codes = _violation_codes(result.get("violations", []))
    for code in codes:
        triggers.update(HUMAN_REVIEW_TRIGGER_CODES.get(code, set()))

    aix = result.get("aix") if isinstance(result.get("aix"), dict) else {}
    hard_blockers = [str(item) for item in aix.get("hard_blockers", []) or [] if item]
    if hard_blockers:
        triggers.add("aix_hard_blocker")
    if result.get("recommended_action") == "defer":
        triggers.add("recommended_action_defer")
    return sorted(triggers)


def _review_priority(triggers):
    priorities = [HUMAN_REVIEW_TRIGGER_PRIORITY.get(trigger, "standard") for trigger in triggers]
    if "critical" in priorities:
        return "critical"
    if "high" in priorities:
        return "high"
    return "standard"


def _human_review_route(result):
    result = result if isinstance(result, dict) else {}
    action = result.get("recommended_action")
    route, required = ACTION_REVIEW_ROUTES.get(action, ("human_review_queue", True))
    reason = f"recommended_action:{action}" if action else "recommended_action:unknown"

    codes = _violation_codes(result.get("violations", []))
    for code in codes:
        support_route = SUPPORT_REVIEW_ROUTE_CODES.get(code)
        if support_route:
            return {
                "required": True,
                "route": support_route,
                "reason": f"violation:{code}",
            }

    aix = result.get("aix") if isinstance(result.get("aix"), dict) else {}
    hard_blockers = [str(item) for item in aix.get("hard_blockers", []) or [] if item]
    if hard_blockers and not required:
        route = "hard_blocker_review"
        required = True
        reason = "aix_hard_blocker"

    return {
        "required": required,
        "route": route,
        "reason": reason,
    }


def _human_review_queue(result):
    route = _human_review_route(result)
    triggers = _review_triggers(result)
    required = bool(route.get("required") or triggers)
    return {
        "required": required,
        "queue": "support_human_review" if required else "none",
        "route": route.get("route"),
        "priority": _review_priority(triggers) if required else "none",
        "triggers": triggers,
        "reason": route.get("reason"),
    }


def _add_issue(issues, level, path, message):
    issues.append({"level": level, "path": path, "message": message})


def _audit_sensitive_findings(value, path="$"):
    findings = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            is_fingerprint_metadata = ".input_fingerprints." in child_path
            if (key_text in PROHIBITED_AUDIT_FIELDS and not is_fingerprint_metadata) or PROHIBITED_AUDIT_KEY_PATTERN.search(key_text):
                findings.append(
                    {
                        "path": child_path,
                        "message": "Audit records must not store raw secrets, tokens, passwords, private account IDs, or full tool arguments.",
                    }
                )
            findings.extend(_audit_sensitive_findings(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_audit_sensitive_findings(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for pattern_id, pattern in PROHIBITED_AUDIT_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append(
                    {
                        "path": path,
                        "message": f"Audit record contains a raw sensitive value matching {pattern_id}; store a fingerprint or redacted source id instead.",
                    }
                )
    return findings


def _aix_summary(result):
    if not isinstance(result, dict):
        return None
    aix = result.get("aix")
    if not isinstance(aix, dict):
        return None
    return {
        "score": aix.get("score"),
        "decision": aix.get("decision"),
        "components": aix.get("components", {}),
        "beta": aix.get("beta"),
        "thresholds": aix.get("thresholds", {}),
        "hard_blockers": aix.get("hard_blockers", []),
    }


def shadow_route_from_action(action, gate_decision=None):
    route = SHADOW_ACTION_ROUTE.get(action)
    if route:
        return route
    if gate_decision == "pass":
        return "pass"
    if gate_decision == "fail":
        return "defer"
    return "defer"


def shadow_observation(result):
    result = result if isinstance(result, dict) else {}
    aix = result.get("aix") if isinstance(result.get("aix"), dict) else {}
    action = result.get("recommended_action")
    gate = result.get("gate_decision")
    return {
        "shadow_mode": True,
        "enforcement": "observe_only",
        "would_gate_decision": gate,
        "would_recommended_action": action,
        "would_candidate_gate": result.get("candidate_gate"),
        "would_aix_decision": aix.get("decision"),
        "would_route": shadow_route_from_action(action, gate_decision=gate),
        "production_effect": "not_blocked",
    }


def _execution_mode(result, shadow_mode=False):
    if shadow_mode:
        return "shadow"
    if isinstance(result, dict) and result.get("execution_mode") == "shadow":
        return "shadow"
    if isinstance(result, dict) and result.get("execution_mode") == "advisory":
        return "advisory"
    return "enforce"


def _add_execution_metadata(record, result, shadow_mode=False):
    mode = _execution_mode(result, shadow_mode=shadow_mode)
    record["execution_mode"] = mode
    if mode == "shadow":
        record["shadow_observation"] = shadow_observation(result)
    return record


def _audit_safe_decision_event_from_record(record):
    aix = record.get("aix") if isinstance(record.get("aix"), dict) else {}
    event = {
        "audit_event_version": "aana.audit_safe_decision.v1",
        "route": record.get("recommended_action"),
        "gate_decision": record.get("gate_decision"),
        "candidate_gate": record.get("candidate_gate"),
        "aix_score": aix.get("score"),
        "aix_decision": aix.get("decision"),
        "hard_blockers": list(record.get("hard_blockers") or aix.get("hard_blockers") or []),
        "missing_evidence": list(record.get("missing_evidence") or []),
        "evidence_refs": {
            "used": list(record.get("evidence_source_ids") or []),
            "missing": list(record.get("missing_evidence") or []),
            "contradictory": list(record.get("contradictory_evidence") or []),
        },
        "authorization_state": record.get("authorization_state") or "not_declared",
        "latency_ms": record.get("latency_ms"),
        "raw_payload_logged": False,
    }
    for key in ("tool_name", "tool_category", "risk_domain", "proposed_argument_keys"):
        if key in record:
            event[key] = record.get(key)
    return event


def _missing_evidence_from_result(result):
    missing = []
    if not isinstance(result, dict):
        return missing
    for blocker in result.get("hard_blockers", []) or []:
        text = str(blocker).lower()
        if any(marker in text for marker in ("missing", "evidence", "authorization", "source", "citation", "approval")):
            missing.append(str(blocker))
    for violation in result.get("violations", []) or []:
        if not isinstance(violation, dict):
            continue
        text = f"{violation.get('code', '')} {violation.get('message', '')}".lower()
        if any(marker in text for marker in ("missing", "evidence", "authorization", "source", "citation", "unsupported")):
            missing.append(str(violation.get("code") or violation.get("message")))
    return sorted(set(item for item in missing if item))


def _authorization_state_from_event(event):
    if not isinstance(event, dict):
        return "not_declared"
    if event.get("authorization_state"):
        return event.get("authorization_state")
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    return metadata.get("authorization_state") or "not_declared"


def agent_audit_record(event, result, created_at=None, shadow_mode=False):
    """Create a redacted audit record for an agent event check.

    The record intentionally excludes raw request, candidate, evidence, and
    safe-response text. Use the fingerprints to correlate records with stored
    secure artifacts when a deployment has a reviewed audit store.
    """

    evidence = event.get("available_evidence", []) if isinstance(event, dict) else []
    if not isinstance(evidence, list):
        evidence = []
    metadata = event.get("metadata", {}) if isinstance(event, dict) and isinstance(event.get("metadata"), dict) else {}
    candidate = None
    if isinstance(event, dict):
        candidate = event.get("candidate_action")
        if candidate is None:
            candidate = event.get("candidate_answer")
        if candidate is None:
            candidate = event.get("draft_response")

    violations = result.get("violations", []) if isinstance(result, dict) else []
    aix_summary = _aix_summary(result)
    human_review_queue = _human_review_queue(result)
    operations = _operational_metadata(result, evidence=evidence)
    record = {
        "audit_record_version": AUDIT_RECORD_VERSION,
        "created_at": created_at or _utc_now(),
        "record_type": "agent_check",
        "event_version": event.get("event_version") if isinstance(event, dict) else None,
        "event_id": event.get("event_id") if isinstance(event, dict) else None,
        "agent": result.get("agent") if isinstance(result, dict) else None,
        "adapter_id": (result.get("adapter_id") if isinstance(result, dict) else None)
        or (event.get("adapter_id") if isinstance(event, dict) else None),
        "workflow_id": (result.get("workflow_id") if isinstance(result, dict) else None) or metadata.get("workflow_id"),
        "workflow": result.get("workflow") if isinstance(result, dict) else None,
        "adapter_version": operations["adapter_version"],
        "gate_decision": result.get("gate_decision") if isinstance(result, dict) else None,
        "recommended_action": result.get("recommended_action") if isinstance(result, dict) else None,
        "candidate_gate": result.get("candidate_gate") if isinstance(result, dict) else None,
        "aix": aix_summary,
        "hard_blockers": (aix_summary or {}).get("hard_blockers", []),
        "missing_evidence": _missing_evidence_from_result(result),
        "authorization_state": _authorization_state_from_event(event),
        "violation_count": len(violations),
        "violation_codes": _violation_codes(violations),
        "violation_severities": _violation_severities(violations),
        "evidence_source_ids": _evidence_source_ids(evidence),
        "latency_ms": operations["latency_ms"],
        "connector_failures": operations["connector_failures"],
        "evidence_freshness_failures": operations["evidence_freshness_failures"],
        "allowed_actions": list(event.get("allowed_actions", [])) if isinstance(event, dict) else [],
        "human_review_route": {
            "required": human_review_queue["required"],
            "route": human_review_queue["route"],
            "reason": human_review_queue["reason"],
        },
        "human_review_queue": human_review_queue,
        "input_fingerprints": {
            "user_request": _fingerprint(event.get("user_request") or event.get("prompt")) if isinstance(event, dict) else None,
            "candidate": _fingerprint(candidate),
            "evidence": _fingerprint_list(evidence),
            "safe_response": _fingerprint(result.get("safe_response")) if isinstance(result, dict) else None,
        },
    }
    record["audit_safe_log_event"] = _audit_safe_decision_event_from_record(record)
    return _add_execution_metadata(record, result, shadow_mode=shadow_mode)


def tool_precheck_audit_record(
    event,
    result,
    created_at=None,
    latency_ms=None,
    surface="runtime",
    route="/pre-tool-check",
    shadow_mode=False,
):
    """Create a redacted audit record for a pre-tool-call decision."""

    event = event if isinstance(event, dict) else {}
    result = result if isinstance(result, dict) else {}
    evidence_refs = event.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    operations = _operational_metadata(result, evidence=evidence_refs)
    if latency_ms is not None:
        operations["latency_ms"] = round(float(latency_ms), 3) if isinstance(latency_ms, (int, float)) and latency_ms >= 0 else None
    aix_summary = _aix_summary(result)
    human_review_queue = _human_review_queue(result)
    violations = result.get("violations", []) if isinstance(result.get("violations"), list) else []
    record = {
        "audit_record_version": AUDIT_RECORD_VERSION,
        "created_at": created_at or _utc_now(),
        "record_type": "tool_precheck",
        "surface": surface,
        "route": route,
        "contract_version": result.get("contract_version") or event.get("schema_version") or event.get("contract_version"),
        "tool_name": event.get("tool_name") or result.get("tool_name"),
        "tool_category": event.get("tool_category") or result.get("tool_category"),
        "risk_domain": event.get("risk_domain") or result.get("risk_domain"),
        "adapter_version": operations["adapter_version"],
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "aix": aix_summary,
        "hard_blockers": (aix_summary or {}).get("hard_blockers", result.get("hard_blockers", []) or []),
        "missing_evidence": _missing_evidence_from_result(result),
        "authorization_state": _authorization_state_from_event(event),
        "violation_count": len(violations),
        "violation_codes": _violation_codes(violations),
        "violation_severities": _violation_severities(violations),
        "evidence_source_ids": _tool_evidence_source_ids(evidence_refs),
        "proposed_argument_keys": _safe_argument_keys(event.get("proposed_arguments")),
        "latency_ms": operations["latency_ms"],
        "connector_failures": operations["connector_failures"],
        "evidence_freshness_failures": operations["evidence_freshness_failures"],
        "human_review_route": {
            "required": human_review_queue["required"],
            "route": human_review_queue["route"],
            "reason": human_review_queue["reason"],
        },
        "human_review_queue": human_review_queue,
        "input_fingerprints": {
            "evidence_refs": _fingerprint_list(evidence_refs),
            "tool_name": _fingerprint(event.get("tool_name")),
            "proposed_arguments": _fingerprint(event.get("proposed_arguments")),
        },
    }
    record["audit_safe_log_event"] = _audit_safe_decision_event_from_record(record)
    return _add_execution_metadata(record, result, shadow_mode=shadow_mode)


def workflow_audit_record(workflow_request, result, created_at=None, shadow_mode=False):
    """Create a redacted audit record for a Workflow Contract check."""

    workflow_request = workflow_request if isinstance(workflow_request, dict) else {}
    evidence = workflow_request.get("evidence", []) if isinstance(workflow_request, dict) else []
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        evidence = []
    constraints = workflow_request.get("constraints", []) if isinstance(workflow_request, dict) else []
    if isinstance(constraints, str):
        constraints = [constraints]
    if not isinstance(constraints, list):
        constraints = []

    violations = result.get("violations", []) if isinstance(result, dict) else []
    aix_summary = _aix_summary(result)
    human_review_queue = _human_review_queue(result)
    operations = _operational_metadata(result, evidence=evidence)
    record = {
        "audit_record_version": AUDIT_RECORD_VERSION,
        "created_at": created_at or _utc_now(),
        "record_type": "workflow_check",
        "contract_version": workflow_request.get("contract_version") if isinstance(workflow_request, dict) else None,
        "workflow_id": (result.get("workflow_id") if isinstance(result, dict) else None) or workflow_request.get("workflow_id"),
        "adapter": result.get("adapter") if isinstance(result, dict) else None,
        "adapter_id": (result.get("adapter") if isinstance(result, dict) else None) or workflow_request.get("adapter"),
        "workflow": result.get("workflow") if isinstance(result, dict) else None,
        "adapter_version": operations["adapter_version"],
        "gate_decision": result.get("gate_decision") if isinstance(result, dict) else None,
        "recommended_action": result.get("recommended_action") if isinstance(result, dict) else None,
        "candidate_gate": result.get("candidate_gate") if isinstance(result, dict) else None,
        "aix": aix_summary,
        "hard_blockers": (aix_summary or {}).get("hard_blockers", []),
        "missing_evidence": _missing_evidence_from_result(result),
        "authorization_state": _authorization_state_from_event(workflow_request),
        "violation_count": len(violations),
        "violation_codes": _violation_codes(violations),
        "violation_severities": _violation_severities(violations),
        "evidence_source_ids": _evidence_source_ids(evidence),
        "latency_ms": operations["latency_ms"],
        "connector_failures": operations["connector_failures"],
        "evidence_freshness_failures": operations["evidence_freshness_failures"],
        "allowed_actions": list(workflow_request.get("allowed_actions", [])) if isinstance(workflow_request, dict) else [],
        "constraint_count": len(constraints),
        "evidence_count": len(evidence),
        "human_review_route": {
            "required": human_review_queue["required"],
            "route": human_review_queue["route"],
            "reason": human_review_queue["reason"],
        },
        "human_review_queue": human_review_queue,
        "input_fingerprints": {
            "request": _fingerprint(workflow_request.get("request")) if isinstance(workflow_request, dict) else None,
            "candidate": _fingerprint(workflow_request.get("candidate")) if isinstance(workflow_request, dict) else None,
            "evidence": _fingerprint_list(evidence),
            "constraints": _fingerprint_list(constraints),
            "output": _fingerprint(result.get("output")) if isinstance(result, dict) else None,
        },
    }
    record["audit_safe_log_event"] = _audit_safe_decision_event_from_record(record)
    return _add_execution_metadata(record, result, shadow_mode=shadow_mode)


def append_jsonl(path, record):
    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    return str(output_path)


def _file_sha256(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(payload):
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _manifest_payload(manifest):
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return payload


def load_jsonl(path):
    records = []
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL audit record at line {line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Audit record at line {line_number} must be a JSON object.")
            records.append(record)
    return records


def validate_audit_record(record, path="$"):
    issues = []
    if not isinstance(record, dict):
        return {
            "valid": False,
            "errors": 1,
            "warnings": 0,
            "issues": [{"level": "error", "path": path, "message": "Audit record must be a JSON object."}],
        }

    if record.get("audit_record_version") != AUDIT_RECORD_VERSION:
        _add_issue(issues, "error", f"{path}.audit_record_version", f"audit_record_version must be {AUDIT_RECORD_VERSION}.")
    if record.get("record_type") not in AUDIT_RECORD_TYPES:
        _add_issue(issues, "error", f"{path}.record_type", "record_type must be a known AANA audit record type.")
    if not isinstance(record.get("created_at"), str) or not record.get("created_at", "").strip():
        _add_issue(issues, "error", f"{path}.created_at", "created_at must be a non-empty timestamp string.")
    if "gate_decision" in record and record.get("gate_decision") is not None and not isinstance(record.get("gate_decision"), str):
        _add_issue(issues, "error", f"{path}.gate_decision", "gate_decision must be a string or null.")
    if "recommended_action" in record and record.get("recommended_action") is not None and not isinstance(record.get("recommended_action"), str):
        _add_issue(issues, "error", f"{path}.recommended_action", "recommended_action must be a string or null.")
    if "adapter_version" in record and record.get("adapter_version") is not None and not isinstance(record.get("adapter_version"), str):
        _add_issue(issues, "error", f"{path}.adapter_version", "adapter_version must be a string or null.")
    if "latency_ms" in record and record.get("latency_ms") is not None and not isinstance(record.get("latency_ms"), (int, float)):
        _add_issue(issues, "error", f"{path}.latency_ms", "latency_ms must be numeric or null.")
    if "missing_evidence" in record and not isinstance(record.get("missing_evidence"), list):
        _add_issue(issues, "error", f"{path}.missing_evidence", "missing_evidence must be an array.")
    if "authorization_state" in record and record.get("authorization_state") is not None and not isinstance(record.get("authorization_state"), str):
        _add_issue(issues, "error", f"{path}.authorization_state", "authorization_state must be a string or null.")
    audit_event = record.get("audit_safe_log_event")
    if not isinstance(audit_event, dict):
        _add_issue(issues, "error", f"{path}.audit_safe_log_event", "Audit record must include audit_safe_log_event.")
    else:
        if audit_event.get("audit_event_version") != "aana.audit_safe_decision.v1":
            _add_issue(issues, "error", f"{path}.audit_safe_log_event.audit_event_version", "audit_safe_log_event must use aana.audit_safe_decision.v1.")
        for key in ("route", "hard_blockers", "missing_evidence", "authorization_state", "latency_ms"):
            if key not in audit_event:
                _add_issue(issues, "error", f"{path}.audit_safe_log_event.{key}", "Required audit-safe decision field is missing.")
        if not isinstance(audit_event.get("hard_blockers", []), list):
            _add_issue(issues, "error", f"{path}.audit_safe_log_event.hard_blockers", "hard_blockers must be an array.")
        if not isinstance(audit_event.get("missing_evidence", []), list):
            _add_issue(issues, "error", f"{path}.audit_safe_log_event.missing_evidence", "missing_evidence must be an array.")
        if audit_event.get("latency_ms") is not None and not isinstance(audit_event.get("latency_ms"), (int, float)):
            _add_issue(issues, "error", f"{path}.audit_safe_log_event.latency_ms", "latency_ms must be numeric or null.")
        if audit_event.get("raw_payload_logged") is not False:
            _add_issue(issues, "error", f"{path}.audit_safe_log_event.raw_payload_logged", "audit-safe decision events must not log raw payloads.")
    for field in ("connector_failures", "evidence_freshness_failures"):
        if field in record and (
            not isinstance(record.get(field), list)
            or not all(isinstance(item, str) for item in record.get(field))
        ):
            _add_issue(issues, "error", f"{path}.{field}", f"{field} must be an array of strings.")
    if record.get("execution_mode") is not None and record.get("execution_mode") not in EXECUTION_MODES:
        _add_issue(issues, "error", f"{path}.execution_mode", f"execution_mode must be one of {sorted(EXECUTION_MODES)}.")
    if record.get("execution_mode") == "shadow":
        shadow = record.get("shadow_observation")
        if not isinstance(shadow, dict):
            _add_issue(issues, "error", f"{path}.shadow_observation", "Shadow audit records must include shadow_observation.")
        else:
            if shadow.get("enforcement") != "observe_only":
                _add_issue(issues, "error", f"{path}.shadow_observation.enforcement", "Shadow enforcement must be observe_only.")
            if shadow.get("would_route") not in SHADOW_ROUTES:
                _add_issue(issues, "error", f"{path}.shadow_observation.would_route", f"would_route must be one of {sorted(SHADOW_ROUTES)}.")
    if not isinstance(record.get("input_fingerprints"), dict):
        _add_issue(issues, "error", f"{path}.input_fingerprints", "Audit record must include input_fingerprints object.")
    if "violation_count" in record and not isinstance(record.get("violation_count"), int):
        _add_issue(issues, "error", f"{path}.violation_count", "violation_count must be an integer.")
    if "violation_codes" in record and not isinstance(record.get("violation_codes"), list):
        _add_issue(issues, "error", f"{path}.violation_codes", "violation_codes must be an array.")
    if "hard_blockers" in record and not isinstance(record.get("hard_blockers"), list):
        _add_issue(issues, "error", f"{path}.hard_blockers", "hard_blockers must be an array.")
    if "evidence_source_ids" in record:
        source_ids = record.get("evidence_source_ids")
        if not isinstance(source_ids, list) or not all(isinstance(item, str) for item in source_ids):
            _add_issue(issues, "error", f"{path}.evidence_source_ids", "evidence_source_ids must be an array of strings.")
    if "human_review_route" in record:
        route = record.get("human_review_route")
        if not isinstance(route, dict):
            _add_issue(issues, "error", f"{path}.human_review_route", "human_review_route must be an object.")
        else:
            if not isinstance(route.get("required"), bool):
                _add_issue(issues, "error", f"{path}.human_review_route.required", "human_review_route.required must be boolean.")
            if not isinstance(route.get("route"), str) or not route.get("route"):
                _add_issue(issues, "error", f"{path}.human_review_route.route", "human_review_route.route must be a non-empty string.")
            if "reason" in route and route.get("reason") is not None and not isinstance(route.get("reason"), str):
                _add_issue(issues, "error", f"{path}.human_review_route.reason", "human_review_route.reason must be a string or null.")
    if "human_review_queue" in record:
        queue = record.get("human_review_queue")
        if not isinstance(queue, dict):
            _add_issue(issues, "error", f"{path}.human_review_queue", "human_review_queue must be an object.")
        else:
            if not isinstance(queue.get("required"), bool):
                _add_issue(issues, "error", f"{path}.human_review_queue.required", "human_review_queue.required must be boolean.")
            if not isinstance(queue.get("queue"), str) or not queue.get("queue"):
                _add_issue(issues, "error", f"{path}.human_review_queue.queue", "human_review_queue.queue must be a non-empty string.")
            if "route" in queue and queue.get("route") is not None and not isinstance(queue.get("route"), str):
                _add_issue(issues, "error", f"{path}.human_review_queue.route", "human_review_queue.route must be a string or null.")
            if "priority" in queue and queue.get("priority") not in {"none", "standard", "high", "critical"}:
                _add_issue(
                    issues,
                    "error",
                    f"{path}.human_review_queue.priority",
                    "human_review_queue.priority must be none, standard, high, or critical.",
                )
            triggers = queue.get("triggers")
            if not isinstance(triggers, list) or not all(isinstance(item, str) for item in triggers):
                _add_issue(issues, "error", f"{path}.human_review_queue.triggers", "human_review_queue.triggers must be an array of strings.")
            if "reason" in queue and queue.get("reason") is not None and not isinstance(queue.get("reason"), str):
                _add_issue(issues, "error", f"{path}.human_review_queue.reason", "human_review_queue.reason must be a string or null.")
    aix = record.get("aix")
    if aix is not None:
        if not isinstance(aix, dict):
            _add_issue(issues, "error", f"{path}.aix", "aix must be an object or null.")
        else:
            if "score" in aix and aix.get("score") is not None and not isinstance(aix.get("score"), (int, float)):
                _add_issue(issues, "error", f"{path}.aix.score", "aix.score must be numeric or null.")
            if "decision" in aix and aix.get("decision") is not None and not isinstance(aix.get("decision"), str):
                _add_issue(issues, "error", f"{path}.aix.decision", "aix.decision must be a string or null.")
            if "components" in aix and not isinstance(aix.get("components"), dict):
                _add_issue(issues, "error", f"{path}.aix.components", "aix.components must be an object.")
            if "hard_blockers" in aix and not isinstance(aix.get("hard_blockers"), list):
                _add_issue(issues, "error", f"{path}.aix.hard_blockers", "aix.hard_blockers must be an array.")

    for field in sorted(PROHIBITED_AUDIT_FIELDS & set(record)):
        _add_issue(issues, "error", f"{path}.{field}", "Raw sensitive field is not allowed in redacted audit records.")
    for finding in _audit_sensitive_findings(record, path=path):
        _add_issue(issues, "error", finding["path"], finding["message"])

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "issues": issues}


def validate_audit_records(records):
    issues = []
    if not isinstance(records, list):
        return {
            "valid": False,
            "errors": 1,
            "warnings": 0,
            "record_count": 0,
            "issues": [{"level": "error", "path": "$", "message": "Audit records must be a list."}],
        }
    for index, record in enumerate(records):
        report = validate_audit_record(record, path=f"$[{index}]")
        issues.extend(report["issues"])
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "record_count": len(records),
        "issues": issues,
    }


def validate_audit_jsonl(path):
    return validate_audit_records(load_jsonl(path))


def redaction_report(records, forbidden_terms=None):
    forbidden = [term for term in (forbidden_terms or []) if isinstance(term, str) and term]
    issues = []
    validation = validate_audit_records(records)
    issues.extend(validation["issues"])
    for index, record in enumerate(records if isinstance(records, list) else []):
        serialized = json.dumps(record, sort_keys=True, ensure_ascii=False)
        for term in forbidden:
            if term in serialized:
                _add_issue(issues, "error", f"$[{index}]", f"Forbidden raw term appears in audit record: {term!r}.")
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "redacted": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "record_count": len(records) if isinstance(records, list) else 0,
        "issues": issues,
    }


def validate_metrics_export(metrics_export):
    issues = []
    if not isinstance(metrics_export, dict):
        return {
            "valid": False,
            "errors": 1,
            "warnings": 0,
            "issues": [{"level": "error", "path": "$", "message": "Audit metrics export must be a JSON object."}],
        }
    if metrics_export.get("audit_metrics_export_version") != AUDIT_METRICS_EXPORT_VERSION:
        _add_issue(issues, "error", "$.audit_metrics_export_version", f"audit_metrics_export_version must be {AUDIT_METRICS_EXPORT_VERSION}.")
    if not isinstance(metrics_export.get("record_count"), int):
        _add_issue(issues, "error", "$.record_count", "record_count must be an integer.")
    if not isinstance(metrics_export.get("metrics"), dict):
        _add_issue(issues, "error", "$.metrics", "metrics must be an object.")
    if not isinstance(metrics_export.get("summary"), dict):
        _add_issue(issues, "error", "$.summary", "summary must be an object.")
    if not isinstance(metrics_export.get("unavailable_metrics"), list):
        _add_issue(issues, "error", "$.unavailable_metrics", "unavailable_metrics must be an array.")

    metrics = metrics_export.get("metrics", {}) if isinstance(metrics_export.get("metrics"), dict) else {}
    for required in (
        "audit_records_total",
        "decision_case_count",
        "allowed_case_count",
        "blocked_case_count",
        "deferred_case_count",
        "false_positive_case_count",
        "unresolved_case_count",
        "gate_decision_count",
        "recommended_action_count",
        "adapter_check_count",
        "human_review_rate",
        "refusal_defer_rate",
        "connector_failure_count",
        "evidence_freshness_failure_count",
        "drift_by_adapter_version_count",
    ):
        if required not in metrics:
            _add_issue(issues, "error", f"$.metrics.{required}", "Required audit metric is missing.")
    if "aix_score_average" in metrics and not isinstance(metrics.get("aix_score_average"), (int, float)):
        _add_issue(issues, "error", "$.metrics.aix_score_average", "aix_score_average must be numeric when present.")
    for numeric in ("human_review_rate", "refusal_defer_rate"):
        if numeric in metrics and not isinstance(metrics.get(numeric), (int, float)):
            _add_issue(issues, "error", f"$.metrics.{numeric}", f"{numeric} must be numeric.")

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "issues": issues}


def summarize_records(records):
    gate_decisions = {}
    recommended_actions = {}
    adapters = {}
    families = {}
    roles = {}
    violation_codes = {}
    record_types = {}
    execution_modes = {}
    shadow_routes = {}
    human_review_queues = {}
    human_review_triggers = {}
    connector_failures = {}
    evidence_freshness_failures = {}
    adapter_versions = {}
    latency_ms = []
    aix_scores = []
    aix_decisions = {}
    aix_hard_blockers = {}
    decision_cases = {
        "allowed": 0,
        "blocked": 0,
        "deferred": 0,
        "false_positive": 0,
        "unresolved": 0,
    }
    for record in records:
        _increment(decision_cases, _decision_case(record))
        record_type = record.get("record_type", "unknown")
        record_types[record_type] = record_types.get(record_type, 0) + 1
        execution_mode = record.get("execution_mode") or "enforce"
        execution_modes[execution_mode] = execution_modes.get(execution_mode, 0) + 1
        gate = record.get("gate_decision")
        if gate:
            gate_decisions[gate] = gate_decisions.get(gate, 0) + 1
        action = record.get("recommended_action")
        if action:
            recommended_actions[action] = recommended_actions.get(action, 0) + 1
        adapter = record.get("adapter") or record.get("adapter_id")
        if adapter:
            adapters[adapter] = adapters.get(adapter, 0) + 1
            version = record.get("adapter_version") or "unknown"
            adapter_version_counts = adapter_versions.setdefault(adapter, {})
            adapter_version_counts[version] = adapter_version_counts.get(version, 0) + 1
            for family in _adapter_families(adapter):
                families[family] = families.get(family, 0) + 1
            for role in _adapter_roles(adapter):
                roles[role] = roles.get(role, 0) + 1
        for code in record.get("violation_codes", []) or []:
            violation_codes[code] = violation_codes.get(code, 0) + 1
        review_queue = record.get("human_review_queue") if isinstance(record.get("human_review_queue"), dict) else {}
        if review_queue.get("required"):
            queue_name = review_queue.get("queue") or "human_review_queue"
            human_review_queues[queue_name] = human_review_queues.get(queue_name, 0) + 1
            for trigger in review_queue.get("triggers", []) or []:
                human_review_triggers[trigger] = human_review_triggers.get(trigger, 0) + 1
        if execution_mode == "shadow":
            shadow = record.get("shadow_observation") if isinstance(record.get("shadow_observation"), dict) else {}
            route = shadow.get("would_route") or shadow_route_from_action(record.get("recommended_action"), gate_decision=record.get("gate_decision"))
            if route:
                shadow_routes[route] = shadow_routes.get(route, 0) + 1
        for failure in record.get("connector_failures", []) or []:
            connector_failures[failure] = connector_failures.get(failure, 0) + 1
        for failure in record.get("evidence_freshness_failures", []) or []:
            evidence_freshness_failures[failure] = evidence_freshness_failures.get(failure, 0) + 1
        latency = record.get("latency_ms")
        if isinstance(latency, (int, float)) and latency >= 0:
            latency_ms.append(float(latency))
        aix = record.get("aix")
        if isinstance(aix, dict):
            score = aix.get("score")
            if isinstance(score, (int, float)):
                aix_scores.append(float(score))
            decision = aix.get("decision")
            if decision:
                aix_decisions[decision] = aix_decisions.get(decision, 0) + 1
            for blocker in aix.get("hard_blockers", []) or []:
                aix_hard_blockers[blocker] = aix_hard_blockers.get(blocker, 0) + 1

    summary = {
        "total": len(records),
        "record_types": record_types,
        "execution_modes": execution_modes,
        "gate_decisions": gate_decisions,
        "recommended_actions": recommended_actions,
        "decision_cases": dict(sorted(decision_cases.items())),
        "adapters": adapters,
        "families": families,
        "roles": roles,
        "violation_codes": dict(sorted(violation_codes.items(), key=lambda item: (-item[1], item[0]))),
        "human_review_queues": human_review_queues,
        "human_review_triggers": dict(sorted(human_review_triggers.items(), key=lambda item: (-item[1], item[0]))),
        "connector_failures": dict(sorted(connector_failures.items(), key=lambda item: (-item[1], item[0]))),
        "evidence_freshness_failures": dict(sorted(evidence_freshness_failures.items(), key=lambda item: (-item[1], item[0]))),
        "adapter_versions": {adapter: dict(sorted(versions.items())) for adapter, versions in sorted(adapter_versions.items())},
        "latency": _latency_stats(latency_ms),
    }
    if shadow_routes:
        summary["shadow"] = {
            "records": _sum_counts(shadow_routes),
            "would_routes": shadow_routes,
        }
    if aix_scores:
        summary["aix"] = {
            "average_score": round(sum(aix_scores) / len(aix_scores), 4),
            "min_score": round(min(aix_scores), 4),
            "max_score": round(max(aix_scores), 4),
            "score_distribution": _aix_score_distribution(aix_scores),
            "decisions": aix_decisions,
            "hard_blockers": dict(sorted(aix_hard_blockers.items(), key=lambda item: (-item[1], item[0]))),
        }
    return summary


def summarize_jsonl(path):
    return summarize_records(load_jsonl(path))


def _metric_key(prefix, value):
    safe = str(value).strip().replace(" ", "_").replace("/", "_")
    return f"{prefix}.{safe}" if safe else prefix


def _sum_counts(counts):
    return sum(value for value in counts.values() if isinstance(value, int))


def _canonical_adapter_id(adapter_id):
    aliases = {
        "support_reply": "crm_support_reply",
        "research_summary": "research_answer_grounding",
        "billing_reply": "invoice_billing_reply",
    }
    return aliases.get(adapter_id, adapter_id)


def _adapter_families(adapter_id):
    adapter_id = _canonical_adapter_id(adapter_id)
    families = adapter_gallery.adapter_families(adapter_id) if adapter_id else []
    return families or ["unclassified"]


def _adapter_roles(adapter_id):
    adapter_id = _canonical_adapter_id(adapter_id)
    roles = adapter_gallery.adapter_roles(adapter_id) if adapter_id else []
    return roles or ["unclassified"]


def _record_has_missing_evidence(record):
    codes = record.get("violation_codes", []) if isinstance(record, dict) else []
    for code in codes or []:
        text = str(code).lower()
        if "missing" in text and ("evidence" in text or "source" in text or "approval" in text):
            return True
        if text in {"missing_source", "missing_evidence", "unknown_source", "stale_evidence"}:
            return True
    return False


def _record_is_false_positive(record):
    if not isinstance(record, dict):
        return False
    for key in ("review_outcome", "audit_review", "labels", "review"):
        value = record.get(key)
        if value == "false_positive":
            return True
        if isinstance(value, dict) and value.get("false_positive") is True:
            return True
        if isinstance(value, dict) and value.get("outcome") == "false_positive":
            return True
    return False


def _decision_case(record):
    if not isinstance(record, dict):
        return "unresolved"
    action = record.get("recommended_action")
    gate = record.get("gate_decision")
    if _record_is_false_positive(record):
        return "false_positive"
    if action == "accept" and gate == "pass":
        return "allowed"
    if action == "defer":
        return "deferred"
    if gate == "fail" or action in {"ask", "refuse", "revise"}:
        return "blocked"
    return "unresolved"


def _rate(count, total):
    return round(count / total, 4) if total else 0.0


def _latency_stats(values):
    if not values:
        return {"count": 0, "average_ms": None, "min_ms": None, "max_ms": None, "p50_ms": None, "p95_ms": None, "buckets": {}}
    ordered = sorted(float(value) for value in values)

    def percentile(fraction):
        index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
        return round(ordered[index], 3)

    buckets = {
        "le_100ms": sum(1 for value in ordered if value <= 100),
        "le_250ms": sum(1 for value in ordered if value <= 250),
        "le_500ms": sum(1 for value in ordered if value <= 500),
        "le_1000ms": sum(1 for value in ordered if value <= 1000),
        "gt_1000ms": sum(1 for value in ordered if value > 1000),
    }
    return {
        "count": len(ordered),
        "average_ms": round(sum(ordered) / len(ordered), 3),
        "min_ms": round(ordered[0], 3),
        "max_ms": round(ordered[-1], 3),
        "p50_ms": percentile(0.50),
        "p95_ms": percentile(0.95),
        "buckets": buckets,
    }


def _aix_score_distribution(scores):
    buckets = {
        "lt_0_50": 0,
        "gte_0_50_lt_0_70": 0,
        "gte_0_70_lt_0_85": 0,
        "gte_0_85_lt_0_95": 0,
        "gte_0_95": 0,
    }
    for score in scores:
        if score < 0.50:
            buckets["lt_0_50"] += 1
        elif score < 0.70:
            buckets["gte_0_50_lt_0_70"] += 1
        elif score < 0.85:
            buckets["gte_0_70_lt_0_85"] += 1
        elif score < 0.95:
            buckets["gte_0_85_lt_0_95"] += 1
        else:
            buckets["gte_0_95"] += 1
    return buckets


def export_metrics(records, audit_log_path=None, created_at=None):
    """Export flat dashboard-friendly metrics from redacted audit records."""

    summary = summarize_records(records)
    metrics = {
        "audit_records_total": summary["total"],
        "gate_decision_count": _sum_counts(summary["gate_decisions"]),
        "recommended_action_count": _sum_counts(summary["recommended_actions"]),
        "decision_case_count": _sum_counts(summary.get("decision_cases", {})),
        "violation_code_count": _sum_counts(summary["violation_codes"]),
        "adapter_check_count": _sum_counts(summary["adapters"]),
        "family_check_count": _sum_counts(summary.get("families", {})),
        "role_check_count": _sum_counts(summary.get("roles", {})),
        "human_review_queue_count": _sum_counts(summary.get("human_review_queues", {})),
        "human_review_trigger_count": _sum_counts(summary.get("human_review_triggers", {})),
        "connector_failure_count": _sum_counts(summary.get("connector_failures", {})),
        "evidence_freshness_failure_count": _sum_counts(summary.get("evidence_freshness_failures", {})),
    }
    decision_cases = summary.get("decision_cases", {})
    metrics["allowed_case_count"] = int(decision_cases.get("allowed", 0))
    metrics["blocked_case_count"] = int(decision_cases.get("blocked", 0))
    metrics["deferred_case_count"] = int(decision_cases.get("deferred", 0))
    metrics["false_positive_case_count"] = int(decision_cases.get("false_positive", 0))
    metrics["unresolved_case_count"] = int(decision_cases.get("unresolved", 0))
    total = summary["total"]
    defer_count = summary["recommended_actions"].get("defer", 0)
    refuse_count = summary["recommended_actions"].get("refuse", 0)
    human_review_count = metrics["human_review_queue_count"]
    metrics["human_review_rate"] = _rate(human_review_count, total)
    metrics["defer_rate"] = _rate(defer_count, total)
    metrics["refusal_rate"] = _rate(refuse_count, total)
    metrics["refusal_defer_rate"] = _rate(refuse_count + defer_count, total)

    for record_type, count in summary["record_types"].items():
        metrics[_metric_key("audit_record_type_count", record_type)] = count
    for mode, count in summary["execution_modes"].items():
        metrics[_metric_key("execution_mode_count", mode)] = count
    for decision, count in summary["gate_decisions"].items():
        metrics[_metric_key("gate_decision_count", decision)] = count
    for action, count in summary["recommended_actions"].items():
        metrics[_metric_key("recommended_action_count", action)] = count
    for case, count in summary.get("decision_cases", {}).items():
        metrics[_metric_key("decision_case_count", case)] = count
    for adapter, count in summary["adapters"].items():
        metrics[_metric_key("adapter_check_count", adapter)] = count
        for family in _adapter_families(adapter):
            metrics[_metric_key("family_adapter_check_count", family)] = metrics.get(
                _metric_key("family_adapter_check_count", family),
                0,
            ) + count
        for role in _adapter_roles(adapter):
            metrics[_metric_key("role_adapter_check_count", role)] = metrics.get(
                _metric_key("role_adapter_check_count", role),
                0,
            ) + count
    for family, count in summary.get("families", {}).items():
        metrics[_metric_key("family_check_count", family)] = count
    for role, count in summary.get("roles", {}).items():
        metrics[_metric_key("role_check_count", role)] = count
    for code, count in summary["violation_codes"].items():
        metrics[_metric_key("violation_code_count", code)] = count
    for queue, count in summary.get("human_review_queues", {}).items():
        metrics[_metric_key("human_review_queue_count", queue)] = count
    for trigger, count in summary.get("human_review_triggers", {}).items():
        metrics[_metric_key("human_review_trigger_count", trigger)] = count
    for failure, count in summary.get("connector_failures", {}).items():
        metrics[_metric_key("connector_failure_count", failure)] = count
    for failure, count in summary.get("evidence_freshness_failures", {}).items():
        metrics[_metric_key("evidence_freshness_failure_count", failure)] = count
    drift_by_adapter_version = 0
    for adapter, versions in summary.get("adapter_versions", {}).items():
        distinct_versions = len(versions)
        metrics[_metric_key("adapter_version_distinct_count", adapter)] = distinct_versions
        if distinct_versions > 1:
            drift_by_adapter_version += 1
        for version, count in versions.items():
            metrics[_metric_key("adapter_version_check_count", f"{adapter}.{version}")] = count
    metrics["drift_by_adapter_version_count"] = drift_by_adapter_version

    shadow = summary.get("shadow", {})
    shadow_routes = shadow.get("would_routes", {}) if isinstance(shadow, dict) else {}
    metrics["shadow_records_total"] = int(shadow.get("records", 0)) if isinstance(shadow, dict) else 0
    metrics["shadow_would_action_count"] = _sum_counts(shadow_routes)
    for route in sorted(SHADOW_ROUTES):
        count = shadow_routes.get(route, 0)
        metrics[_metric_key("shadow_would_action_count", route)] = count
        metrics[f"shadow_would_{route}_count"] = count

    latency = summary.get("latency", {})
    unavailable_metrics = []
    if latency.get("count"):
        metrics["latency_count"] = latency["count"]
        metrics["latency_average_ms"] = latency["average_ms"]
        metrics["latency_min_ms"] = latency["min_ms"]
        metrics["latency_max_ms"] = latency["max_ms"]
        metrics["latency_p50_ms"] = latency["p50_ms"]
        metrics["latency_p95_ms"] = latency["p95_ms"]
        for bucket, count in latency.get("buckets", {}).items():
            metrics[_metric_key("latency_bucket_count", bucket)] = count
    else:
        unavailable_metrics.append("latency")
    aix = summary.get("aix")
    if aix:
        metrics["aix_score_average"] = aix["average_score"]
        metrics["aix_score_min"] = aix["min_score"]
        metrics["aix_score_max"] = aix["max_score"]
        metrics["aix_decision_count"] = _sum_counts(aix["decisions"])
        metrics["aix_hard_blocker_count"] = _sum_counts(aix["hard_blockers"])
        for bucket, count in aix.get("score_distribution", {}).items():
            metrics[_metric_key("aix_score_bucket_count", bucket)] = count
        for decision, count in aix["decisions"].items():
            metrics[_metric_key("aix_decision_count", decision)] = count
        for blocker, count in aix["hard_blockers"].items():
            metrics[_metric_key("aix_hard_blocker_count", blocker)] = count
    else:
        unavailable_metrics.extend(["aix_score_average", "aix_decision_count", "aix_hard_blocker_count"])

    payload = {
        "audit_metrics_export_version": AUDIT_METRICS_EXPORT_VERSION,
        "created_at": created_at or _utc_now(),
        "record_count": len(records),
        "metrics": dict(sorted(metrics.items())),
        "unavailable_metrics": sorted(unavailable_metrics),
        "summary": summary,
    }
    if audit_log_path:
        payload["audit_log_path"] = str(pathlib.Path(audit_log_path).resolve())
    return payload


def export_metrics_jsonl(audit_log_path, output_path=None, created_at=None):
    metrics = export_metrics(load_jsonl(audit_log_path), audit_log_path=audit_log_path, created_at=created_at)
    if output_path:
        path = pathlib.Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(metrics, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return metrics


def _record_adapter(record):
    return record.get("adapter") or record.get("adapter_id") or "unknown"


def _record_day(record):
    created_at = record.get("created_at")
    if not isinstance(created_at, str) or not created_at:
        return "unknown"
    return created_at[:10]


def _increment(target, key, count=1):
    if not key:
        return
    target[key] = target.get(key, 0) + count


def _aix_stats(scores):
    if not scores:
        return {"count": 0, "average": None, "min": None, "max": None}
    return {
        "count": len(scores),
        "average": round(sum(scores) / len(scores), 4),
        "min": round(min(scores), 4),
        "max": round(max(scores), 4),
    }


def _empty_breakdown_item(item_id):
    return {
        "id": item_id,
        "total": 0,
        "gate_decisions": {},
        "recommended_actions": {},
        "execution_modes": {},
        "violation_total": 0,
        "violation_codes": {},
        "aix_decisions": {},
        "aix_scores": [],
        "hard_blockers": {},
        "hard_blocker_total": 0,
        "human_review_escalations": 0,
        "evidence_missing": 0,
        "connector_failures": {},
        "connector_failure_total": 0,
        "evidence_freshness_failures": {},
        "evidence_freshness_failure_total": 0,
        "adapter_versions": {},
        "latency_ms": [],
        "shadow_routes": {},
        "shadow_records": 0,
        "shadow_would_block": 0,
        "shadow_would_intervene": 0,
    }


def _finalize_breakdown_item(item):
    scores = item.pop("aix_scores", [])
    latencies = item.pop("latency_ms", [])
    shadow_records = item.get("shadow_records", 0)
    item["aix"] = _aix_stats(scores)
    item["latency"] = _latency_stats(latencies)
    item["shadow_would_block_rate"] = round(item["shadow_would_block"] / shadow_records, 4) if shadow_records else 0.0
    item["shadow_would_intervene_rate"] = round(item["shadow_would_intervene"] / shadow_records, 4) if shadow_records else 0.0
    item["safety_intervention_rate"] = round(
        (item["total"] - item["recommended_actions"].get("accept", 0)) / item["total"],
        4,
    ) if item["total"] else 0.0
    item["adapter_usage"] = item["total"]
    item["revise_rate"] = round(item["recommended_actions"].get("revise", 0) / item["total"], 4) if item["total"] else 0.0
    item["defer_rate"] = round(item["recommended_actions"].get("defer", 0) / item["total"], 4) if item["total"] else 0.0
    item["refuse_rate"] = round(item["recommended_actions"].get("refuse", 0) / item["total"], 4) if item["total"] else 0.0
    item["human_review_escalation_rate"] = round(item["human_review_escalations"] / item["total"], 4) if item["total"] else 0.0
    item["evidence_missing_rate"] = round(item["evidence_missing"] / item["total"], 4) if item["total"] else 0.0
    item["connector_failure_rate"] = round(item["connector_failure_total"] / item["total"], 4) if item["total"] else 0.0
    item["evidence_freshness_failure_rate"] = round(item["evidence_freshness_failure_total"] / item["total"], 4) if item["total"] else 0.0
    item["adapter_version_drift"] = len(item["adapter_versions"]) > 1
    item["violation_codes"] = dict(sorted(item["violation_codes"].items(), key=lambda pair: (-pair[1], pair[0])))
    item["hard_blockers"] = dict(sorted(item["hard_blockers"].items(), key=lambda pair: (-pair[1], pair[0])))
    item["connector_failures"] = dict(sorted(item["connector_failures"].items(), key=lambda pair: (-pair[1], pair[0])))
    item["evidence_freshness_failures"] = dict(sorted(item["evidence_freshness_failures"].items(), key=lambda pair: (-pair[1], pair[0])))
    item["adapter_versions"] = dict(sorted(item["adapter_versions"].items()))
    return item


def dashboard_payload(records, audit_log_path=None, created_at=None):
    """Build dashboard-ready metrics from redacted audit records."""

    metrics_export = export_metrics(records, audit_log_path=audit_log_path, created_at=created_at)
    summary = metrics_export["summary"]
    metrics = metrics_export["metrics"]
    adapters = {}
    families = {}
    roles = {}
    trends = {}
    global_scores = []
    hard_blockers = {}
    hard_blocker_total = 0
    shadow_records = 0
    shadow_routes = {}
    shadow_would_block = 0
    shadow_would_intervene = 0

    for record in records:
        adapter_id = _record_adapter(record)
        day = _record_day(record)
        adapter = adapters.setdefault(adapter_id, _empty_breakdown_item(adapter_id))
        trend = trends.setdefault(day, _empty_breakdown_item(day))
        family_items = [
            families.setdefault(family, _empty_breakdown_item(family))
            for family in _adapter_families(adapter_id)
        ]
        role_items = [
            roles.setdefault(role, _empty_breakdown_item(role))
            for role in _adapter_roles(adapter_id)
        ]
        review_escalation = record.get("recommended_action") in {"ask", "defer", "refuse"}
        missing_evidence = _record_has_missing_evidence(record)
        breakdown_items = [adapter, trend, *family_items, *role_items]
        for item in breakdown_items:
            item["total"] += 1
            _increment(item["gate_decisions"], record.get("gate_decision"))
            _increment(item["recommended_actions"], record.get("recommended_action"))
            _increment(item["execution_modes"], record.get("execution_mode") or "enforce")
            item["violation_total"] += int(record.get("violation_count") or 0)
            if review_escalation:
                item["human_review_escalations"] += 1
            if missing_evidence:
                item["evidence_missing"] += 1
            for failure in record.get("connector_failures", []) or []:
                _increment(item["connector_failures"], failure)
                item["connector_failure_total"] += 1
            for failure in record.get("evidence_freshness_failures", []) or []:
                _increment(item["evidence_freshness_failures"], failure)
                item["evidence_freshness_failure_total"] += 1
            version = record.get("adapter_version") or "unknown"
            _increment(item["adapter_versions"], version)
            latency = record.get("latency_ms")
            if isinstance(latency, (int, float)) and latency >= 0:
                item["latency_ms"].append(float(latency))
            for code in record.get("violation_codes", []) or []:
                _increment(item["violation_codes"], code)
            aix = record.get("aix") if isinstance(record.get("aix"), dict) else {}
            score = aix.get("score")
            if isinstance(score, (int, float)):
                item["aix_scores"].append(float(score))
            _increment(item["aix_decisions"], aix.get("decision"))
            for blocker in aix.get("hard_blockers", []) or []:
                _increment(item["hard_blockers"], blocker)
                item["hard_blocker_total"] += 1

        aix = record.get("aix") if isinstance(record.get("aix"), dict) else {}
        score = aix.get("score")
        if isinstance(score, (int, float)):
            global_scores.append(float(score))
        for blocker in aix.get("hard_blockers", []) or []:
            _increment(hard_blockers, blocker)
            hard_blocker_total += 1

        if record.get("execution_mode") == "shadow":
            shadow_records += 1
            shadow = record.get("shadow_observation") if isinstance(record.get("shadow_observation"), dict) else {}
            route = shadow.get("would_route") or shadow_route_from_action(
                record.get("recommended_action"),
                gate_decision=record.get("gate_decision"),
            )
            _increment(shadow_routes, route)
            if route in {"defer", "refuse"}:
                shadow_would_block += 1
            if route in {"revise", "defer", "refuse"}:
                shadow_would_intervene += 1
            for item in breakdown_items:
                item["shadow_records"] += 1
                _increment(item["shadow_routes"], route)
                if route in {"defer", "refuse"}:
                    item["shadow_would_block"] += 1
                if route in {"revise", "defer", "refuse"}:
                    item["shadow_would_intervene"] += 1

    adapter_breakdown = [_finalize_breakdown_item(item) for _, item in sorted(adapters.items())]
    family_breakdown = [_finalize_breakdown_item(item) for _, item in sorted(families.items())]
    role_breakdown = [_finalize_breakdown_item(item) for _, item in sorted(roles.items())]
    trend_series = [_finalize_breakdown_item(item) for _, item in sorted(trends.items())]
    top_violations = [
        {"code": code, "count": count}
        for code, count in list(summary.get("violation_codes", {}).items())[:20]
    ]
    top_hard_blockers = [
        {"code": code, "count": count}
        for code, count in sorted(hard_blockers.items(), key=lambda pair: (-pair[1], pair[0]))[:20]
    ]
    return {
        "audit_dashboard_version": AUDIT_DASHBOARD_VERSION,
        "created_at": created_at or _utc_now(),
        "audit_log_path": str(pathlib.Path(audit_log_path).resolve()) if audit_log_path else None,
        "record_count": len(records),
        "cards": {
            "total_records": len(records),
            "gate_pass": summary.get("gate_decisions", {}).get("pass", 0),
            "gate_fail": summary.get("gate_decisions", {}).get("fail", 0),
            "accepted": summary.get("recommended_actions", {}).get("accept", 0),
            "revised": summary.get("recommended_actions", {}).get("revise", 0),
            "deferred": summary.get("recommended_actions", {}).get("defer", 0),
            "refused": summary.get("recommended_actions", {}).get("refuse", 0),
            "allowed_cases": summary.get("decision_cases", {}).get("allowed", 0),
            "blocked_cases": summary.get("decision_cases", {}).get("blocked", 0),
            "deferred_cases": summary.get("decision_cases", {}).get("deferred", 0),
            "false_positive_cases": summary.get("decision_cases", {}).get("false_positive", 0),
            "violation_total": metrics.get("violation_code_count", 0),
            "hard_blocker_total": hard_blocker_total,
            "human_review_rate": metrics.get("human_review_rate", 0.0),
            "refusal_defer_rate": metrics.get("refusal_defer_rate", 0.0),
            "latency_p95_ms": metrics.get("latency_p95_ms"),
            "connector_failure_total": metrics.get("connector_failure_count", 0),
            "evidence_freshness_failure_total": metrics.get("evidence_freshness_failure_count", 0),
            "adapter_version_drift": metrics.get("drift_by_adapter_version_count", 0),
            "shadow_records": shadow_records,
            "shadow_would_block_rate": round(shadow_would_block / shadow_records, 4) if shadow_records else 0.0,
            "shadow_would_intervene_rate": round(shadow_would_intervene / shadow_records, 4) if shadow_records else 0.0,
        },
        "aix": _aix_stats(global_scores),
        "latency": summary.get("latency", {}),
        "connector_failures": summary.get("connector_failures", {}),
        "evidence_freshness_failures": summary.get("evidence_freshness_failures", {}),
        "adapter_versions": summary.get("adapter_versions", {}),
        "gate_decisions": summary.get("gate_decisions", {}),
        "recommended_actions": summary.get("recommended_actions", {}),
        "decision_cases": summary.get("decision_cases", {}),
        "violation_trends": trend_series,
        "top_violations": top_violations,
        "hard_blockers": {
            "total": hard_blocker_total,
            "items": top_hard_blockers,
        },
        "adapter_breakdown": adapter_breakdown,
        "family_breakdown": family_breakdown,
        "role_breakdown": role_breakdown,
        "shadow_mode": {
            "records": shadow_records,
            "would_routes": shadow_routes,
            "would_block": shadow_would_block,
            "would_intervene": shadow_would_intervene,
            "would_block_rate": round(shadow_would_block / shadow_records, 4) if shadow_records else 0.0,
            "would_intervene_rate": round(shadow_would_intervene / shadow_records, 4) if shadow_records else 0.0,
        },
        "metrics_export": metrics_export,
    }


def dashboard_payload_jsonl(audit_log_path, created_at=None):
    return dashboard_payload(load_jsonl(audit_log_path), audit_log_path=audit_log_path, created_at=created_at)


def aix_drift_report(
    records,
    baseline_metrics=None,
    *,
    allowed_decisions=None,
    min_average_score=0.85,
    min_min_score=0.5,
    max_hard_blockers=0,
    created_at=None,
):
    metrics_export = export_metrics(records, created_at=created_at)
    metrics = metrics_export.get("metrics", {})
    allowed = set(allowed_decisions or {"accept", "revise"})
    issues = []

    average_score = metrics.get("aix_score_average")
    if not isinstance(average_score, (int, float)):
        _add_issue(issues, "error", "$.metrics.aix_score_average", "AIx average score is unavailable.")
    elif average_score < min_average_score:
        _add_issue(issues, "error", "$.metrics.aix_score_average", f"AIx average score {average_score} is below {min_average_score}.")

    min_score = metrics.get("aix_score_min")
    if not isinstance(min_score, (int, float)):
        _add_issue(issues, "error", "$.metrics.aix_score_min", "AIx minimum score is unavailable.")
    elif min_score < min_min_score:
        _add_issue(issues, "error", "$.metrics.aix_score_min", f"AIx minimum score {min_score} is below {min_min_score}.")

    hard_blockers = metrics.get("aix_hard_blocker_count", 0)
    if not isinstance(hard_blockers, int):
        _add_issue(issues, "error", "$.metrics.aix_hard_blocker_count", "AIx hard-blocker count is unavailable.")
    elif hard_blockers > max_hard_blockers:
        _add_issue(issues, "error", "$.metrics.aix_hard_blocker_count", f"AIx hard-blocker count {hard_blockers} exceeds {max_hard_blockers}.")

    decision_counts = {
        key.removeprefix("aix_decision_count."): value
        for key, value in metrics.items()
        if key.startswith("aix_decision_count.") and isinstance(value, int) and value > 0
    }
    unexpected = {decision: count for decision, count in decision_counts.items() if decision not in allowed}
    if unexpected:
        detail = ", ".join(f"{decision}={count}" for decision, count in sorted(unexpected.items()))
        _add_issue(issues, "error", "$.metrics.aix_decision_count", f"AIx decision drift includes disallowed decisions: {detail}.")

    baseline = baseline_metrics or {}
    if isinstance(baseline, dict) and "metrics" in baseline and isinstance(baseline.get("metrics"), dict):
        baseline = baseline["metrics"]
    comparisons = {}
    if isinstance(baseline, dict) and baseline:
        for key in ("aix_score_average", "aix_score_min", "aix_hard_blocker_count", "aix_decision_count.accept", "aix_decision_count.revise"):
            current = metrics.get(key)
            previous = baseline.get(key)
            if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
                comparisons[key] = {"current": current, "baseline": previous, "delta": round(current - previous, 4)}

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "audit_drift_report_version": AUDIT_DRIFT_REPORT_VERSION,
        "created_at": created_at or _utc_now(),
        "valid": errors == 0,
        "production_ready": errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "record_count": len(records),
        "thresholds": {
            "allowed_decisions": sorted(allowed),
            "min_average_score": min_average_score,
            "min_min_score": min_min_score,
            "max_hard_blockers": max_hard_blockers,
        },
        "metrics": metrics,
        "decision_counts": decision_counts,
        "baseline_comparisons": comparisons,
        "issues": issues,
    }


def aix_drift_report_jsonl(audit_log_path, output_path=None, baseline_metrics_path=None, created_at=None):
    baseline = None
    if baseline_metrics_path:
        with pathlib.Path(baseline_metrics_path).open(encoding="utf-8") as handle:
            baseline = json.load(handle)
    report = aix_drift_report(load_jsonl(audit_log_path), baseline_metrics=baseline, created_at=created_at)
    if output_path:
        path = pathlib.Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def reviewer_report_markdown(audit_log_path, metrics_export=None, drift_report=None, manifest=None, created_at=None):
    audit_path = pathlib.Path(audit_log_path)
    records = load_jsonl(audit_path)
    metrics_export = metrics_export or export_metrics(records, audit_log_path=audit_path, created_at=created_at)
    drift_report = drift_report or aix_drift_report(records, created_at=created_at)
    validation = validate_audit_records(records)
    redaction = redaction_report(records)
    summary = summarize_records(records)
    lines = [
        "# AANA Audit Reviewer Report",
        "",
        f"- Report version: {AUDIT_REVIEWER_REPORT_VERSION}",
        f"- Created at: {created_at or _utc_now()}",
        f"- Audit log: {audit_path}",
        f"- Records: {len(records)}",
        f"- Audit schema valid: {str(validation['valid']).lower()}",
        f"- Redaction check passed: {str(redaction['valid']).lower()}",
        f"- AIx drift valid: {str(drift_report['valid']).lower()}",
        "",
        "## Gate Summary",
    ]
    for key, value in sorted(summary.get("gate_decisions", {}).items()):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Recommended Actions")
    for key, value in sorted(summary.get("recommended_actions", {}).items()):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## AIx")
    aix = summary.get("aix", {})
    if aix:
        lines.extend(
            [
                f"- Average score: {aix.get('average_score')}",
                f"- Minimum score: {aix.get('min_score')}",
                f"- Maximum score: {aix.get('max_score')}",
            ]
        )
        for decision, count in sorted(aix.get("decisions", {}).items()):
            lines.append(f"- Decision {decision}: {count}")
        if aix.get("hard_blockers"):
            for blocker, count in sorted(aix.get("hard_blockers", {}).items()):
                lines.append(f"- Hard blocker {blocker}: {count}")
        else:
            lines.append("- Hard blockers: 0")
    else:
        lines.append("- AIx metrics unavailable.")
    lines.append("")
    lines.append("## Top Violations")
    for code, count in list(summary.get("violation_codes", {}).items())[:10]:
        lines.append(f"- {code}: {count}")
    if not summary.get("violation_codes"):
        lines.append("- None")
    lines.append("")
    lines.append("## Reviewer Checks")
    lines.append(f"- Metrics export version: {metrics_export.get('audit_metrics_export_version')}")
    if manifest:
        lines.append(f"- Manifest SHA-256: {manifest.get('manifest_sha256')}")
        lines.append(f"- Audit SHA-256: {manifest.get('audit_log_sha256')}")
    if drift_report.get("issues"):
        lines.append("- Drift issues:")
        for issue in drift_report["issues"]:
            lines.append(f"  - {issue['level']} {issue['path']}: {issue['message']}")
    else:
        lines.append("- Drift issues: none")
    return "\n".join(lines) + "\n"


def write_reviewer_report(audit_log_path, output_path, metrics_path=None, drift_report_path=None, manifest_path=None, created_at=None):
    metrics_export = None
    drift = None
    manifest = None
    if metrics_path and pathlib.Path(metrics_path).exists():
        with pathlib.Path(metrics_path).open(encoding="utf-8") as handle:
            metrics_export = json.load(handle)
    if drift_report_path and pathlib.Path(drift_report_path).exists():
        with pathlib.Path(drift_report_path).open(encoding="utf-8") as handle:
            drift = json.load(handle)
    if manifest_path and pathlib.Path(manifest_path).exists():
        manifest = load_integrity_manifest(manifest_path)
    markdown = reviewer_report_markdown(
        audit_log_path,
        metrics_export=metrics_export,
        drift_report=drift,
        manifest=manifest,
        created_at=created_at,
    )
    path = pathlib.Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return {
        "audit_reviewer_report_version": AUDIT_REVIEWER_REPORT_VERSION,
        "output_path": str(path),
        "audit_log_path": str(pathlib.Path(audit_log_path)),
        "bytes": len(markdown.encode("utf-8")),
    }


def create_integrity_manifest(audit_log_path, manifest_path=None, previous_manifest_path=None, created_at=None):
    audit_path = pathlib.Path(audit_log_path)
    records = load_jsonl(audit_path)
    audit_bytes = audit_path.read_bytes()
    manifest = {
        "audit_integrity_manifest_version": AUDIT_INTEGRITY_MANIFEST_VERSION,
        "created_at": created_at or _utc_now(),
        "audit_log_path": str(audit_path.resolve()),
        "audit_log_sha256": hashlib.sha256(audit_bytes).hexdigest(),
        "audit_log_size_bytes": len(audit_bytes),
        "record_count": len(records),
        "summary": summarize_records(records),
    }
    if previous_manifest_path:
        previous_path = pathlib.Path(previous_manifest_path)
        manifest["previous_manifest_path"] = str(previous_path.resolve())
        manifest["previous_manifest_sha256"] = _file_sha256(previous_path)
    manifest["manifest_sha256"] = _canonical_json_sha256(_manifest_payload(manifest))

    if manifest_path:
        output_path = pathlib.Path(manifest_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def load_integrity_manifest(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError("Audit integrity manifest must be a JSON object.")
    return manifest


def verify_integrity_manifest(path):
    manifest_path = pathlib.Path(path)
    issues = []
    manifest = load_integrity_manifest(manifest_path)
    stored_manifest_hash = manifest.get("manifest_sha256")
    computed_manifest_hash = _canonical_json_sha256(_manifest_payload(manifest))
    if stored_manifest_hash != computed_manifest_hash:
        issues.append(
            {
                "level": "error",
                "path": "$.manifest_sha256",
                "message": "Manifest self-hash does not match manifest contents.",
            }
        )

    audit_path_value = manifest.get("audit_log_path")
    audit_path = pathlib.Path(audit_path_value) if isinstance(audit_path_value, str) else None
    records = []
    if audit_path is None:
        issues.append({"level": "error", "path": "$.audit_log_path", "message": "Audit log path is missing."})
    elif not audit_path.exists():
        issues.append({"level": "error", "path": "$.audit_log_path", "message": "Audit log file does not exist."})
    else:
        audit_bytes = audit_path.read_bytes()
        audit_hash = hashlib.sha256(audit_bytes).hexdigest()
        if manifest.get("audit_log_sha256") != audit_hash:
            issues.append(
                {
                    "level": "error",
                    "path": "$.audit_log_sha256",
                    "message": "Audit log SHA-256 does not match the manifest.",
                }
            )
        if manifest.get("audit_log_size_bytes") != len(audit_bytes):
            issues.append(
                {
                    "level": "error",
                    "path": "$.audit_log_size_bytes",
                    "message": "Audit log byte size does not match the manifest.",
                }
            )
        try:
            records = load_jsonl(audit_path)
            if manifest.get("record_count") != len(records):
                issues.append(
                    {
                        "level": "error",
                        "path": "$.record_count",
                        "message": "Audit record count does not match the manifest.",
                    }
                )
        except ValueError as exc:
            issues.append({"level": "error", "path": "$.audit_log_path", "message": str(exc)})

    previous_path_value = manifest.get("previous_manifest_path")
    if previous_path_value:
        previous_path = pathlib.Path(previous_path_value)
        if not previous_path.exists():
            issues.append(
                {
                    "level": "error",
                    "path": "$.previous_manifest_path",
                    "message": "Previous manifest file does not exist.",
                }
            )
        elif manifest.get("previous_manifest_sha256") != _file_sha256(previous_path):
            issues.append(
                {
                    "level": "error",
                    "path": "$.previous_manifest_sha256",
                    "message": "Previous manifest SHA-256 does not match.",
                }
            )

    errors = sum(1 for issue in issues if issue["level"] == "error")
    return {
        "valid": errors == 0,
        "errors": errors,
        "issues": issues,
        "manifest_path": str(manifest_path),
        "audit_log_path": audit_path_value,
        "record_count": len(records),
        "manifest_sha256": stored_manifest_hash,
        "computed_manifest_sha256": computed_manifest_hash,
    }
