"""Contract freeze inventory and compatibility checks for AANA public surfaces."""

import json
import pathlib

from eval_pipeline import agent_api, agent_contract, audit, aix, evidence, workflow_contract
from scripts import validate_adapter, validate_adapter_gallery


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT_FREEZE_VERSION = "0.1"
CONTRACT_STATUS = "frozen"


EVIDENCE_OBJECT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/evidence-object.schema.json",
    "title": "AANA Evidence Object",
    "description": "A structured evidence item supplied to workflow or agent checks.",
    "type": "object",
    "required": ["text"],
    "properties": {
        "text": {"type": "string", "minLength": 1},
        "source_id": {"type": "string"},
        "retrieved_at": {"type": "string"},
        "trust_tier": {"type": "string"},
        "redaction_status": {"type": "string"},
    },
    "additionalProperties": True,
}


AUDIT_RECORD_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/audit-record.schema.json",
    "title": "AANA Redacted Audit Record",
    "description": "A redacted audit record for an agent or workflow gate decision.",
    "type": "object",
    "required": ["audit_record_version", "created_at", "record_type", "gate_decision", "recommended_action", "input_fingerprints"],
    "properties": {
        "audit_record_version": {"type": "string", "examples": [audit.AUDIT_RECORD_VERSION]},
        "created_at": {"type": "string"},
        "record_type": {"type": "string", "enum": ["agent_check", "workflow_check"]},
        "event_version": {"type": ["string", "null"]},
        "contract_version": {"type": ["string", "null"]},
        "adapter_id": {"type": ["string", "null"]},
        "adapter": {"type": ["string", "null"]},
        "gate_decision": {"type": ["string", "null"], "enum": agent_contract.GATE_DECISIONS + [None]},
        "recommended_action": {"type": ["string", "null"], "enum": agent_contract.ALLOWED_ACTIONS + [None]},
        "candidate_gate": {"type": ["string", "null"]},
        "aix": {"type": ["object", "null"]},
        "violation_count": {"type": "integer"},
        "violation_codes": {"type": "array", "items": {"type": "string"}},
        "input_fingerprints": {"type": "object"},
    },
    "additionalProperties": True,
}


AUDIT_METRICS_EXPORT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/audit-metrics-export.schema.json",
    "title": "AANA Audit Metrics Export",
    "description": "Flat metrics generated from redacted AANA audit records.",
    "type": "object",
    "required": ["audit_metrics_export_version", "created_at", "record_count", "metrics", "summary", "unavailable_metrics"],
    "properties": {
        "audit_metrics_export_version": {"type": "string", "examples": [audit.AUDIT_METRICS_EXPORT_VERSION]},
        "created_at": {"type": "string"},
        "record_count": {"type": "integer"},
        "metrics": {"type": "object"},
        "summary": {"type": "object"},
        "unavailable_metrics": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": True,
}


AUDIT_INTEGRITY_MANIFEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/audit-integrity-manifest.schema.json",
    "title": "AANA Audit Integrity Manifest",
    "description": "SHA-256 manifest for a local redacted audit JSONL file.",
    "type": "object",
    "required": [
        "audit_integrity_manifest_version",
        "created_at",
        "audit_log_path",
        "audit_log_sha256",
        "audit_log_size_bytes",
        "record_count",
        "summary",
        "manifest_sha256",
    ],
    "properties": {
        "audit_integrity_manifest_version": {"type": "string", "examples": [audit.AUDIT_INTEGRITY_MANIFEST_VERSION]},
        "created_at": {"type": "string"},
        "audit_log_path": {"type": "string"},
        "audit_log_sha256": {"type": "string"},
        "audit_log_size_bytes": {"type": "integer"},
        "record_count": {"type": "integer"},
        "summary": {"type": "object"},
        "manifest_sha256": {"type": "string"},
    },
    "additionalProperties": True,
}


ADAPTER_CONTRACT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/adapter-contract.schema.json",
    "title": "AANA Adapter Contract",
    "description": "The stable top-level contract for executable AANA adapter JSON files.",
    "type": "object",
    "required": ["adapter_name", "version", "domain", "failure_modes", "constraints", "correction_policy", "evaluation"],
    "properties": {
        "adapter_name": {"type": "string"},
        "version": {"type": "string"},
        "domain": {"type": "object"},
        "failure_modes": {"type": "array"},
        "constraints": {"type": "array"},
        "correction_policy": {"type": "object"},
        "evaluation": {"type": "object"},
        "aix": {"type": "object"},
        "production_readiness": {"type": "object"},
    },
    "additionalProperties": True,
}


