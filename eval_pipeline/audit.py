"""Redacted audit records for AANA gate decisions."""

import datetime
import hashlib
import json
import pathlib

from eval_pipeline import adapter_gallery


AUDIT_RECORD_VERSION = "0.1"
AUDIT_INTEGRITY_MANIFEST_VERSION = "0.1"
AUDIT_METRICS_EXPORT_VERSION = "0.1"
AUDIT_DRIFT_REPORT_VERSION = "0.1"
AUDIT_REVIEWER_REPORT_VERSION = "0.1"
AUDIT_DASHBOARD_VERSION = "0.1"
AUDIT_RECORD_TYPES = {"agent_check", "workflow_check", "workflow_batch_check"}
EXECUTION_MODES = {"enforce", "shadow"}
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
}


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


def _add_issue(issues, level, path, message):
    issues.append({"level": level, "path": path, "message": message})


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
    return "enforce"


def _add_execution_metadata(record, result, shadow_mode=False):
    mode = _execution_mode(result, shadow_mode=shadow_mode)
    record["execution_mode"] = mode
    if mode == "shadow":
        record["shadow_observation"] = shadow_observation(result)
    return record


def agent_audit_record(event, result, created_at=None, shadow_mode=False):
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
    record = {
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
    return _add_execution_metadata(record, result, shadow_mode=shadow_mode)


def workflow_audit_record(workflow_request, result, created_at=None, shadow_mode=False):
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
    record = {
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
    aix = record.get("aix")
    if aix is not None:
        if not isinstance(aix, dict):
            _add_issue(issues, "error", f"{path}.aix", "aix must be an object or null.")
        else:
            if "score" in aix and aix.get("score") is not None and not isinstance(aix.get("score"), (int, float)):
                _add_issue(issues, "error", f"{path}.aix.score", "aix.score must be numeric or null.")
            if "decision" in aix and aix.get("decision") is not None and not isinstance(aix.get("decision"), str):
                _add_issue(issues, "error", f"{path}.aix.decision", "aix.decision must be a string or null.")
            if "hard_blockers" in aix and not isinstance(aix.get("hard_blockers"), list):
                _add_issue(issues, "error", f"{path}.aix.hard_blockers", "aix.hard_blockers must be an array.")

    for field in sorted(PROHIBITED_AUDIT_FIELDS & set(record)):
        _add_issue(issues, "error", f"{path}.{field}", "Raw sensitive field is not allowed in redacted audit records.")

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
    for required in ("audit_records_total", "gate_decision_count", "recommended_action_count", "adapter_check_count"):
        if required not in metrics:
            _add_issue(issues, "error", f"$.metrics.{required}", "Required audit metric is missing.")
    if "aix_score_average" in metrics and not isinstance(metrics.get("aix_score_average"), (int, float)):
        _add_issue(issues, "error", "$.metrics.aix_score_average", "aix_score_average must be numeric when present.")

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
    aix_scores = []
    aix_decisions = {}
    aix_hard_blockers = {}
    for record in records:
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
            for family in _adapter_families(adapter):
                families[family] = families.get(family, 0) + 1
            for role in _adapter_roles(adapter):
                roles[role] = roles.get(role, 0) + 1
        for code in record.get("violation_codes", []) or []:
            violation_codes[code] = violation_codes.get(code, 0) + 1
        if execution_mode == "shadow":
            shadow = record.get("shadow_observation") if isinstance(record.get("shadow_observation"), dict) else {}
            route = shadow.get("would_route") or shadow_route_from_action(record.get("recommended_action"), gate_decision=record.get("gate_decision"))
            if route:
                shadow_routes[route] = shadow_routes.get(route, 0) + 1
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
        "adapters": adapters,
        "families": families,
        "roles": roles,
        "violation_codes": dict(sorted(violation_codes.items(), key=lambda item: (-item[1], item[0]))),
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


def export_metrics(records, audit_log_path=None, created_at=None):
    """Export flat dashboard-friendly metrics from redacted audit records."""

    summary = summarize_records(records)
    metrics = {
        "audit_records_total": summary["total"],
        "gate_decision_count": _sum_counts(summary["gate_decisions"]),
        "recommended_action_count": _sum_counts(summary["recommended_actions"]),
        "violation_code_count": _sum_counts(summary["violation_codes"]),
        "adapter_check_count": _sum_counts(summary["adapters"]),
        "family_check_count": _sum_counts(summary.get("families", {})),
        "role_check_count": _sum_counts(summary.get("roles", {})),
    }

    for record_type, count in summary["record_types"].items():
        metrics[_metric_key("audit_record_type_count", record_type)] = count
    for mode, count in summary["execution_modes"].items():
        metrics[_metric_key("execution_mode_count", mode)] = count
    for decision, count in summary["gate_decisions"].items():
        metrics[_metric_key("gate_decision_count", decision)] = count
    for action, count in summary["recommended_actions"].items():
        metrics[_metric_key("recommended_action_count", action)] = count
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

    shadow = summary.get("shadow", {})
    shadow_routes = shadow.get("would_routes", {}) if isinstance(shadow, dict) else {}
    metrics["shadow_records_total"] = int(shadow.get("records", 0)) if isinstance(shadow, dict) else 0
    metrics["shadow_would_action_count"] = _sum_counts(shadow_routes)
    for route in sorted(SHADOW_ROUTES):
        count = shadow_routes.get(route, 0)
        metrics[_metric_key("shadow_would_action_count", route)] = count
        metrics[f"shadow_would_{route}_count"] = count

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
        "shadow_routes": {},
        "shadow_records": 0,
        "shadow_would_block": 0,
        "shadow_would_intervene": 0,
    }


def _finalize_breakdown_item(item):
    scores = item.pop("aix_scores", [])
    shadow_records = item.get("shadow_records", 0)
    item["aix"] = _aix_stats(scores)
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
    item["violation_codes"] = dict(sorted(item["violation_codes"].items(), key=lambda pair: (-pair[1], pair[0])))
    item["hard_blockers"] = dict(sorted(item["hard_blockers"].items(), key=lambda pair: (-pair[1], pair[0])))
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
            "violation_total": metrics.get("violation_code_count", 0),
            "hard_blocker_total": hard_blocker_total,
            "shadow_records": shadow_records,
            "shadow_would_block_rate": round(shadow_would_block / shadow_records, 4) if shadow_records else 0.0,
            "shadow_would_intervene_rate": round(shadow_would_intervene / shadow_records, 4) if shadow_records else 0.0,
        },
        "aix": _aix_stats(global_scores),
        "gate_decisions": summary.get("gate_decisions", {}),
        "recommended_actions": summary.get("recommended_actions", {}),
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
