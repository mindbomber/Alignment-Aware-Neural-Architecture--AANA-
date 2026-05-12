"""Human-review queue export for normal AANA runtime audit records."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline import audit


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME_HUMAN_REVIEW_VERSION = "0.1"
RUNTIME_HUMAN_REVIEW_PACKET_TYPE = "aana_runtime_human_review_packet"
RUNTIME_HUMAN_REVIEW_EXPORT_TYPE = "aana_runtime_human_review_export"
DEFAULT_RUNTIME_HUMAN_REVIEW_QUEUE_PATH = ROOT / "eval_outputs" / "human_review" / "runtime-review-queue.jsonl"
DEFAULT_RUNTIME_HUMAN_REVIEW_SUMMARY_PATH = ROOT / "eval_outputs" / "human_review" / "runtime-review-summary.json"
DEFAULT_RUNTIME_HUMAN_REVIEW_CONFIG_PATH = ROOT / "examples" / "human_review_queue_export.json"
HUMAN_REVIEW_DECISIONS = (
    "approve",
    "reject",
    "request_revision",
    "request_retrieval",
    "ask_clarification",
    "defer",
)
REVIEW_ACTIONS = {"ask", "defer", "refuse"}
ALLOWED_RAW_METADATA_KEYS = {
    "raw_payload_logged",
    "raw_payload_storage",
    "raw_artifact_storage",
    "raw_private_content_allowed_in_audit",
}
PROHIBITED_PACKET_KEYS = set(audit.PROHIBITED_AUDIT_FIELDS) - ALLOWED_RAW_METADATA_KEYS


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_sha256(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _write_json(path: str | pathlib.Path, payload: dict[str, Any]) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: str | pathlib.Path, records: list[dict[str, Any]], *, append: bool = False) -> str:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with output.open(mode, encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    return str(output)


def _load_jsonl(path: str | pathlib.Path) -> list[dict[str, Any]]:
    return audit.load_jsonl(path)


def _source_identity(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": record.get("record_type"),
        "event_id": record.get("event_id"),
        "workflow_id": record.get("workflow_id"),
        "tool_name": record.get("tool_name"),
        "adapter": record.get("adapter") or record.get("adapter_id"),
        "adapter_version": record.get("adapter_version"),
        "execution_mode": record.get("execution_mode") or "enforce",
        "source_record_sha256": _canonical_sha256(record),
    }


def _aix_summary(record: dict[str, Any]) -> dict[str, Any]:
    aix = record.get("aix") if isinstance(record.get("aix"), dict) else {}
    return {
        "score": aix.get("score"),
        "decision": aix.get("decision"),
        "components": aix.get("components") if isinstance(aix.get("components"), dict) else {},
        "risk_tier": aix.get("risk_tier"),
        "beta": aix.get("beta"),
        "thresholds": aix.get("thresholds") if isinstance(aix.get("thresholds"), dict) else {},
        "hard_blockers": list(aix.get("hard_blockers", []) or []),
    }


def should_export_human_review_record(record: dict[str, Any], *, include_all: bool = False) -> bool:
    """Return whether a redacted audit record should become a review packet."""

    if include_all:
        return True
    queue = record.get("human_review_queue") if isinstance(record.get("human_review_queue"), dict) else {}
    if queue.get("required") is True:
        return True
    action = record.get("recommended_action")
    if action in REVIEW_ACTIONS:
        return True
    hard_blockers = record.get("hard_blockers") or []
    aix = record.get("aix") if isinstance(record.get("aix"), dict) else {}
    return bool(hard_blockers or aix.get("hard_blockers"))


def runtime_human_review_packet(record: dict[str, Any], *, created_at: str | None = None) -> dict[str, Any]:
    """Create an audit-safe human-review packet from one redacted audit record."""

    if not isinstance(record, dict):
        raise TypeError("Audit record must be a JSON object.")
    queue = record.get("human_review_queue") if isinstance(record.get("human_review_queue"), dict) else {}
    packet = {
        "runtime_human_review_version": RUNTIME_HUMAN_REVIEW_VERSION,
        "packet_type": RUNTIME_HUMAN_REVIEW_PACKET_TYPE,
        "created_at": created_at or _utc_now(),
        "status": "open",
        "review_queue": {
            "required": bool(queue.get("required")),
            "queue": queue.get("queue") or "human_review_queue",
            "route": queue.get("route"),
            "priority": queue.get("priority") or "standard",
            "triggers": list(queue.get("triggers", []) or []),
            "reason": queue.get("reason"),
        },
        "source": _source_identity(record),
        "decision_context": {
            "gate_decision": record.get("gate_decision"),
            "recommended_action": record.get("recommended_action"),
            "candidate_gate": record.get("candidate_gate"),
            "authorization_state": record.get("authorization_state"),
            "aix": _aix_summary(record),
            "hard_blockers": list(record.get("hard_blockers", []) or []),
            "missing_evidence": list(record.get("missing_evidence", []) or []),
            "violation_codes": list(record.get("violation_codes", []) or []),
            "connector_failures": list(record.get("connector_failures", []) or []),
            "evidence_freshness_failures": list(record.get("evidence_freshness_failures", []) or []),
        },
        "evidence_metadata": {
            "evidence_source_ids": list(record.get("evidence_source_ids", []) or []),
            "input_fingerprints": record.get("input_fingerprints", {}) if isinstance(record.get("input_fingerprints"), dict) else {},
            "audit_safe_log_event": record.get("audit_safe_log_event", {}) if isinstance(record.get("audit_safe_log_event"), dict) else {},
        },
        "reviewer_workflow": {
            "allowed_decisions": list(HUMAN_REVIEW_DECISIONS),
            "required_fields": ["reviewer_id", "decision", "reason", "decided_at"],
            "override_rule": "Reviewer overrides must be written back as redacted audit metadata and cannot bypass fail-closed runtime execution.",
        },
        "redaction": {
            "raw_prompt_logged": False,
            "raw_candidate_logged": False,
            "raw_evidence_text_logged": False,
            "raw_safe_response_logged": False,
        },
    }
    validation = validate_runtime_human_review_packet(packet)
    if not validation["valid"]:
        raise ValueError(f"Generated human-review packet is invalid: {validation['issues']}")
    return packet


def runtime_human_review_packets(
    records: list[dict[str, Any]],
    *,
    include_all: bool = False,
    created_at: str | None = None,
) -> list[dict[str, Any]]:
    return [
        runtime_human_review_packet(record, created_at=created_at)
        for record in records
        if should_export_human_review_record(record, include_all=include_all)
    ]


def _prohibited_key_findings(value: Any, *, path: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            is_fingerprint_metadata = ".input_fingerprints." in child_path
            raw_key = (
                key_text in PROHIBITED_PACKET_KEYS
                or key_text.startswith("raw_")
                or key_text.startswith("raw-")
                or bool(audit.PROHIBITED_AUDIT_KEY_PATTERN.search(key_text))
            )
            is_redaction_flag = ".redaction." in child_path
            if raw_key and not is_fingerprint_metadata and not is_redaction_flag and key_text not in ALLOWED_RAW_METADATA_KEYS:
                findings.append(_issue("error", child_path, "Human-review packets must not contain raw sensitive fields."))
            findings.extend(_prohibited_key_findings(child, path=child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_prohibited_key_findings(item, path=f"{path}[{index}]"))
    return findings


def validate_runtime_human_review_packet(packet: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(packet, dict):
        return {"valid": False, "errors": 1, "warnings": 0, "issues": [_issue("error", "$", "Packet must be a JSON object.")]}
    if packet.get("runtime_human_review_version") != RUNTIME_HUMAN_REVIEW_VERSION:
        issues.append(_issue("error", "$.runtime_human_review_version", f"Must be {RUNTIME_HUMAN_REVIEW_VERSION}."))
    if packet.get("packet_type") != RUNTIME_HUMAN_REVIEW_PACKET_TYPE:
        issues.append(_issue("error", "$.packet_type", f"Must be {RUNTIME_HUMAN_REVIEW_PACKET_TYPE}."))
    if packet.get("status") != "open":
        issues.append(_issue("error", "$.status", "Exported packets must start with status=open."))
    queue = packet.get("review_queue") if isinstance(packet.get("review_queue"), dict) else {}
    if not queue:
        issues.append(_issue("error", "$.review_queue", "review_queue is required."))
    elif not isinstance(queue.get("queue"), str) or not queue.get("queue"):
        issues.append(_issue("error", "$.review_queue.queue", "Queue name is required."))
    source = packet.get("source") if isinstance(packet.get("source"), dict) else {}
    if not source.get("source_record_sha256"):
        issues.append(_issue("error", "$.source.source_record_sha256", "Source record fingerprint is required."))
    context = packet.get("decision_context") if isinstance(packet.get("decision_context"), dict) else {}
    if not context:
        issues.append(_issue("error", "$.decision_context", "decision_context is required."))
    workflow = packet.get("reviewer_workflow") if isinstance(packet.get("reviewer_workflow"), dict) else {}
    decisions = workflow.get("allowed_decisions") if isinstance(workflow.get("allowed_decisions"), list) else []
    if set(decisions) != set(HUMAN_REVIEW_DECISIONS):
        issues.append(_issue("error", "$.reviewer_workflow.allowed_decisions", "Allowed reviewer decisions are incomplete."))
    redaction = packet.get("redaction") if isinstance(packet.get("redaction"), dict) else {}
    for key in ("raw_prompt_logged", "raw_candidate_logged", "raw_evidence_text_logged", "raw_safe_response_logged"):
        if redaction.get(key) is not False:
            issues.append(_issue("error", f"$.redaction.{key}", "Raw content logging must be disabled."))
    issues.extend(_prohibited_key_findings(packet))
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "issues": issues}


def validate_runtime_human_review_packets(packets: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(packets, list):
        return {"valid": False, "errors": 1, "warnings": 0, "packet_count": 0, "issues": [_issue("error", "$", "Packets must be a list.")]}
    for index, packet in enumerate(packets):
        report = validate_runtime_human_review_packet(packet)
        for issue in report["issues"]:
            issues.append(_issue(issue["level"], f"$[{index}]{issue['path'][1:]}", issue["message"]))
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "packet_count": len(packets), "issues": issues}


def load_runtime_human_review_queue(path: str | pathlib.Path) -> list[dict[str, Any]]:
    return _load_jsonl(path)


def human_review_export_config() -> dict[str, Any]:
    return {
        "runtime_human_review_version": RUNTIME_HUMAN_REVIEW_VERSION,
        "export_type": RUNTIME_HUMAN_REVIEW_EXPORT_TYPE,
        "source": "redacted_aana_runtime_audit_jsonl",
        "default_queue_path": "eval_outputs/human_review/runtime-review-queue.jsonl",
        "default_summary_path": "eval_outputs/human_review/runtime-review-summary.json",
        "include_records": "required_human_review_only",
        "allowed_reviewer_decisions": list(HUMAN_REVIEW_DECISIONS),
        "redaction": {
            "raw_prompt_logged": False,
            "raw_candidate_logged": False,
            "raw_evidence_text_logged": False,
            "raw_safe_response_logged": False,
            "private_records_logged": False,
        },
        "handoff_policy": {
            "status_on_export": "open",
            "override_rule": "Reviewer overrides must be written back as redacted audit metadata and cannot bypass fail-closed runtime execution.",
            "sla_owner": "customer_domain_owner",
        },
        "claim_boundary": "Human-review export readiness only; not production certification or go-live approval.",
    }


def validate_human_review_export_config(config: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(config, dict):
        return {"valid": False, "errors": 1, "warnings": 0, "issues": [_issue("error", "$", "Config must be a JSON object.")]}
    if config.get("runtime_human_review_version") != RUNTIME_HUMAN_REVIEW_VERSION:
        issues.append(_issue("error", "runtime_human_review_version", f"Must be {RUNTIME_HUMAN_REVIEW_VERSION}."))
    if config.get("export_type") != RUNTIME_HUMAN_REVIEW_EXPORT_TYPE:
        issues.append(_issue("error", "export_type", f"Must be {RUNTIME_HUMAN_REVIEW_EXPORT_TYPE}."))
    if config.get("source") != "redacted_aana_runtime_audit_jsonl":
        issues.append(_issue("error", "source", "Human-review export must use redacted AANA runtime audit JSONL."))
    if "not production certification" not in str(config.get("claim_boundary", "")).lower():
        issues.append(_issue("error", "claim_boundary", "Claim boundary must state this is not production certification."))
    redaction = config.get("redaction") if isinstance(config.get("redaction"), dict) else {}
    for key in ("raw_prompt_logged", "raw_candidate_logged", "raw_evidence_text_logged", "raw_safe_response_logged", "private_records_logged"):
        if redaction.get(key) is not False:
            issues.append(_issue("error", f"redaction.{key}", "Raw/private content logging must be disabled."))
    decisions = config.get("allowed_reviewer_decisions")
    if not isinstance(decisions, list) or set(decisions) != set(HUMAN_REVIEW_DECISIONS):
        issues.append(_issue("error", "allowed_reviewer_decisions", "Allowed reviewer decisions are incomplete."))
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "issues": issues}


def write_human_review_export_config(path: str | pathlib.Path = DEFAULT_RUNTIME_HUMAN_REVIEW_CONFIG_PATH) -> dict[str, Any]:
    config = human_review_export_config()
    _write_json(path, config)
    return {"config_path": str(path), "config": config, "validation": validate_human_review_export_config(config)}


def _summary_from_packets(
    packets: list[dict[str, Any]],
    *,
    audit_log_path: str | pathlib.Path,
    queue_path: str | pathlib.Path,
    created_at: str,
) -> dict[str, Any]:
    by_queue: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_action: dict[str, int] = {}
    by_adapter: dict[str, int] = {}
    hard_blockers: dict[str, int] = {}
    violations: dict[str, int] = {}
    for packet in packets:
        queue = packet.get("review_queue", {})
        context = packet.get("decision_context", {})
        source = packet.get("source", {})
        queue_name = queue.get("queue") or "human_review_queue"
        by_queue[queue_name] = by_queue.get(queue_name, 0) + 1
        priority = queue.get("priority") or "standard"
        by_priority[priority] = by_priority.get(priority, 0) + 1
        action = context.get("recommended_action") or "unknown"
        by_action[action] = by_action.get(action, 0) + 1
        adapter_id = source.get("adapter") or "unknown"
        by_adapter[adapter_id] = by_adapter.get(adapter_id, 0) + 1
        for blocker in context.get("hard_blockers", []) or []:
            hard_blockers[blocker] = hard_blockers.get(blocker, 0) + 1
        aix = context.get("aix") if isinstance(context.get("aix"), dict) else {}
        for blocker in aix.get("hard_blockers", []) or []:
            hard_blockers[blocker] = hard_blockers.get(blocker, 0) + 1
        for code in context.get("violation_codes", []) or []:
            violations[code] = violations.get(code, 0) + 1
    return {
        "runtime_human_review_version": RUNTIME_HUMAN_REVIEW_VERSION,
        "export_type": RUNTIME_HUMAN_REVIEW_EXPORT_TYPE,
        "created_at": created_at,
        "source_audit_log": str(audit_log_path),
        "queue_path": str(queue_path),
        "packet_count": len(packets),
        "redacted_records_only": True,
        "raw_payload_logged": False,
        "review_status": {"open": len(packets)},
        "by_queue": dict(sorted(by_queue.items())),
        "by_priority": dict(sorted(by_priority.items())),
        "by_recommended_action": dict(sorted(by_action.items())),
        "by_adapter": dict(sorted(by_adapter.items())),
        "hard_blockers": dict(sorted(hard_blockers.items(), key=lambda item: (-item[1], item[0]))),
        "violation_codes": dict(sorted(violations.items(), key=lambda item: (-item[1], item[0]))),
    }


def export_runtime_human_review_queue(
    audit_log_path: str | pathlib.Path,
    *,
    queue_path: str | pathlib.Path = DEFAULT_RUNTIME_HUMAN_REVIEW_QUEUE_PATH,
    summary_path: str | pathlib.Path | None = DEFAULT_RUNTIME_HUMAN_REVIEW_SUMMARY_PATH,
    include_all: bool = False,
    append: bool = False,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Export standalone human-review packets from a redacted AANA audit JSONL."""

    records = audit.load_jsonl(audit_log_path)
    source_validation = audit.validate_audit_records(records)
    if not source_validation["valid"]:
        raise ValueError(f"Source audit log is not valid redacted AANA audit JSONL: {source_validation['issues']}")
    source_raw_findings = []
    for index, record in enumerate(records):
        source_raw_findings.extend(_prohibited_key_findings(record, path=f"$[{index}]"))
    if source_raw_findings:
        raise ValueError(f"Source audit log contains raw sensitive fields: {source_raw_findings}")
    timestamp = created_at or _utc_now()
    packets = runtime_human_review_packets(records, include_all=include_all, created_at=timestamp)
    packet_validation = validate_runtime_human_review_packets(packets)
    if not packet_validation["valid"]:
        raise ValueError(f"Human-review export packets are invalid: {packet_validation['issues']}")
    _write_jsonl(queue_path, packets, append=append)
    summary = _summary_from_packets(packets, audit_log_path=audit_log_path, queue_path=queue_path, created_at=timestamp)
    if summary_path:
        _write_json(summary_path, summary)
    return {
        "runtime_human_review_version": RUNTIME_HUMAN_REVIEW_VERSION,
        "export_type": RUNTIME_HUMAN_REVIEW_EXPORT_TYPE,
        "valid": packet_validation["valid"],
        "source_validation": source_validation,
        "packet_validation": packet_validation,
        "audit_log_path": str(audit_log_path),
        "queue_path": str(queue_path),
        "summary_path": str(summary_path) if summary_path else None,
        "packet_count": len(packets),
        "include_all": include_all,
        "append": append,
        "summary": summary,
    }


__all__ = [
    "DEFAULT_RUNTIME_HUMAN_REVIEW_CONFIG_PATH",
    "DEFAULT_RUNTIME_HUMAN_REVIEW_QUEUE_PATH",
    "DEFAULT_RUNTIME_HUMAN_REVIEW_SUMMARY_PATH",
    "HUMAN_REVIEW_DECISIONS",
    "RUNTIME_HUMAN_REVIEW_EXPORT_TYPE",
    "RUNTIME_HUMAN_REVIEW_PACKET_TYPE",
    "RUNTIME_HUMAN_REVIEW_VERSION",
    "export_runtime_human_review_queue",
    "human_review_export_config",
    "load_runtime_human_review_queue",
    "runtime_human_review_packet",
    "runtime_human_review_packets",
    "should_export_human_review_record",
    "validate_human_review_export_config",
    "validate_runtime_human_review_packet",
    "validate_runtime_human_review_packets",
    "write_human_review_export_config",
]
