"""Contract freeze inventory and compatibility checks for AANA public surfaces."""

import inspect
import json
import pathlib
import re

from eval_pipeline import agent_api, agent_contract, audit, aix, evidence, evidence_integrations, workflow_contract
from scripts.validation import validate_adapter, validate_adapter_gallery


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT_FREEZE_VERSION = "0.1"
CONTRACT_STATUS = "frozen"
AGENT_ACTION_CONTRACT_V1_FIELDS = [
    "tool_name",
    "tool_category",
    "authorization_state",
    "evidence_refs",
    "risk_domain",
    "proposed_arguments",
    "recommended_route",
]
AGENT_ACTION_CONTRACT_V1_ROUTES = ["accept", "ask", "defer", "refuse"]
PRIMARY_PUBLIC_CONTRACTS = {
    "agent_action_contract_v1",
    "agent_event",
    "agent_check_result",
    "workflow_request",
    "workflow_batch_request",
    "workflow_result",
    "workflow_batch_result",
}


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


AUDIT_DRIFT_REPORT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/audit-drift-report.schema.json",
    "title": "AANA AIx Drift Report",
    "description": "AIx drift and threshold report generated from redacted AANA audit records.",
    "type": "object",
    "required": ["audit_drift_report_version", "created_at", "valid", "record_count", "thresholds", "metrics", "issues"],
    "properties": {
        "audit_drift_report_version": {"type": "string", "examples": [audit.AUDIT_DRIFT_REPORT_VERSION]},
        "created_at": {"type": "string"},
        "valid": {"type": "boolean"},
        "record_count": {"type": "integer"},
        "thresholds": {"type": "object"},
        "metrics": {"type": "object"},
        "decision_counts": {"type": "object"},
        "baseline_comparisons": {"type": "object"},
        "issues": {"type": "array", "items": {"type": "object"}},
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
    agent_action_contract_v1 = _load_json(ROOT / "schemas" / "agent_tool_precheck.schema.json")
    catalog = {
        **agent_api.schema_catalog(),
        "agent_action_contract_v1": agent_action_contract_v1,
        "adapter_contract": ADAPTER_CONTRACT_SCHEMA,
        "evidence_object": EVIDENCE_OBJECT_SCHEMA,
        "evidence_registry": EVIDENCE_REGISTRY_SCHEMA,
        "audit_record": AUDIT_RECORD_SCHEMA,
        "audit_metrics_export": AUDIT_METRICS_EXPORT_SCHEMA,
        "audit_integrity_manifest": AUDIT_INTEGRITY_MANIFEST_SCHEMA,
        "audit_drift_report": AUDIT_DRIFT_REPORT_SCHEMA,
    }
    return dict(sorted(catalog.items()))


def contract_inventory():
    return [
        {
            "id": "agent_action_contract_v1",
            "version": "v1",
            "schema": "agent_action_contract_v1",
            "validator": "eval_pipeline.pre_tool_call_gate.validate_event",
            "stability": CONTRACT_STATUS,
            "public_api": True,
            "boundary": "primary_public_api",
            "required_fields": list(AGENT_ACTION_CONTRACT_V1_FIELDS),
            "breaking_change_requires": "new Agent Action Contract schema id and compatibility/migration notes",
        },
        {
            "id": "adapter_contract",
            "version": "0.1",
            "schema": "adapter_contract",
            "validator": "scripts.validate_adapter.validate_adapter",
            "stability": CONTRACT_STATUS,
            "public_api": False,
            "boundary": "adapter_catalog",
            "breaking_change_requires": "adapter contract version bump and migration notes",
        },
        {
            "id": "agent_event",
            "version": agent_contract.AGENT_EVENT_VERSION,
            "schema": "agent_event",
            "validator": "eval_pipeline.agent_contract.validate_agent_event",
            "stability": CONTRACT_STATUS,
            "public_api": True,
            "boundary": "primary_public_api",
            "breaking_change_requires": "event_version bump",
        },
        {
            "id": "agent_check_result",
            "version": agent_contract.AGENT_EVENT_VERSION,
            "schema": "agent_check_result",
            "validator": "eval_pipeline.agent_api.check_event",
            "stability": CONTRACT_STATUS,
            "public_api": True,
            "boundary": "primary_public_api",
            "breaking_change_requires": "agent_check_version bump",
        },
        {
            "id": "workflow_request",
            "version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "schema": "workflow_request",
            "validator": "eval_pipeline.workflow_contract.validate_workflow_request",
            "stability": CONTRACT_STATUS,
            "public_api": True,
            "boundary": "primary_public_api",
            "breaking_change_requires": "contract_version bump",
        },
        {
            "id": "workflow_batch_request",
            "version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "schema": "workflow_batch_request",
            "validator": "eval_pipeline.workflow_contract.validate_workflow_batch_request",
            "stability": CONTRACT_STATUS,
            "public_api": True,
            "boundary": "primary_public_api",
            "breaking_change_requires": "contract_version bump",
        },
        {
            "id": "workflow_result",
            "version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "schema": "workflow_result",
            "validator": "eval_pipeline.agent_api.check_workflow_request",
            "stability": CONTRACT_STATUS,
            "public_api": True,
            "boundary": "primary_public_api",
            "breaking_change_requires": "contract_version bump",
        },
        {
            "id": "workflow_batch_result",
            "version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "schema": "workflow_batch_result",
            "validator": "eval_pipeline.agent_api.check_workflow_batch",
            "stability": CONTRACT_STATUS,
            "public_api": True,
            "boundary": "primary_public_api",
            "breaking_change_requires": "contract_version bump",
        },
        {
            "id": "aix",
            "version": aix.AIX_VERSION,
            "schema": "aix",
            "validator": "eval_pipeline.aix.compute_aix",
            "stability": CONTRACT_STATUS,
            "public_api": False,
            "boundary": "public_result_block",
            "breaking_change_requires": "aix_version bump",
        },
        {
            "id": "evidence_object",
            "version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "schema": "evidence_object",
            "validator": "eval_pipeline.workflow_contract.validate_workflow_request",
            "stability": CONTRACT_STATUS,
            "public_api": False,
            "boundary": "public_contract_component",
            "breaking_change_requires": "contract_version bump",
        },
        {
            "id": "evidence_registry",
            "version": evidence.EVIDENCE_REGISTRY_VERSION,
            "schema": "evidence_registry",
            "validator": "eval_pipeline.evidence.validate_registry",
            "stability": CONTRACT_STATUS,
            "public_api": False,
            "boundary": "public_contract_component",
            "breaking_change_requires": "registry_version bump",
        },
        {
            "id": "audit_record",
            "version": audit.AUDIT_RECORD_VERSION,
            "schema": "audit_record",
            "validator": "eval_pipeline.audit.agent_audit_record",
            "stability": CONTRACT_STATUS,
            "public_api": False,
            "boundary": "public_observability_contract",
            "breaking_change_requires": "audit_record_version bump",
        },
        {
            "id": "audit_metrics_export",
            "version": audit.AUDIT_METRICS_EXPORT_VERSION,
            "schema": "audit_metrics_export",
            "validator": "eval_pipeline.audit.export_metrics",
            "stability": CONTRACT_STATUS,
            "public_api": False,
            "boundary": "public_observability_contract",
            "breaking_change_requires": "audit_metrics_export_version bump",
        },
        {
            "id": "audit_integrity_manifest",
            "version": audit.AUDIT_INTEGRITY_MANIFEST_VERSION,
            "schema": "audit_integrity_manifest",
            "validator": "eval_pipeline.audit.create_integrity_manifest",
            "stability": CONTRACT_STATUS,
            "public_api": False,
            "boundary": "public_observability_contract",
            "breaking_change_requires": "audit_integrity_manifest_version bump",
        },
        {
            "id": "audit_drift_report",
            "version": audit.AUDIT_DRIFT_REPORT_VERSION,
            "schema": "audit_drift_report",
            "validator": "eval_pipeline.audit.aix_drift_report",
            "stability": CONTRACT_STATUS,
            "public_api": False,
            "boundary": "public_observability_contract",
            "breaking_change_requires": "audit_drift_report_version bump",
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
        expected_public_api = item_id in PRIMARY_PUBLIC_CONTRACTS
        if item.get("public_api") is not expected_public_api:
            issues.append(_issue("error", f"{path}.public_api", f"public_api must be {expected_public_api}."))
        if expected_public_api and item.get("boundary") != "primary_public_api":
            issues.append(_issue("error", f"{path}.boundary", "Primary public APIs must declare boundary='primary_public_api'."))
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


def _read_text(path):
    return pathlib.Path(path).read_text(encoding="utf-8")


def _contract_event_has_frozen_fields(event):
    return isinstance(event, dict) and all(field in event for field in AGENT_ACTION_CONTRACT_V1_FIELDS)


def _check_text_surface(path, issues, *, require_heading=False):
    rel = str(pathlib.Path(path).relative_to(ROOT))
    if not pathlib.Path(path).exists():
        issues.append(_issue("error", rel, "Agent Action Contract compatibility surface is missing."))
        return
    text = _read_text(path)
    if require_heading and "Agent Action Contract v1" not in text:
        issues.append(_issue("error", rel, "Surface must name Agent Action Contract v1."))
    for field in AGENT_ACTION_CONTRACT_V1_FIELDS:
        if field not in text:
            issues.append(_issue("error", rel, f"Surface is missing frozen field {field!r}."))


def _check_json_event_file(path, issues):
    rel = str(pathlib.Path(path).relative_to(ROOT))
    if not pathlib.Path(path).exists():
        issues.append(_issue("error", rel, "Agent Action Contract example file is missing."))
        return 0
    try:
        payload = _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(_issue("error", rel, str(exc)))
        return 0
    events = []
    if _contract_event_has_frozen_fields(payload):
        events.append(payload)
    if isinstance(payload.get("event"), dict):
        events.append(payload["event"])
    for item in payload.get("examples", []) if isinstance(payload.get("examples"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("event"), dict):
            events.append(item["event"])
    for item in payload.get("cases", []) if isinstance(payload.get("cases"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("event"), dict):
            events.append(item["event"])
    if not events:
        issues.append(_issue("error", rel, "No Agent Action Contract example events found."))
        return 0
    for index, event in enumerate(events):
        for field in AGENT_ACTION_CONTRACT_V1_FIELDS:
            if field not in event:
                issues.append(_issue("error", f"{rel}.events[{index}]", f"Example event is missing frozen field {field!r}."))
    return len(events)


def validate_agent_action_contract_v1_compatibility():
    """Validate that all public pre-tool-call surfaces honor the v1 freeze."""

    issues = []
    schema = _load_json(ROOT / "schemas" / "agent_tool_precheck.schema.json")
    freeze = schema.get("x-aana-contract-freeze") if isinstance(schema.get("x-aana-contract-freeze"), dict) else {}
    if schema.get("title") != "AANA Agent Action Contract v1":
        issues.append(_issue("error", "schemas/agent_tool_precheck.schema.json.title", "Schema title must remain AANA Agent Action Contract v1."))
    if schema.get("$id") != "https://aana.dev/schemas/agent_action_contract_v1.schema.json":
        issues.append(_issue("error", "schemas/agent_tool_precheck.schema.json.$id", "Schema $id must remain the public v1 URL."))
    if schema.get("required") != AGENT_ACTION_CONTRACT_V1_FIELDS:
        issues.append(_issue("error", "schemas/agent_tool_precheck.schema.json.required", "Required fields must match the frozen seven-field order."))
    if freeze.get("required_field_order") != AGENT_ACTION_CONTRACT_V1_FIELDS:
        issues.append(_issue("error", "schemas/agent_tool_precheck.schema.json.x-aana-contract-freeze", "Freeze metadata must match the frozen field order."))
    if schema.get("properties", {}).get("recommended_route", {}).get("enum") != AGENT_ACTION_CONTRACT_V1_ROUTES:
        issues.append(_issue("error", "schemas/agent_tool_precheck.schema.json.recommended_route", "Route enum must stay accept, ask, defer, refuse."))

    from aana import sdk

    signature = inspect.signature(sdk.build_tool_precheck_event)
    for field in AGENT_ACTION_CONTRACT_V1_FIELDS:
        if field not in signature.parameters:
            issues.append(_issue("error", f"aana.sdk.build_tool_precheck_event.{field}", "Python SDK builder is missing a frozen field parameter."))
    try:
        event = sdk.build_tool_precheck_event(
            tool_name="search_docs",
            tool_category="public_read",
            authorization_state="none",
            evidence_refs=["docs:aana-agent-action-contract-v1"],
            risk_domain="public_information",
            proposed_arguments={"query": "AANA Agent Action Contract v1"},
            recommended_route="accept",
        )
        if not _contract_event_has_frozen_fields(event):
            issues.append(_issue("error", "aana.sdk.build_tool_precheck_event", "Python SDK builder output is missing one or more frozen fields."))
    except Exception as exc:
        issues.append(_issue("error", "aana.sdk.build_tool_precheck_event", f"Python SDK builder failed the frozen-field smoke test: {exc}"))

    for path in [ROOT / "sdk" / "typescript" / "src" / "index.ts", ROOT / "sdk" / "typescript" / "dist" / "index.d.ts"]:
        rel = str(path.relative_to(ROOT))
        text = _read_text(path)
        if "ToolPrecheckEvent" not in text:
            issues.append(_issue("error", rel, "TypeScript SDK must expose ToolPrecheckEvent."))
        event_match = re.search(r"interface\s+ToolPrecheckEvent\s*\{(?P<body>.*?)\n\}", text, flags=re.S)
        event_text = event_match.group("body") if event_match else text
        for field in AGENT_ACTION_CONTRACT_V1_FIELDS:
            if not re.search(rf"\b{re.escape(field)}\s*:", event_text):
                issues.append(_issue("error", rel, f"TypeScript SDK event type is missing required field {field!r}."))
            if re.search(rf"\b{re.escape(field)}\s*\?:", event_text):
                issues.append(_issue("error", rel, f"TypeScript SDK must not make frozen field {field!r} optional."))

    from eval_pipeline import fastapi_app, mcp_server

    for example_name, example in {
        "PRE_TOOL_CHECK_EXAMPLE": fastapi_app.PRE_TOOL_CHECK_EXAMPLE,
        "CONFIRMED_PRE_TOOL_CHECK_EXAMPLE": fastapi_app.CONFIRMED_PRE_TOOL_CHECK_EXAMPLE,
    }.items():
        if not _contract_event_has_frozen_fields(example):
            issues.append(_issue("error", f"eval_pipeline.fastapi_app.{example_name}", "FastAPI OpenAPI example is missing one or more frozen fields."))
    try:
        app = fastapi_app.create_app(auth_token="redacted-contract-freeze-test-token")
        openapi = app.openapi()
        request_body = openapi["paths"]["/pre-tool-check"]["post"]["requestBody"]["content"]["application/json"]
        examples = request_body.get("examples") or {}
        if len(examples) < 2:
            issues.append(_issue("error", "eval_pipeline.fastapi_app.openapi./pre-tool-check", "FastAPI OpenAPI must publish pre-tool examples."))
        for name, item in examples.items():
            if not _contract_event_has_frozen_fields(item.get("value")):
                issues.append(_issue("error", f"eval_pipeline.fastapi_app.openapi.examples.{name}", "OpenAPI example is missing frozen fields."))
    except Exception as exc:
        issues.append(_issue("error", "eval_pipeline.fastapi_app.openapi", f"FastAPI OpenAPI compatibility check failed: {exc}"))

    mcp_schema = mcp_server.AANA_PRE_TOOL_CHECK_TOOL.get("inputSchema", {})
    if mcp_schema.get("required") != AGENT_ACTION_CONTRACT_V1_FIELDS:
        issues.append(_issue("error", "eval_pipeline.mcp_server.AANA_PRE_TOOL_CHECK_TOOL.inputSchema.required", "MCP tool required fields must match the frozen seven-field order."))
    for field in AGENT_ACTION_CONTRACT_V1_FIELDS:
        if field not in mcp_schema.get("properties", {}):
            issues.append(_issue("error", f"eval_pipeline.mcp_server.AANA_PRE_TOOL_CHECK_TOOL.inputSchema.properties.{field}", "MCP tool schema is missing a frozen field."))

    docs = [
        ROOT / "docs" / "agent-action-contract-v1.md",
        ROOT / "docs" / "agent-action-contract-quickstart.md",
        ROOT / "docs" / "agent-tool-precheck-contract.md",
        ROOT / "docs" / "fastapi-service.md",
        ROOT / "docs" / "aana-mcp-chatgpt-app.md",
        ROOT / "docs" / "openai-agents-quickstart.md",
        ROOT / "docs" / "huggingface-model-card.md",
    ]
    for path in docs:
        _check_text_surface(path, issues, require_heading=path.name in {"agent-action-contract-v1.md", "agent-tool-precheck-contract.md"})

    example_count = 0
    for path in [
        ROOT / "examples" / "agent_action_contract_cases.json",
        ROOT / "examples" / "sdk" / "agent_tool_precheck_examples.json",
        ROOT / "examples" / "api" / "pre_tool_check_write_ask.json",
        ROOT / "examples" / "api" / "pre_tool_check_confirmed_write.json",
    ]:
        example_count += _check_json_event_file(path, issues)

    hf_space_app = ROOT / "examples" / "huggingface_space" / "app.py"
    hf_space_readme = ROOT / "examples" / "huggingface_space" / "README.md"
    _check_text_surface(hf_space_app, issues)
    _check_text_surface(hf_space_readme, issues, require_heading=True)

    return {
        "valid": not any(issue["level"] == "error" for issue in issues),
        "frozen_fields": list(AGENT_ACTION_CONTRACT_V1_FIELDS),
        "frozen_routes": list(AGENT_ACTION_CONTRACT_V1_ROUTES),
        "surfaces": {
            "python_sdk": "aana.sdk.build_tool_precheck_event",
            "typescript_sdk": ["sdk/typescript/src/index.ts", "sdk/typescript/dist/index.d.ts"],
            "fastapi": "eval_pipeline.fastapi_app:/pre-tool-check",
            "mcp": "eval_pipeline.mcp_server:AANA_PRE_TOOL_CHECK_TOOL",
            "docs": [str(path.relative_to(ROOT)) for path in docs],
            "examples_checked": example_count,
            "hf_space": ["examples/huggingface_space/app.py", "examples/huggingface_space/README.md"],
        },
        "issues": issues,
    }


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

    try:
        workflow_examples = _load_json(ROOT / "examples" / "workflow_contract_examples.json")
        families = workflow_examples.get("adapter_families", [])
        if not isinstance(families, list) or not families:
            issues.append(_issue("error", "workflow_contract_examples.adapter_families", "Workflow example families must be a non-empty array."))
        seen_families = set()
        for family_index, family in enumerate(families if isinstance(families, list) else []):
            family_path = f"workflow_contract_examples.adapter_families[{family_index}]"
            if not isinstance(family, dict):
                issues.append(_issue("error", family_path, "Workflow example family must be an object."))
                continue
            family_id = family.get("family_id")
            if not isinstance(family_id, str) or not family_id.strip():
                issues.append(_issue("error", f"{family_path}.family_id", "Workflow example family must include family_id."))
            elif family_id in seen_families:
                issues.append(_issue("error", f"{family_path}.family_id", f"Duplicate workflow example family: {family_id}."))
            else:
                seen_families.add(family_id)
            examples = family.get("examples")
            if not isinstance(examples, list) or not examples:
                issues.append(_issue("error", f"{family_path}.examples", "Workflow example family must include examples."))
                continue
            for example_index, example in enumerate(examples):
                example_path = f"{family_path}.examples[{example_index}]"
                if not isinstance(example, dict):
                    issues.append(_issue("error", example_path, "Workflow example entry must be an object."))
                    continue
                workflow_file = example.get("workflow_file")
                adapter_id = example.get("adapter")
                if not isinstance(workflow_file, str) or not workflow_file.strip():
                    issues.append(_issue("error", f"{example_path}.workflow_file", "Workflow example entry must include workflow_file."))
                    continue
                workflow_path = ROOT / workflow_file
                if not workflow_path.exists():
                    issues.append(_issue("error", f"{example_path}.workflow_file", f"Workflow example file does not exist: {workflow_file}."))
                    continue
                request = _load_json(workflow_path)
                report = workflow_contract.validate_workflow_request(request)
                for issue in report["issues"]:
                    if issue["level"] == "error":
                        issues.append(_issue("error", f"{example_path}{issue['path'][1:]}", issue["message"]))
                if adapter_id != request.get("adapter"):
                    issues.append(
                        _issue(
                            "error",
                            f"{example_path}.adapter",
                            f"Workflow example adapter {adapter_id!r} does not match request adapter {request.get('adapter')!r}.",
                        )
                    )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(_issue("error", "workflow_contract_examples", str(exc)))

    registry_report = evidence.validate_registry(evidence.load_registry(evidence_registry_path))
    for issue in registry_report["issues"]:
        if issue["level"] == "error":
            issues.append(_issue("error", f"evidence_registry{issue['path'][1:]}", issue["message"]))

    try:
        mock_matrix = evidence_integrations.mock_connector_matrix(
            fixtures=evidence_integrations.load_mock_connector_fixtures(ROOT / "examples" / "evidence_mock_connector_fixtures.json"),
            integration_ids=[
                "crm_support",
                "email_send",
                "calendar",
                "iam",
                "ci",
                "deployment",
                "billing",
                "data_export",
            ],
            now="2026-05-05T01:00:00Z",
        )
        if not mock_matrix["valid"]:
            issues.append(_issue("error", "evidence_mock_connector_fixtures", "One or more mock connector fixtures failed the evidence contract."))
    except (OSError, ValueError, json.JSONDecodeError, evidence_integrations.EvidenceConnectorError) as exc:
        issues.append(_issue("error", "evidence_mock_connector_fixtures", str(exc)))

    event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
    result = agent_api.check_event(event, gallery_path=example_gallery_path)
    audit_record = audit.agent_audit_record(event, result, created_at="2026-01-01T00:00:00+00:00")
    metrics = audit.export_metrics([audit_record], created_at="2026-01-01T00:00:00+00:00")
    drift = audit.aix_drift_report([audit_record], created_at="2026-01-01T00:00:00+00:00")
    if audit_record.get("audit_record_version") != audit.AUDIT_RECORD_VERSION:
        issues.append(_issue("error", "audit_record.audit_record_version", "Audit record version mismatch."))
    audit_record_report = audit.validate_audit_records([audit_record])
    if not audit_record_report["valid"]:
        issues.append(_issue("error", "audit_record.validation", "Generated audit record failed schema/redaction validation."))
    if metrics.get("audit_metrics_export_version") != audit.AUDIT_METRICS_EXPORT_VERSION:
        issues.append(_issue("error", "audit_metrics.audit_metrics_export_version", "Audit metrics export version mismatch."))
    metrics_report = audit.validate_metrics_export(metrics)
    if not metrics_report["valid"]:
        issues.append(_issue("error", "audit_metrics.validation", "Generated audit metrics export failed compatibility validation."))
    if drift.get("audit_drift_report_version") != audit.AUDIT_DRIFT_REPORT_VERSION:
        issues.append(_issue("error", "audit_drift_report.audit_drift_report_version", "Audit drift report version mismatch."))

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
    agent_action_contract_report = validate_agent_action_contract_v1_compatibility()
    fixture_report = validate_fixtures(gallery_path=gallery_path, evidence_registry_path=evidence_registry_path)
    docs = [
        ROOT / "docs" / "contract-freeze.md",
        ROOT / "docs" / "aana-workflow-contract.md",
        ROOT / "docs" / "agent-integration.md",
        ROOT / "docs" / "http-bridge-runbook.md",
        ROOT / "docs" / "openclaw-skill-conformance.md",
        ROOT / "docs" / "openclaw-plugin-install-use.md",
        ROOT / "docs" / "evidence-integration-contracts.md",
        ROOT / "docs" / "audit-observability-hardening.md",
        ROOT / "docs" / "pilot-surface-certification.md",
    ]
    missing_docs = [str(path.relative_to(ROOT)) for path in docs if not path.exists()]
    docs_report = {
        "valid": not missing_docs,
        "issues": [_issue("error", f"docs.{path}", "Required contract freeze documentation is missing.") for path in missing_docs],
    }
    checks = [
        _status("contract_inventory", "pass" if inventory_report["valid"] else "fail", "Frozen contract inventory is complete.", inventory_report),
        _status("schema_catalog", "pass" if schema_report["valid"] else "fail", "Frozen contract schemas are complete.", schema_report),
        _status(
            "agent_action_contract_v1_compatibility",
            "pass" if agent_action_contract_report["valid"] else "fail",
            "Agent Action Contract v1 is frozen across SDK, API, MCP, docs, examples, and HF Space surfaces.",
            agent_action_contract_report,
        ),
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
