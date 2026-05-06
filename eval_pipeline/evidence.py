"""Evidence object and registry validation for AANA workflow checks."""

import datetime
import json
import pathlib
from dataclasses import asdict, dataclass, field
from typing import Any


EVIDENCE_REGISTRY_VERSION = "0.1"
EVIDENCE_OBJECT_VERSION = "0.1"
DEFAULT_EVIDENCE_REGISTRY_PATH = pathlib.Path(__file__).resolve().parents[1] / "examples" / "evidence_registry.json"
ALLOWED_TRUST_TIERS = {"untrusted", "user_provided", "repository_fixture", "approved_fixture", "verified", "system"}
ALLOWED_REDACTION_STATUSES = {
    "public",
    "redacted",
    "partially_redacted",
    "unredacted",
    "synthetic",
    "not_applicable",
}


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


@dataclass(frozen=True)
class EvidenceObject:
    """Structured evidence with provenance for consequential AANA handoffs."""

    source_id: str
    trust_tier: str
    retrieved_at: str
    redaction_status: str
    text: str
    citation_url: str | None = None
    retrieval_url: str | None = None
    evidence_version: str = EVIDENCE_OBJECT_VERSION
    supports: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("EvidenceObject requires a dictionary.")
        return cls(
            evidence_version=data.get("evidence_version", EVIDENCE_OBJECT_VERSION),
            source_id=data.get("source_id", ""),
            trust_tier=data.get("trust_tier", ""),
            retrieved_at=data.get("retrieved_at", ""),
            redaction_status=data.get("redaction_status", ""),
            text=data.get("text", ""),
            citation_url=data.get("citation_url"),
            retrieval_url=data.get("retrieval_url"),
            supports=list(data.get("supports", [])) if isinstance(data.get("supports", []), list) else [],
            limits=list(data.get("limits", [])) if isinstance(data.get("limits", []), list) else [],
            metadata=dict(data.get("metadata", {})) if isinstance(data.get("metadata", {}), dict) else {},
        )

    def to_dict(self):
        return {key: value for key, value in asdict(self).items() if value not in (None, [], {})}


def evidence_object(
    *,
    source_id,
    trust_tier,
    retrieved_at,
    redaction_status,
    text,
    citation_url=None,
    retrieval_url=None,
    supports=None,
    limits=None,
    metadata=None,
):
    """Build a structured EvidenceObject dictionary."""

    return EvidenceObject(
        source_id=source_id,
        trust_tier=trust_tier,
        retrieved_at=retrieved_at,
        redaction_status=redaction_status,
        text=text,
        citation_url=citation_url,
        retrieval_url=retrieval_url,
        supports=list(supports or []),
        limits=list(limits or []),
        metadata=dict(metadata or {}),
    ).to_dict()


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_evidence_object(item, *, path="$.evidence", require_link=True, now=None, max_age_hours=None):
    """Validate one structured evidence object.

    Consequential handoffs require source ID, trust tier, freshness, redaction
    status, text, and either a citation URL or retrieval URL.
    """

    issues = []
    if not isinstance(item, dict):
        _add_issue(issues, "error", path, "Evidence object must be a JSON object.")
        return {
            "valid": False,
            "production_ready": False,
            "errors": 1,
            "warnings": 0,
            "issues": issues,
        }

    for key in ("source_id", "trust_tier", "retrieved_at", "redaction_status", "text"):
        if not _is_nonempty_string(item.get(key)):
            _add_issue(issues, "error", f"{path}.{key}", f"{key} must be a non-empty string.")

    trust_tier = item.get("trust_tier")
    if _is_nonempty_string(trust_tier) and trust_tier not in ALLOWED_TRUST_TIERS:
        _add_issue(issues, "error", f"{path}.trust_tier", f"trust_tier is not recognized: {trust_tier!r}.")

    redaction_status = item.get("redaction_status")
    if _is_nonempty_string(redaction_status) and redaction_status not in ALLOWED_REDACTION_STATUSES:
        _add_issue(
            issues,
            "error",
            f"{path}.redaction_status",
            f"redaction_status is not recognized: {redaction_status!r}.",
        )
    elif redaction_status == "unredacted":
        _add_issue(issues, "error", f"{path}.redaction_status", "Consequential handoff evidence must not be unredacted.")

    citation_url = item.get("citation_url")
    retrieval_url = item.get("retrieval_url")
    if require_link and not (_is_nonempty_string(citation_url) or _is_nonempty_string(retrieval_url)):
        _add_issue(
            issues,
            "error",
            path,
            "Evidence object must include citation_url or retrieval_url for provenance.",
        )

    if citation_url is not None and not _is_nonempty_string(citation_url):
        _add_issue(issues, "error", f"{path}.citation_url", "citation_url must be a non-empty string when present.")
    if retrieval_url is not None and not _is_nonempty_string(retrieval_url):
        _add_issue(issues, "error", f"{path}.retrieval_url", "retrieval_url must be a non-empty string when present.")

    retrieved_at = _parse_time(item.get("retrieved_at"))
    if retrieved_at is None:
        _add_issue(issues, "error", f"{path}.retrieved_at", "retrieved_at must be an ISO timestamp.")
    elif max_age_hours is not None:
        current_time = now or datetime.datetime.now(datetime.timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=datetime.timezone.utc)
        age = current_time.astimezone(datetime.timezone.utc) - retrieved_at
        if age > datetime.timedelta(hours=max_age_hours):
            _add_issue(issues, "error", f"{path}.retrieved_at", f"Evidence is stale; max_age_hours={max_age_hours}.")

    for key in ("supports", "limits"):
        if key in item and not isinstance(item.get(key), list):
            _add_issue(issues, "error", f"{path}.{key}", f"{key} must be an array when present.")
    if "metadata" in item and not isinstance(item.get("metadata"), dict):
        _add_issue(issues, "error", f"{path}.metadata", "metadata must be an object when present.")

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "production_ready": errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
    }


