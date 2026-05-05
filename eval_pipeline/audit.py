"""Redacted audit records for AANA gate decisions."""

import datetime
import hashlib
import json
import pathlib


AUDIT_RECORD_VERSION = "0.1"


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


def agent_audit_record(event, result, created_at=None):
    """Create a redacted audit record for an agent event check.

    The record intentionally excludes raw request, candidate, evidence, and
    safe-response text. Use the fingerprints to correlate records with stored
    secure artifacts when a deployment has a reviewed audit store.
    """

    evidence = event.get("available_evidence", []) if isinstance(event, dict) else []
    if not isinstance(evidence, list):
        evidence = []
    candidate = None
    if isinstance(event, dict):
        candidate = event.get("candidate_action")
        if candidate is None:
            candidate = event.get("candidate_answer")
        if candidate is None:
            candidate = event.get("draft_response")

    violations = result.get("violations", []) if isinstance(result, dict) else []
    return {
        "audit_record_version": AUDIT_RECORD_VERSION,
        "created_at": created_at or _utc_now(),
        "record_type": "agent_check",
        "event_version": event.get("event_version") if isinstance(event, dict) else None,
        "event_id": event.get("event_id") if isinstance(event, dict) else None,
        "agent": result.get("agent") if isinstance(result, dict) else None,
        "adapter_id": result.get("adapter_id") if isinstance(result, dict) else None,
        "workflow": result.get("workflow") if isinstance(result, dict) else None,
        "gate_decision": result.get("gate_decision") if isinstance(result, dict) else None,
        "recommended_action": result.get("recommended_action") if isinstance(result, dict) else None,
        "candidate_gate": result.get("candidate_gate") if isinstance(result, dict) else None,
        "violation_count": len(violations),
        "violation_codes": _violation_codes(violations),
        "violation_severities": _violation_severities(violations),
        "allowed_actions": list(event.get("allowed_actions", [])) if isinstance(event, dict) else [],
        "input_fingerprints": {
            "user_request": _fingerprint(event.get("user_request") or event.get("prompt")) if isinstance(event, dict) else None,
            "candidate": _fingerprint(candidate),
            "evidence": _fingerprint_list(evidence),
            "safe_response": _fingerprint(result.get("safe_response")) if isinstance(result, dict) else None,
        },
    }


def workflow_audit_record(workflow_request, result, created_at=None):
    """Create a redacted audit record for a Workflow Contract check."""

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
    return {
        "audit_record_version": AUDIT_RECORD_VERSION,
        "created_at": created_at or _utc_now(),
        "record_type": "workflow_check",
        "contract_version": workflow_request.get("contract_version") if isinstance(workflow_request, dict) else None,
        "workflow_id": result.get("workflow_id") if isinstance(result, dict) else None,
        "adapter": result.get("adapter") if isinstance(result, dict) else None,
        "workflow": result.get("workflow") if isinstance(result, dict) else None,
        "gate_decision": result.get("gate_decision") if isinstance(result, dict) else None,
        "recommended_action": result.get("recommended_action") if isinstance(result, dict) else None,
        "candidate_gate": result.get("candidate_gate") if isinstance(result, dict) else None,
        "violation_count": len(violations),
        "violation_codes": _violation_codes(violations),
        "violation_severities": _violation_severities(violations),
        "allowed_actions": list(workflow_request.get("allowed_actions", [])) if isinstance(workflow_request, dict) else [],
        "constraint_count": len(constraints),
        "evidence_count": len(evidence),
        "input_fingerprints": {
            "request": _fingerprint(workflow_request.get("request")) if isinstance(workflow_request, dict) else None,
            "candidate": _fingerprint(workflow_request.get("candidate")) if isinstance(workflow_request, dict) else None,
            "evidence": _fingerprint_list(evidence),
            "constraints": _fingerprint_list(constraints),
            "output": _fingerprint(result.get("output")) if isinstance(result, dict) else None,
        },
    }


def append_jsonl(path, record):
    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    return str(output_path)


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


def summarize_records(records):
    gate_decisions = {}
    recommended_actions = {}
    adapters = {}
    violation_codes = {}
    record_types = {}
    for record in records:
        record_type = record.get("record_type", "unknown")
        record_types[record_type] = record_types.get(record_type, 0) + 1
        gate = record.get("gate_decision")
        if gate:
            gate_decisions[gate] = gate_decisions.get(gate, 0) + 1
        action = record.get("recommended_action")
        if action:
            recommended_actions[action] = recommended_actions.get(action, 0) + 1
        adapter = record.get("adapter") or record.get("adapter_id")
        if adapter:
            adapters[adapter] = adapters.get(adapter, 0) + 1
        for code in record.get("violation_codes", []) or []:
            violation_codes[code] = violation_codes.get(code, 0) + 1

    return {
        "total": len(records),
        "record_types": record_types,
        "gate_decisions": gate_decisions,
        "recommended_actions": recommended_actions,
        "adapters": adapters,
        "violation_codes": dict(sorted(violation_codes.items(), key=lambda item: (-item[1], item[0]))),
    }


def summarize_jsonl(path):
    return summarize_records(load_jsonl(path))