EVIDENCE_REGISTRY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/evidence-registry.schema.json",
    "title": "AANA Evidence Registry",
    "description": "Registry of approved evidence sources and freshness/redaction rules.",
    "type": "object",
    "required": ["sources"],
    "properties": {
        "registry_version": {"type": "string", "examples": [evidence.EVIDENCE_REGISTRY_VERSION]},
        "sources": {"type": "array", "items": {"type": "object"}},
    },
    "additionalProperties": True,
}


def schema_catalog():
    catalog = {
        **agent_api.schema_catalog(),
        "adapter_contract": ADAPTER_CONTRACT_SCHEMA,
        "evidence_object": EVIDENCE_OBJECT_SCHEMA,
        "evidence_registry": EVIDENCE_REGISTRY_SCHEMA,
        "audit_record": AUDIT_RECORD_SCHEMA,
        "audit_metrics_export": AUDIT_METRICS_EXPORT_SCHEMA,
        "audit_integrity_manifest": AUDIT_INTEGRITY_MANIFEST_SCHEMA,
    }
    return dict(sorted(catalog.items()))


def contract_inventory():
    return [
        {
            "id": "adapter_contract",
            "version": "0.1",
            "schema": "adapter_contract",
            "validator": "scripts.validate_adapter.validate_adapter",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "adapter contract version bump and migration notes",
        },
        {
            "id": "agent_event",
            "version": agent_contract.AGENT_EVENT_VERSION,
            "schema": "agent_event",
            "validator": "eval_pipeline.agent_contract.validate_agent_event",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "event_version bump",
        },
        {
            "id": "agent_check_result",
            "version": agent_contract.AGENT_EVENT_VERSION,
            "schema": "agent_check_result",
            "validator": "eval_pipeline.agent_api.check_event",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "agent_check_version bump",
        },
        {
            "id": "workflow_request",
            "version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "schema": "workflow_request",
            "validator": "eval_pipeline.workflow_contract.validate_workflow_request",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "contract_version bump",
        },
        {
            "id": "workflow_batch_request",
            "version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "schema": "workflow_batch_request",
            "validator": "eval_pipeline.workflow_contract.validate_workflow_batch_request",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "contract_version bump",
        },
        {
            "id": "workflow_result",
            "version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "schema": "workflow_result",
            "validator": "eval_pipeline.agent_api.check_workflow_request",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "contract_version bump",
        },
        {
            "id": "workflow_batch_result",
            "version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "schema": "workflow_batch_result",
            "validator": "eval_pipeline.agent_api.check_workflow_batch",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "contract_version bump",
        },
        {
            "id": "aix",
            "version": aix.AIX_VERSION,
            "schema": "aix",
            "validator": "eval_pipeline.aix.compute_aix",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "aix_version bump",
        },
        {
            "id": "evidence_object",
            "version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "schema": "evidence_object",
            "validator": "eval_pipeline.workflow_contract.validate_workflow_request",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "contract_version bump",
        },
        {
            "id": "evidence_registry",
            "version": evidence.EVIDENCE_REGISTRY_VERSION,
            "schema": "evidence_registry",
            "validator": "eval_pipeline.evidence.validate_registry",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "registry_version bump",
        },
        {
            "id": "audit_record",
            "version": audit.AUDIT_RECORD_VERSION,
            "schema": "audit_record",
            "validator": "eval_pipeline.audit.agent_audit_record",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "audit_record_version bump",
        },
        {
            "id": "audit_metrics_export",
            "version": audit.AUDIT_METRICS_EXPORT_VERSION,
            "schema": "audit_metrics_export",
            "validator": "eval_pipeline.audit.export_metrics",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "audit_metrics_export_version bump",
        },
        {
            "id": "audit_integrity_manifest",
            "version": audit.AUDIT_INTEGRITY_MANIFEST_VERSION,
            "schema": "audit_integrity_manifest",
            "validator": "eval_pipeline.audit.create_integrity_manifest",
            "stability": CONTRACT_STATUS,
            "breaking_change_requires": "audit_integrity_manifest_version bump",
        },
    ]


def _status(name, status, message, details=None):
    return {"name": name, "status": status, "message": message, "details": details or {}}


def _issue(level, path, message):
    return {"level": level, "path": path, "message": message}