def validate_evidence_objects(items, *, path="$.evidence", require_link=True, now=None, max_age_hours=None):
    issues = []
    if not isinstance(items, list) or not items:
        _add_issue(issues, "error", path, "Evidence must be a non-empty array of structured evidence objects.")
        return {
            "valid": False,
            "production_ready": False,
            "errors": 1,
            "warnings": 0,
            "checked_evidence": 0,
            "issues": issues,
        }

    for index, item in enumerate(items):
        report = validate_evidence_object(
            item,
            path=f"{path}[{index}]",
            require_link=require_link,
            now=now,
            max_age_hours=max_age_hours,
        )
        issues.extend(report["issues"])

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "production_ready": errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "checked_evidence": len(items),
        "issues": issues,
    }


def _registry_sources(registry):
    sources = registry.get("sources", [])
    if not isinstance(sources, list):
        return None
    return {source.get("source_id"): source for source in sources if isinstance(source, dict)}


def default_evidence_registry():
    """Load the repository default production evidence registry."""

    return load_registry(DEFAULT_EVIDENCE_REGISTRY_PATH)


def evidence_source_contract(registry, source_id):
    """Resolve an evidence source contract by source_id."""

    source_map = _registry_sources(registry) or {}
    source = source_map.get(source_id)
    return dict(source) if isinstance(source, dict) else None


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


def _registry_for_binding(registry=None, registry_path=None):
    if isinstance(registry, dict):
        return registry
    if registry_path is not None:
        return load_registry(registry_path)
    return default_evidence_registry()


def validate_evidence_registry_binding(
    evidence_items,
    registry=None,
    *,
    registry_path=None,
    path="$.evidence",
    now=None,
    require_link=True,
):
    """Validate MI evidence objects against known production source contracts."""

    issues = []
    try:
        active_registry = _registry_for_binding(registry, registry_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _add_issue(issues, "error", "$.evidence_registry", f"Evidence registry could not be loaded: {exc}")
        return {
            "valid": False,
            "production_ready": False,
            "errors": 1,
            "warnings": 0,
            "checked_evidence": 0,
            "resolved_source_ids": [],
            "unresolved_source_ids": [],
            "source_contracts": [],
            "issues": issues,
        }

    registry_report = validate_registry(active_registry)
    issues.extend(registry_report["issues"])
    source_map = _registry_sources(active_registry) or {}
    items = evidence_items if isinstance(evidence_items, list) else []
    if not isinstance(evidence_items, list) or not evidence_items:
        _add_issue(issues, "error", path, "Evidence must be a non-empty array of structured evidence objects.")

    checked = 0
    resolved_source_ids = []
    unresolved_source_ids = []
    source_contracts = []
    current_time = now or datetime.datetime.now(datetime.timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=datetime.timezone.utc)

    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        checked += 1
        if not isinstance(item, dict):
            _add_issue(issues, "error", item_path, "Evidence object must be a JSON object.")
            continue

        source_id = item.get("source_id")
        source = source_map.get(source_id)
        if not isinstance(source, dict):
            unresolved_source_ids.append(str(source_id))
            _add_issue(issues, "error", f"{item_path}.source_id", f"Evidence source_id does not resolve to a known source contract: {source_id!r}.")
            object_report = validate_evidence_object(item, path=item_path, require_link=require_link, now=current_time)
            issues.extend(object_report["issues"])
            continue

        resolved_source_ids.append(str(source_id))
        source_contracts.append(
            {
                "source_id": source.get("source_id"),
                "owner": source.get("owner"),
                "enabled": source.get("enabled", True),
                "max_age_hours": source.get("max_age_hours"),
                "allowed_trust_tiers": list(source.get("allowed_trust_tiers", [])),
                "allowed_redaction_statuses": list(source.get("allowed_redaction_statuses", [])),
            }
        )

        if source.get("enabled", True) is not True:
            _add_issue(issues, "error", f"{item_path}.source_id", f"Evidence source is disabled: {source_id!r}.")

        max_age_hours = source.get("max_age_hours")
        object_report = validate_evidence_object(
            item,
            path=item_path,
            require_link=require_link,
            now=current_time,
            max_age_hours=max_age_hours,
        )
        issues.extend(object_report["issues"])

        trust_tier = item.get("trust_tier")
        if trust_tier not in source.get("allowed_trust_tiers", []):
            _add_issue(issues, "error", f"{item_path}.trust_tier", f"trust_tier {trust_tier!r} is not allowed by source contract {source_id!r}.")

        redaction_status = item.get("redaction_status")
        if redaction_status not in source.get("allowed_redaction_statuses", []):
            _add_issue(issues, "error", f"{item_path}.redaction_status", f"redaction_status {redaction_status!r} is not allowed by source contract {source_id!r}.")

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "production_ready": errors == 0 and warnings == 0,
        "errors": errors,
        "warnings": warnings,
        "checked_evidence": checked,
        "resolved_source_ids": sorted(set(resolved_source_ids)),
        "unresolved_source_ids": sorted(set(unresolved_source_ids)),
        "source_contracts": source_contracts,
        "issues": issues,
    }


def validate_handoff_evidence_binding(handoff, registry=None, *, registry_path=None, now=None):
    """Validate a MI handoff's evidence against the production evidence registry."""

    evidence_items = handoff.get("evidence") if isinstance(handoff, dict) else None
    return validate_evidence_registry_binding(
        evidence_items,
        registry,
        registry_path=registry_path,
        path="$.evidence",
        now=now,
        require_link=True,
    )


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
