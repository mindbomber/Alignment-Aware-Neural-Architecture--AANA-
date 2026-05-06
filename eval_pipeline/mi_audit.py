"""Redacted MI audit JSONL records for handoff decisions."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any


MI_AUDIT_RECORD_VERSION = "0.1"
MI_AUDIT_RECORD_TYPE = "mi_handoff_decision"
RAW_CONTENT_FIELDS = {
    "message",
    "evidence",
    "evidence_summary",
    "summary",
    "claims",
    "assumptions",
    "payload",
    "text",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _endpoint_summary(value: Any) -> dict[str, Any]:
    endpoint = value if isinstance(value, dict) else {}
    return {
        "id": endpoint.get("id"),
        "type": endpoint.get("type"),
        "adapter_id": endpoint.get("adapter_id"),
        "trust_tier": endpoint.get("trust_tier"),
    }


def _violation_codes(violations: Any) -> list[str]:
    codes = []
    for violation in violations if isinstance(violations, list) else []:
        if isinstance(violation, dict):
            code = violation.get("code") or violation.get("id")
            if code is not None:
                codes.append(str(code))
    return codes


def _aix_summary(block: Any) -> dict[str, Any]:
    aix = block if isinstance(block, dict) else {}
    return {
        "score": aix.get("score"),
        "decision": aix.get("decision"),
        "components": aix.get("components") if isinstance(aix.get("components"), dict) else {},
        "beta": aix.get("beta"),
        "thresholds": aix.get("thresholds") if isinstance(aix.get("thresholds"), dict) else {},
        "hard_blockers": list(aix.get("hard_blockers", [])) if isinstance(aix.get("hard_blockers"), list) else [],
    }


def _audit_summary_fingerprints(result: dict[str, Any]) -> dict[str, Any]:
    audit_summary = result.get("audit_summary") if isinstance(result.get("audit_summary"), dict) else {}
    handoff_aix = result.get("handoff_aix") if isinstance(result.get("handoff_aix"), dict) else {}
    return {
        "message": audit_summary.get("message_fingerprint") or handoff_aix.get("message_fingerprint"),
        "evidence": audit_summary.get("evidence_fingerprints", []),
        "audit_summary": _fingerprint(audit_summary),
    }


def mi_audit_record(result: dict[str, Any], *, created_at: str | None = None, workflow_id: str | None = None) -> dict[str, Any]:
    """Create a redacted audit record for one MI handoff result."""

    result = result if isinstance(result, dict) else {}
    audit_summary = result.get("audit_summary") if isinstance(result.get("audit_summary"), dict) else {}
    aix_summary = _aix_summary(result.get("aix"))
    handoff_aix_summary = _aix_summary(result.get("handoff_aix"))
    record = {
        "mi_audit_record_version": MI_AUDIT_RECORD_VERSION,
        "created_at": created_at or _utc_now(),
        "record_type": MI_AUDIT_RECORD_TYPE,
        "workflow_id": workflow_id,
        "handoff_id": result.get("handoff_id") or audit_summary.get("handoff_id"),
        "boundary_type": result.get("boundary_type"),
        "boundary_supported": result.get("boundary_supported"),
        "sender": _endpoint_summary(result.get("sender")),
        "recipient": _endpoint_summary(result.get("recipient")),
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "aix": aix_summary,
        "handoff_aix": handoff_aix_summary,
        "hard_blockers": sorted(set(aix_summary.get("hard_blockers", []) + handoff_aix_summary.get("hard_blockers", []))),
        "violation_count": len(result.get("violations", [])) if isinstance(result.get("violations"), list) else 0,
        "violation_codes": _violation_codes(result.get("violations")),
        "fingerprints": _audit_summary_fingerprints(result),
    }
    record["record_fingerprint"] = _fingerprint(record)
    return record


def mi_audit_records(
    workflow_result: list[dict[str, Any]] | dict[str, Any],
    *,
    created_at: str | None = None,
    workflow_id: str | None = None,
) -> list[dict[str, Any]]:
    """Create redacted audit records for MI handoff results."""

    if isinstance(workflow_result, dict) and isinstance(workflow_result.get("results"), list):
        results = [item for item in workflow_result["results"] if isinstance(item, dict)]
        workflow = workflow_id
        if workflow is None:
            workflow_aix = workflow_result.get("workflow_aix")
            workflow = workflow_aix.get("workflow_id") if isinstance(workflow_aix, dict) else None
    elif isinstance(workflow_result, list):
        results = [item for item in workflow_result if isinstance(item, dict)]
        workflow = workflow_id
    else:
        results = []
        workflow = workflow_id
    return [mi_audit_record(item, created_at=created_at, workflow_id=workflow) for item in results]


def append_mi_audit_jsonl(path: str | pathlib.Path, records: dict[str, Any] | list[dict[str, Any]]) -> str:
    """Append one or more redacted MI audit records to JSONL."""

    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = records if isinstance(records, list) else [records]
    with output_path.open("a", encoding="utf-8") as handle:
        for record in rows:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    return str(output_path)


def load_mi_audit_jsonl(path: str | pathlib.Path) -> list[dict[str, Any]]:
    records = []
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid MI audit JSONL record at line {line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"MI audit JSONL record at line {line_number} must be an object.")
            records.append(record)
    return records


def validate_mi_audit_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate that an MI audit record keeps only redacted decision metadata."""

    issues = []
    if not isinstance(record, dict):
        return {"valid": False, "issues": [{"path": "$", "message": "MI audit record must be an object."}]}
    if record.get("mi_audit_record_version") != MI_AUDIT_RECORD_VERSION:
        issues.append({"path": "$.mi_audit_record_version", "message": f"Must be {MI_AUDIT_RECORD_VERSION}."})
    if record.get("record_type") != MI_AUDIT_RECORD_TYPE:
        issues.append({"path": "$.record_type", "message": f"Must be {MI_AUDIT_RECORD_TYPE}."})
    for field in ("sender", "recipient", "aix", "handoff_aix", "fingerprints"):
        if not isinstance(record.get(field), dict):
            issues.append({"path": f"$.{field}", "message": f"{field} must be an object."})
    for field in ("hard_blockers", "violation_codes"):
        if not isinstance(record.get(field), list):
            issues.append({"path": f"$.{field}", "message": f"{field} must be an array."})
    for raw_field in RAW_CONTENT_FIELDS:
        if raw_field in record:
            issues.append({"path": f"$.{raw_field}", "message": "Raw MI content field is not allowed in audit records."})
    return {"valid": not issues, "issues": issues}


def validate_mi_audit_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    issues = []
    for index, record in enumerate(records if isinstance(records, list) else []):
        report = validate_mi_audit_record(record)
        for issue in report["issues"]:
            issues.append({"path": f"$[{index}]{issue['path'][1:]}", "message": issue["message"]})
    if not isinstance(records, list):
        issues.append({"path": "$", "message": "MI audit records must be a list."})
    return {"valid": not issues, "issues": issues, "record_count": len(records) if isinstance(records, list) else 0}


__all__ = [
    "MI_AUDIT_RECORD_TYPE",
    "MI_AUDIT_RECORD_VERSION",
    "append_mi_audit_jsonl",
    "load_mi_audit_jsonl",
    "mi_audit_record",
    "mi_audit_records",
    "validate_mi_audit_record",
    "validate_mi_audit_records",
]