def _schema_issues(name, schema):
    issues = []
    if not isinstance(schema, dict):
        return [_issue("error", name, "Schema must be a JSON object.")]
    for key in ("$schema", "$id", "title", "type", "properties"):
        if key not in schema:
            issues.append(_issue("error", f"{name}.{key}", f"Schema is missing {key}."))
    if schema.get("type") != "object":
        issues.append(_issue("error", f"{name}.type", "Public contract schemas must describe JSON objects."))
    if not isinstance(schema.get("properties"), dict) or not schema.get("properties"):
        issues.append(_issue("error", f"{name}.properties", "Schema properties must be non-empty."))
    return issues


def validate_schema_catalog(catalog=None):
    catalog = catalog or schema_catalog()
    required = {item["schema"] for item in contract_inventory()}
    missing = sorted(required - set(catalog))
    issues = [_issue("error", f"schemas.{name}", "Required frozen contract schema is missing.") for name in missing]
    for name in sorted(required & set(catalog)):
        issues.extend(_schema_issues(name, catalog[name]))
    return {
        "valid": not any(issue["level"] == "error" for issue in issues),
        "schema_count": len(catalog),
        "required_schema_count": len(required),
        "issues": issues,
    }


def validate_inventory(catalog=None):
    catalog = catalog or schema_catalog()
    issues = []
    inventory = contract_inventory()
    seen = set()
    for item in inventory:
        item_id = item.get("id")
        path = f"contracts.{item_id}"
        if not item_id:
            issues.append(_issue("error", "contracts", "Contract entry is missing id."))
            continue
        if item_id in seen:
            issues.append(_issue("error", path, "Duplicate contract id."))
        seen.add(item_id)
        if item.get("stability") != CONTRACT_STATUS:
            issues.append(_issue("error", f"{path}.stability", f"Contract stability must be {CONTRACT_STATUS}."))
        if not isinstance(item.get("version"), str) or not item.get("version").strip():
            issues.append(_issue("error", f"{path}.version", "Contract version must be a non-empty string."))
        if item.get("schema") not in catalog:
            issues.append(_issue("error", f"{path}.schema", f"Schema {item.get('schema')!r} is not available."))
        if not item.get("breaking_change_requires"):
            issues.append(_issue("error", f"{path}.breaking_change_requires", "Contract must document breaking-change bump rule."))
    return {
        "valid": not any(issue["level"] == "error" for issue in issues),
        "contract_count": len(inventory),
        "issues": issues,
    }


