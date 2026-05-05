"""Evidence registry validation for AANA workflow checks."""

import datetime
import json
import pathlib


EVIDENCE_REGISTRY_VERSION = "0.1"


def load_registry(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        registry = json.load(handle)
    if not isinstance(registry, dict):
        raise ValueError("Evidence registry must be a JSON object.")
    return registry


def _add_issue(issues, level, path, message):
    issues.append({"level": level, "path": path, "message": message})


def _parse_time(value):
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _registry_sources(registry):
    sources = registry.get("sources", [])
    if not isinstance(sources, list):
        return None
    return {source.get("source_id"): source for source in sources if isinstance(source, dict)}


def validate_registry(registry):
    issues = []
    if not isinstance(registry, dict):
        return {
            "valid": False,
            "production_ready": False,
            "errors": 1,
            "warnings": 0,
            "issues": [{"level": "error", "path": "$", "message": "Evidence registry must be a JSON object."}],
        }

    sources = registry.get("sources")
    if not isinstance(sources, list) or not sources:
        _add_issue(issues, "error", "$.sources", "Evidence registry must include a non-empty sources array.")
    else:
        seen = set()
        for index, source in enumerate(sources):
            base = f"$.sources[{index}]"
            if not isinstance(source, dict):
                _add_issue(issues, "error", base, "Evidence source must be an object.")
                continue
            source_id = source.get("source_id")
            if not isinstance(source_id, str) or not source_id.strip():
                _add_issue(issues, "error", f"{base}.source_id", "source_id must be a non-empty string.")
            elif source_id in seen:
                _add_issue(issues, "error", f"{base}.source_id", f"Duplicate source_id: {source_id}.")
            else:
                seen.add(source_id)
            if not isinstance(source.get("owner"), str) or not source.get("owner", "").strip():
                _add_issue(issues, "error", f"{base}.owner", "owner must be a non-empty string.")
            for key in ("allowed_trust_tiers", "allowed_redaction_statuses"):
                if not isinstance(source.get(key), list) or not source.get(key):
                    _add_issue(issues, "error", f"{base}.{key}", f"{key} must be a non-empty list.")
            if "max_age_hours" in source and source.get("max_age_hours") is not None:
                if not isinstance(source.get("max_age_hours"), int) or source.get("max_age_hours") <= 0:
                    _add_issue(issues, "error", f"{base}.max_age_hours", "max_age_hours must be a positive integer or null.")

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "production_ready": errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
    }


def validate_workflow_evidence(workflow_request, registry, require_structured=False, now=None):
    registry_report = validate_registry(registry)
    issues = list(registry_report["issues"])
    source_map = _registry_sources(registry) or {}
    current_time = now or datetime.datetime.now(datetime.timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=datetime.timezone.utc)

    evidence_items = workflow_request.get("evidence", []) if isinstance(workflow_request, dict) else []
    if isinstance(evidence_items, str):
        evidence_items = [evidence_items]
    if not isinstance(evidence_items, list):
        _add_issue(issues, "error", "$.evidence", "Workflow evidence must be a string or array.")
        evidence_items = []

    checked = 0
    structured = 0
    for index, item in enumerate(evidence_items):
        path = f"$.evidence[{index}]"
        checked += 1
        if isinstance(item, str):
            level = "error" if require_structured else "warning"
            _add_issue(issues, level, path, "Evidence item is unstructured; production evidence should include source_id, trust_tier, redaction_status, retrieved_at, and text.")
            continue
        if not isinstance(item, dict):
            _add_issue(issues, "error", path, "Evidence item must be a string or object.")
            continue
        structured += 1
        source_id = item.get("source_id")
        source = source_map.get(source_id)
        if not source:
            _add_issue(issues, "error", f"{path}.source_id", f"Evidence source is not approved: {source_id!r}.")
            continue
        if source.get("enabled", True) is not True:
            _add_issue(issues, "error", f"{path}.source_id", f"Evidence source is disabled: {source_id!r}.")
        trust_tier = item.get("trust_tier")
        if trust_tier not in source.get("allowed_trust_tiers", []):
            _add_issue(issues, "error", f"{path}.trust_tier", f"trust_tier {trust_tier!r} is not allowed for source {source_id!r}.")
        redaction_status = item.get("redaction_status")
        if redaction_status not in source.get("allowed_redaction_statuses", []):
            _add_issue(issues, "error", f"{path}.redaction_status", f"redaction_status {redaction_status!r} is not allowed for source {source_id!r}.")
        retrieved_at = _parse_time(item.get("retrieved_at"))
        if retrieved_at is None:
            _add_issue(issues, "error", f"{path}.retrieved_at", "retrieved_at must be an ISO timestamp.")
        elif source.get("max_age_hours") is not None:
            age = current_time - retrieved_at
            max_age = datetime.timedelta(hours=source["max_age_hours"])
            if age > max_age:
                _add_issue(issues, "error", f"{path}.retrieved_at", f"Evidence is stale for source {source_id!r}; max_age_hours={source['max_age_hours']}.")

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "production_ready": errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "checked_evidence": checked,
        "structured_evidence": structured,
        "issues": issues,
    }


def validate_workflow_batch_evidence(batch_request, registry, require_structured=False, now=None):
    issues = []
    reports = []
    if not isinstance(batch_request, dict):
        _add_issue(issues, "error", "$", "Workflow batch request must be a JSON object.")
        return {
            "valid": False,
            "production_ready": False,
            "errors": 1,
            "warnings": 0,
            "reports": reports,
            "issues": issues,
        }

    requests = batch_request.get("requests", [])
    if not isinstance(requests, list):
        _add_issue(issues, "error", "$.requests", "Workflow batch request must include a requests array.")
        requests = []

    for index, workflow_request in enumerate(requests):
        report = validate_workflow_evidence(
            workflow_request,
            registry,
            require_structured=require_structured,
            now=now,
        )
        item_issues = [
            {**issue, "path": f"$.requests[{index}]{issue['path'][1:]}"}
            for issue in report.get("issues", [])
        ]
        reports.append(
            {
                "index": index,
                "workflow_id": workflow_request.get("workflow_id") if isinstance(workflow_request, dict) else None,
                "adapter": workflow_request.get("adapter") if isinstance(workflow_request, dict) else None,
                "valid": report["valid"],
                "production_ready": report["production_ready"],
                "errors": report["errors"],
                "warnings": report["warnings"],
                "checked_evidence": report["checked_evidence"],
                "structured_evidence": report["structured_evidence"],
                "issues": item_issues,
            }
        )
        issues.extend(item_issues)

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "production_ready": errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "reports": reports,
        "issues": issues,
    }
