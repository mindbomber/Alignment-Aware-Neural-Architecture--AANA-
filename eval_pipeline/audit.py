"""Redacted audit records for AANA gate decisions."""

import datetime
import hashlib
import json
import pathlib


AUDIT_RECORD_VERSION = "0.1"
AUDIT_INTEGRITY_MANIFEST_VERSION = "0.1"
AUDIT_METRICS_EXPORT_VERSION = "0.1"


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
        "aix": _aix_summary(result),
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
        "aix": _aix_summary(result),
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


def summarize_records(records):
    gate_decisions = {}
    recommended_actions = {}
    adapters = {}
    violation_codes = {}
    record_types = {}
    aix_scores = []
    aix_decisions = {}
    aix_hard_blockers = {}
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
        "gate_decisions": gate_decisions,
        "recommended_actions": recommended_actions,
        "adapters": adapters,
        "violation_codes": dict(sorted(violation_codes.items(), key=lambda item: (-item[1], item[0]))),
    }
    if aix_scores:
        summary["aix"] = {
            "average_score": round(sum(aix_scores) / len(aix_scores), 4),
            "min_score": round(min(aix_scores), 4),
            "max_score": round(max(aix_scores), 4),
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


def export_metrics(records, audit_log_path=None, created_at=None):
    """Export flat dashboard-friendly metrics from redacted audit records."""

    summary = summarize_records(records)
    metrics = {
        "audit_records_total": summary["total"],
        "gate_decision_count": _sum_counts(summary["gate_decisions"]),
        "recommended_action_count": _sum_counts(summary["recommended_actions"]),
        "violation_code_count": _sum_counts(summary["violation_codes"]),
        "adapter_check_count": _sum_counts(summary["adapters"]),
    }

    for record_type, count in summary["record_types"].items():
        metrics[_metric_key("audit_record_type_count", record_type)] = count
    for decision, count in summary["gate_decisions"].items():
        metrics[_metric_key("gate_decision_count", decision)] = count
    for action, count in summary["recommended_actions"].items():
        metrics[_metric_key("recommended_action_count", action)] = count
    for adapter, count in summary["adapters"].items():
        metrics[_metric_key("adapter_check_count", adapter)] = count
    for code, count in summary["violation_codes"].items():
        metrics[_metric_key("violation_code_count", code)] = count

    unavailable_metrics = ["latency"]
    aix = summary.get("aix")
    if aix:
        metrics["aix_score_average"] = aix["average_score"]
        metrics["aix_score_min"] = aix["min_score"]
        metrics["aix_score_max"] = aix["max_score"]
        metrics["aix_decision_count"] = _sum_counts(aix["decisions"])
        metrics["aix_hard_blocker_count"] = _sum_counts(aix["hard_blockers"])
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