def _load_json(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def validate_fixtures(gallery_path=None, evidence_registry_path=None):
    gallery_path = pathlib.Path(gallery_path or ROOT / "examples" / "adapter_gallery.json")
    default_gallery_path = ROOT / "examples" / "adapter_gallery.json"
    example_gallery_path = gallery_path if gallery_path.resolve() == default_gallery_path.resolve() else default_gallery_path
    evidence_registry_path = pathlib.Path(evidence_registry_path or ROOT / "examples" / "evidence_registry.json")
    issues = []

    gallery = validate_adapter_gallery.load_gallery(gallery_path)
    gallery_report = validate_adapter_gallery.validate_gallery(gallery, run_examples=True)
    for issue in gallery_report.get("issues", []):
        level = "error" if issue.get("level") == "error" else "warning"
        issues.append(_issue(level, f"adapter_gallery.{issue.get('path')}", issue.get("message", "Gallery issue.")))

    adapter_count = 0
    for entry in gallery.get("adapters", []):
        if not isinstance(entry, dict) or not entry.get("adapter_path"):
            continue
        adapter_count += 1
        adapter_path = ROOT / entry["adapter_path"]
        adapter_report = validate_adapter.validate_adapter(validate_adapter.load_adapter(adapter_path))
        for issue in adapter_report.get("issues", []):
            if issue.get("level") == "error":
                issues.append(_issue("error", f"{entry.get('id')}.{issue.get('path')}", issue.get("message", "Adapter issue.")))

    try:
        agent_examples = agent_api.run_agent_event_examples(gallery_path=example_gallery_path)
        if not agent_examples["valid"]:
            issues.append(_issue("error", "agent_event_examples", "One or more agent event examples failed."))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        agent_examples = {"count": 0}
        issues.append(_issue("error", "agent_event_examples", str(exc)))

    try:
        agent_contract_fixtures = _load_json(ROOT / "examples" / "agent_event_contract_fixtures.json")
        registry = evidence.load_registry(evidence_registry_path)
        for index, item in enumerate(agent_contract_fixtures.get("valid_events", [])):
            report = agent_api.validate_event(item.get("event"), evidence_registry=registry)
            if not report["valid"]:
                issues.append(_issue("error", f"agent_event_contract_fixtures.valid_events[{index}]", f"Valid fixture failed: {item.get('name')}"))
        for index, item in enumerate(agent_contract_fixtures.get("invalid_events", [])):
            report = agent_api.validate_event(item.get("event"), evidence_registry=registry)
            if report["valid"]:
                issues.append(_issue("error", f"agent_event_contract_fixtures.invalid_events[{index}]", f"Invalid fixture passed: {item.get('name')}"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(_issue("error", "agent_event_contract_fixtures", str(exc)))

    workflow_request = _load_json(ROOT / "examples" / "workflow_research_summary_structured.json")
    workflow_report = workflow_contract.validate_workflow_request(workflow_request)
    for issue in workflow_report["issues"]:
        if issue["level"] == "error":
            issues.append(_issue("error", f"workflow_request{issue['path'][1:]}", issue["message"]))

    workflow_batch = _load_json(ROOT / "examples" / "workflow_batch_productive_work.json")
    batch_report = workflow_contract.validate_workflow_batch_request(workflow_batch)
    for issue in batch_report["issues"]:
        if issue["level"] == "error":
            issues.append(_issue("error", f"workflow_batch{issue['path'][1:]}", issue["message"]))

    registry_report = evidence.validate_registry(evidence.load_registry(evidence_registry_path))
    for issue in registry_report["issues"]:
        if issue["level"] == "error":
            issues.append(_issue("error", f"evidence_registry{issue['path'][1:]}", issue["message"]))

    event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
    result = agent_api.check_event(event, gallery_path=example_gallery_path)
    audit_record = audit.agent_audit_record(event, result, created_at="2026-01-01T00:00:00+00:00")
    metrics = audit.export_metrics([audit_record], created_at="2026-01-01T00:00:00+00:00")
    if audit_record.get("audit_record_version") != audit.AUDIT_RECORD_VERSION:
        issues.append(_issue("error", "audit_record.audit_record_version", "Audit record version mismatch."))
    if metrics.get("audit_metrics_export_version") != audit.AUDIT_METRICS_EXPORT_VERSION:
        issues.append(_issue("error", "audit_metrics.audit_metrics_export_version", "Audit metrics export version mismatch."))

    return {
        "valid": not any(issue["level"] == "error" for issue in issues),
        "adapter_count": adapter_count,
        "agent_event_examples": agent_examples["count"],
        "issues": issues,
    }


def contract_freeze_report(gallery_path=None, evidence_registry_path=None):
    catalog = schema_catalog()
    inventory_report = validate_inventory(catalog)
    schema_report = validate_schema_catalog(catalog)
    fixture_report = validate_fixtures(gallery_path=gallery_path, evidence_registry_path=evidence_registry_path)
    docs = [
        ROOT / "docs" / "contract-freeze.md",
        ROOT / "docs" / "aana-workflow-contract.md",
        ROOT / "docs" / "agent-integration.md",
    ]
    missing_docs = [str(path.relative_to(ROOT)) for path in docs if not path.exists()]
    docs_report = {
        "valid": not missing_docs,
        "issues": [_issue("error", f"docs.{path}", "Required contract freeze documentation is missing.") for path in missing_docs],
    }
    checks = [
        _status("contract_inventory", "pass" if inventory_report["valid"] else "fail", "Frozen contract inventory is complete.", inventory_report),
        _status("schema_catalog", "pass" if schema_report["valid"] else "fail", "Frozen contract schemas are complete.", schema_report),
        _status("compatibility_fixtures", "pass" if fixture_report["valid"] else "fail", "Frozen contract fixtures validate.", fixture_report),
        _status("contract_docs", "pass" if docs_report["valid"] else "fail", "Contract freeze documentation is present.", docs_report),
    ]
    failed = [item for item in checks if item["status"] == "fail"]
    return {
        "contract_freeze_version": CONTRACT_FREEZE_VERSION,
        "status": CONTRACT_STATUS,
        "valid": not failed,
        "frozen": not failed,
        "summary": {
            "status": "pass" if not failed else "fail",
            "checks": len(checks),
            "failures": len(failed),
            "contracts": len(contract_inventory()),
            "schemas": len(catalog),
        },
        "contracts": contract_inventory(),
        "checks": checks,
    }
