"""Pilot surface certification matrix for AANA public integration paths."""

from __future__ import annotations

import json
import pathlib

from eval_pipeline import (
    agent_api,
    agent_contract,
    agent_server,
    contract_freeze,
    evidence as evidence_registry,
    evidence_integrations,
    runtime as runtime_api,
    workflow_contract,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
PILOT_CERTIFICATION_VERSION = "0.2"
PILOT_READY_SCORE_THRESHOLD = 90.0


def _status_score(status):
    if status == "pass":
        return 1.0
    if status == "warn":
        return 0.5
    return 0.0


def _readiness_level(score_percent, failures, warnings):
    if failures:
        return "not_pilot_ready"
    if score_percent >= PILOT_READY_SCORE_THRESHOLD and warnings:
        return "pilot_ready_with_warnings"
    if score_percent >= PILOT_READY_SCORE_THRESHOLD:
        return "pilot_ready"
    return "not_pilot_ready"


def _gate(gate_id, status, message, details=None, weight=1):
    return {
        "id": gate_id,
        "status": status,
        "message": message,
        "details": details or {},
        "weight": weight,
        "score": round(weight * _status_score(status), 2),
    }


def _surface(surface_id, title, gates):
    failures = [gate for gate in gates if gate["status"] == "fail"]
    warnings = [gate for gate in gates if gate["status"] == "warn"]
    max_score = sum(gate.get("weight", 1) for gate in gates)
    score = sum(gate.get("score", 0) for gate in gates)
    score_percent = round((score / max_score) * 100, 1) if max_score else 0.0
    readiness_level = _readiness_level(score_percent, len(failures), len(warnings))
    return {
        "surface_id": surface_id,
        "title": title,
        "status": "fail" if failures else "pass",
        "ready": readiness_level != "not_pilot_ready",
        "readiness_level": readiness_level,
        "score": round(score, 2),
        "max_score": max_score,
        "score_percent": score_percent,
        "summary": {
            "gates": len(gates),
            "failures": len(failures),
            "warnings": len(warnings),
            "score_percent": score_percent,
            "readiness_level": readiness_level,
        },
        "gates": gates,
    }


def _path_exists(relative_path):
    path = ROOT / relative_path
    return path.exists(), path


def _json_object(relative_path):
    path = ROOT / relative_path
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{relative_path} must contain a JSON object.")
    return data


def _cli_surface(cli_commands=None):
    commands = cli_commands or []
    command_names = {item.get("command") for item in commands if isinstance(item, dict)}
    required = {
        "agent-check",
        "workflow-check",
        "workflow-batch",
        "validate-event",
        "validate-workflow",
        "validate-workflow-batch",
        "evidence-integrations",
        "audit-validate",
        "audit-metrics",
        "audit-drift",
        "audit-reviewer-report",
        "contract-freeze",
        "enterprise-certify",
        "personal-certify",
        "civic-certify",
        "pilot-certify",
        "production-certify",
        "release-check",
    }
    missing = sorted(required - command_names)
    gates = [
        _gate(
            "cli_command_matrix",
            "pass" if commands and not missing else "fail",
            "CLI command matrix covers pilot workflows." if commands and not missing else "CLI command matrix is missing required pilot commands.",
            {"missing": missing, "command_count": len(commands)},
        )
    ]
    docs_exist, docs_path = _path_exists("docs/cli-hardening.md")
    gates.append(
        _gate(
            "cli_docs",
            "pass" if docs_exist else "fail",
            "CLI hardening docs are present." if docs_exist else "CLI hardening docs are missing.",
            {"path": str(docs_path)},
        )
    )
    return _surface("cli", "CLI", gates)


def _python_api_surface():
    required_runtime_exports = {
        "check",
        "check_request",
        "check_batch",
        "RuntimeResult",
        "ValidationReport",
    }
    required_agent_api_exports = {
        "validate_audit_records",
        "audit_aix_drift_report",
        "run_evidence_mock_connector",
    }
    missing_runtime = sorted(name for name in required_runtime_exports if not hasattr(runtime_api, name))
    missing_agent_api = sorted(name for name in required_agent_api_exports if not hasattr(agent_api, name))
    missing = [f"eval_pipeline.runtime.{name}" for name in missing_runtime] + [
        f"eval_pipeline.agent_api.{name}" for name in missing_agent_api
    ]
    docs_exist, docs_path = _path_exists("docs/python-runtime-api.md")
    gates = [
        _gate(
            "public_api_exports",
            "pass" if not missing else "fail",
            "Python API exposes pilot runtime helpers." if not missing else "Python API is missing pilot runtime helpers.",
            {"missing": missing},
        ),
        _gate(
            "runtime_api_docs",
            "pass" if docs_exist else "fail",
            "Python runtime API docs are present." if docs_exist else "Python runtime API docs are missing.",
            {"path": str(docs_path)},
        ),
    ]
    return _surface("python_api", "Python API", gates)


def _http_bridge_surface():
    readiness = agent_server.readiness_report(
        gallery_path=agent_api.DEFAULT_GALLERY,
        auth_token="pilot-certification-token",
        audit_log_path=ROOT / "examples" / "pilot-certification-audit.jsonl",
    )
    openapi = agent_server.openapi_schema()
    paths = openapi.get("paths", {}) if isinstance(openapi, dict) else {}
    required_paths = {
        "/health",
        "/ready",
        "/adapter-gallery/",
        "/adapter-gallery/data.json",
        "/agent-check",
        "/workflow-check",
        "/workflow-batch",
        "/playground/gallery",
        "/playground/check",
        "/demos/scenarios",
        "/dashboard/metrics",
        "/enterprise/",
        "/personal-productivity/",
        "/government-civic/",
        "/families/data.json",
        "/openapi.json",
    }
    missing_paths = sorted(required_paths - set(paths))
    docs_exist, docs_path = _path_exists("docs/http-bridge-runbook.md")
    docker_paths = [
        "Dockerfile",
        "docker-compose.yml",
        ".dockerignore",
        "examples/aana_bridge.env.example",
        "docs/docker-http-bridge.md",
    ]
    missing_docker_paths = []
    for item in docker_paths:
        exists, _ = _path_exists(item)
        if not exists:
            missing_docker_paths.append(item)
    playground_paths = [
        "web/playground/index.html",
        "web/playground/app.css",
        "web/playground/app.js",
        "docs/web-playground.md",
    ]
    missing_playground_paths = []
    for item in playground_paths:
        exists, _ = _path_exists(item)
        if not exists:
            missing_playground_paths.append(item)
    demo_paths = [
        "web/demos/index.html",
        "web/demos/app.css",
        "web/demos/app.js",
        "examples/local_action_demos.json",
        "docs/local-desktop-browser-demos.md",
        "scripts/demos/run_local_demos.py",
    ]
    missing_demo_paths = []
    for item in demo_paths:
        exists, _ = _path_exists(item)
        if not exists:
            missing_demo_paths.append(item)
    dashboard_paths = [
        "web/dashboard/index.html",
        "web/dashboard/app.css",
        "web/dashboard/app.js",
        "docs/metrics-dashboard.md",
    ]
    missing_dashboard_paths = []
    for item in dashboard_paths:
        exists, _ = _path_exists(item)
        if not exists:
            missing_dashboard_paths.append(item)
    family_paths = [
        "docs/enterprise/index.html",
        "docs/personal-productivity/index.html",
        "docs/government-civic/index.html",
        "docs/families/data.json",
        "docs/families/family-pack.css",
    ]
    missing_family_paths = []
    for item in family_paths:
        exists, _ = _path_exists(item)
        if not exists:
            missing_family_paths.append(item)
    gates = [
        _gate(
            "bridge_readiness",
            "pass" if readiness["ready"] else "fail",
            "HTTP bridge readiness dependencies pass." if readiness["ready"] else "HTTP bridge readiness dependencies failed.",
            readiness,
        ),
        _gate(
            "bridge_openapi_routes",
            "pass" if not missing_paths else "fail",
            "HTTP bridge OpenAPI includes pilot routes." if not missing_paths else "HTTP bridge OpenAPI is missing pilot routes.",
            {"missing": missing_paths},
        ),
        _gate(
            "bridge_runbook",
            "pass" if docs_exist else "fail",
            "HTTP bridge runbook is present." if docs_exist else "HTTP bridge runbook is missing.",
            {"path": str(docs_path)},
        ),
        _gate(
            "bridge_docker_package",
            "pass" if not missing_docker_paths else "fail",
            "Dockerized HTTP bridge package is present." if not missing_docker_paths else "Dockerized HTTP bridge package is incomplete.",
            {"missing": missing_docker_paths},
        ),
        _gate(
            "bridge_web_playground",
            "pass" if not missing_playground_paths else "fail",
            "Web playground package is present." if not missing_playground_paths else "Web playground package is incomplete.",
            {"missing": missing_playground_paths},
        ),
        _gate(
            "bridge_local_action_demos",
            "pass" if not missing_demo_paths else "fail",
            "Local desktop/browser demo package is present." if not missing_demo_paths else "Local desktop/browser demo package is incomplete.",
            {"missing": missing_demo_paths},
        ),
        _gate(
            "bridge_metrics_dashboard",
            "pass" if not missing_dashboard_paths else "fail",
            "Metrics dashboard package is present." if not missing_dashboard_paths else "Metrics dashboard package is incomplete.",
            {"missing": missing_dashboard_paths},
        ),
        _gate(
            "bridge_family_pages",
            "pass" if not missing_family_paths else "fail",
            "Family landing pages are present." if not missing_family_paths else "Family landing page package is incomplete.",
            {"missing": missing_family_paths},
        ),
    ]
    return _surface("http_bridge", "HTTP Bridge", gates)


def _adapter_path(path):
    candidate = pathlib.Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _adapters_surface(gallery_path):
    gallery = agent_api.load_gallery(gallery_path)
    entries = agent_api.gallery_entries(gallery)
    gallery_report = agent_api.validate_adapter_gallery.validate_gallery(gallery, run_examples=False)
    missing_files = []
    missing_aix = []
    untuned_aix = []
    missing_examples = []
    for entry in entries:
        entry_id = entry.get("id", "<unknown>")
        path = _adapter_path(entry.get("adapter_path", ""))
        if not path.exists():
            missing_files.append({"id": entry_id, "path": str(path)})
            continue
        adapter = agent_api.load_json_file(path)
        aix_config = adapter.get("aix") if isinstance(adapter.get("aix"), dict) else {}
        thresholds = aix_config.get("thresholds") if isinstance(aix_config.get("thresholds"), dict) else {}
        layer_weights = aix_config.get("layer_weights") if isinstance(aix_config.get("layer_weights"), dict) else {}
        if not aix_config:
            missing_aix.append(entry_id)
        elif not aix_config.get("risk_tier") or not isinstance(aix_config.get("beta"), (int, float)):
            untuned_aix.append(entry_id)
        elif not thresholds or not layer_weights:
            untuned_aix.append(entry_id)
        expected = entry.get("expected") if isinstance(entry.get("expected"), dict) else {}
        if not entry.get("prompt") or not entry.get("bad_candidate") or not expected:
            missing_examples.append(entry_id)
    docs_exist, docs_path = _path_exists("docs/adapter-gallery.md")
    gates = [
        _gate(
            "adapter_gallery_shape",
            "pass" if gallery_report["valid"] else "fail",
            "Adapter gallery validates." if gallery_report["valid"] else "Adapter gallery validation failed.",
            {"errors": gallery_report["errors"], "warnings": gallery_report["warnings"], "adapter_count": len(entries)},
            weight=2,
        ),
        _gate(
            "adapter_files",
            "pass" if entries and not missing_files else "fail",
            "All gallery adapter files are present." if entries and not missing_files else "Gallery references missing adapter files.",
            {"missing": missing_files},
        ),
        _gate(
            "adapter_examples",
            "pass" if entries and not missing_examples else "fail",
            "Gallery adapters include executable example inputs and expected outcomes."
            if entries and not missing_examples
            else "Some gallery adapters are missing example inputs or expected outcomes.",
            {"missing": missing_examples},
        ),
        _gate(
            "adapter_aix_tuning",
            "pass" if entries and not missing_aix and not untuned_aix else "fail",
            "Gallery adapters declare AIx risk tier, beta, layer weights, and thresholds."
            if entries and not missing_aix and not untuned_aix
            else "Some gallery adapters are missing explicit AIx tuning.",
            {"missing_aix": missing_aix, "untuned": untuned_aix},
            weight=2,
        ),
        _gate(
            "adapter_gallery_docs",
            "pass" if docs_exist else "fail",
            "Adapter gallery docs are present." if docs_exist else "Adapter gallery docs are missing.",
            {"path": str(docs_path)},
        ),
    ]
    return _surface("adapters", "Adapters", gates)


def _agent_event_surface(evidence_registry_path):
    registry = evidence_registry.load_registry(evidence_registry_path)
    event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
    validation = agent_api.validate_event(event, evidence_registry=registry)
    fixtures = _json_object("examples/agent_event_contract_fixtures.json")
    valid_events = fixtures.get("valid_events", []) if isinstance(fixtures.get("valid_events"), list) else []
    invalid_events = fixtures.get("invalid_events", []) if isinstance(fixtures.get("invalid_events"), list) else []
    schema = agent_contract.AGENT_EVENT_SCHEMA
    gates = [
        _gate(
            "agent_event_schema",
            "pass" if schema.get("title") else "fail",
            "Agent Event schema is available." if schema.get("title") else "Agent Event schema is missing.",
            {"event_version": agent_contract.AGENT_EVENT_VERSION},
        ),
        _gate(
            "agent_event_example",
            "pass" if validation["valid"] else "fail",
            "Agent event example validates." if validation["valid"] else "Agent event example failed validation.",
            validation,
        ),
        _gate(
            "agent_event_fixtures",
            "pass" if valid_events and invalid_events else "fail",
            "Agent event valid/invalid fixtures are present." if valid_events and invalid_events else "Agent event contract fixtures are incomplete.",
            {"valid_events": len(valid_events), "invalid_events": len(invalid_events)},
        ),
    ]
    return _surface("agent_event_contract", "Agent Event Contract", gates)


def _workflow_surface(evidence_registry_path):
    registry = evidence_registry.load_registry(evidence_registry_path)
    request = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary_structured.json")
    batch = agent_api.load_json_file(ROOT / "examples" / "workflow_batch_productive_work.json")
    request_validation = workflow_contract.validate_workflow_request(request)
    batch_validation = workflow_contract.validate_workflow_batch_request(batch)
    evidence_validation = evidence_registry.validate_workflow_evidence(request, registry, require_structured=True)
    examples = _json_object("examples/workflow_contract_examples.json")
    families = examples.get("adapter_families", []) if isinstance(examples.get("adapter_families"), list) else []
    gates = [
        _gate(
            "workflow_request_schema",
            "pass" if workflow_contract.WORKFLOW_REQUEST_SCHEMA.get("title") else "fail",
            "Workflow request schema is available." if workflow_contract.WORKFLOW_REQUEST_SCHEMA.get("title") else "Workflow request schema is missing.",
            {"contract_version": workflow_contract.WORKFLOW_CONTRACT_VERSION},
        ),
        _gate(
            "workflow_example",
            "pass" if request_validation["valid"] and evidence_validation["valid"] else "fail",
            "Structured workflow example validates." if request_validation["valid"] and evidence_validation["valid"] else "Structured workflow example failed validation.",
            {"contract": request_validation, "evidence": evidence_validation},
        ),
        _gate(
            "workflow_batch",
            "pass" if batch_validation["valid"] else "fail",
            "Workflow batch example validates." if batch_validation["valid"] else "Workflow batch example failed validation.",
            batch_validation,
        ),
        _gate(
            "workflow_family_examples",
            "pass" if families else "fail",
            "Canonical workflow family examples are present." if families else "Canonical workflow family examples are missing.",
            {"families": len(families)},
        ),
    ]
    return _surface("workflow_contract", "Workflow Contract", gates)


def _skills_surface():
    docs = [
        "docs/openclaw-skill-conformance.md",
        "docs/openclaw-plugin-install-use.md",
        "examples/openclaw/high-risk-workflow-examples.json",
        "examples/openclaw/aana-runtime-connector-plugin/openclaw.plugin.json",
    ]
    missing = []
    for item in docs:
        exists, _ = _path_exists(item)
        if not exists:
            missing.append(item)
    gates = [
        _gate(
            "skill_conformance_artifacts",
            "pass" if not missing else "fail",
            "Skills/plugins conformance artifacts are present." if not missing else "Skills/plugins conformance artifacts are missing.",
            {"missing": missing},
        )
    ]
    recipe_docs = [
        "docs/integration-recipes.md",
        "docs/recipes/use-aana-with-github-actions.md",
        "docs/recipes/use-aana-with-a-local-agent.md",
        "docs/recipes/use-aana-with-crm-support-drafts.md",
        "docs/recipes/use-aana-for-deployment-reviews.md",
        "docs/recipes/use-aana-in-shadow-mode.md",
    ]
    missing_recipes = []
    for item in recipe_docs:
        exists, _ = _path_exists(item)
        if not exists:
            missing_recipes.append(item)
    gates.append(
        _gate(
            "integration_recipes",
            "pass" if not missing_recipes else "fail",
            "Copyable integration recipes are present." if not missing_recipes else "Copyable integration recipes are missing.",
            {"missing": missing_recipes, "recipe_count": len(recipe_docs) - len(missing_recipes)},
        )
    )
    return _surface("skills_plugins", "Skills/Plugins", gates)


def _evidence_surface(evidence_registry_path):
    registry = evidence_registry.load_registry(evidence_registry_path)
    registry_report = evidence_registry.validate_registry(registry)
    coverage = evidence_integrations.integration_coverage_report(registry=registry)
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
            "workspace_files",
        ],
        now="2026-05-05T01:00:00Z",
    )
    docs_exist, docs_path = _path_exists("docs/evidence-integration-contracts.md")
    gates = [
        _gate(
            "evidence_registry",
            "pass" if registry_report["valid"] else "fail",
            "Evidence registry validates." if registry_report["valid"] else "Evidence registry failed validation.",
            registry_report,
        ),
        _gate(
            "integration_coverage",
            "pass" if coverage["valid"] else "fail",
            "Evidence registry covers integration stubs." if coverage["valid"] else "Evidence registry is missing integration sources.",
            {"missing_source_id_count": coverage["missing_source_id_count"], "integration_count": coverage["integration_count"]},
        ),
        _gate(
            "mock_connector_fixtures",
            "pass" if mock_matrix["valid"] else "fail",
            "Mock evidence connectors normalize successfully." if mock_matrix["valid"] else "Mock evidence connectors failed.",
            {"connector_count": mock_matrix["connector_count"]},
        ),
        _gate(
            "evidence_contract_docs",
            "pass" if docs_exist else "fail",
            "Evidence integration contract docs are present." if docs_exist else "Evidence integration contract docs are missing.",
            {"path": str(docs_path)},
        ),
    ]
    return _surface("evidence", "Evidence", gates)


def _audit_sample_records():
    event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
    event_result = agent_api.check_event(event)
    workflow = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary_structured.json")
    workflow_result = agent_api.check_workflow_request(workflow)
    return [
        agent_api.audit_event_check(event, event_result, created_at="2026-05-05T00:00:00Z"),
        agent_api.audit_workflow_check(workflow, workflow_result, created_at="2026-05-05T00:01:00Z"),
    ]


def _audit_metrics_surface():
    records = _audit_sample_records()
    validation = agent_api.validate_audit_records(records)
    redaction = agent_api.audit_redaction_report(records, forbidden_terms=["4242", "SSN", "password"])
    metrics = agent_api.export_audit_metrics(records, audit_log_path="pilot-certification-sample.jsonl")
    metrics_validation = agent_api.validate_audit_metrics_export(metrics)
    dashboard = agent_api.audit_dashboard(records, audit_log_path="pilot-certification-sample.jsonl")
    drift = agent_api.audit_aix_drift_report(records, baseline_metrics=metrics)
    docs_exist, docs_path = _path_exists("docs/audit-observability-hardening.md")
    gates = [
        _gate(
            "audit_record_schema",
            "pass" if validation["valid"] else "fail",
            "Sample audit records validate." if validation["valid"] else "Sample audit records failed validation.",
            validation,
            weight=2,
        ),
        _gate(
            "audit_redaction",
            "pass" if redaction["valid"] else "fail",
            "Audit redaction check passes." if redaction["valid"] else "Audit redaction check found forbidden terms.",
            redaction,
        ),
        _gate(
            "metrics_export",
            "pass" if metrics_validation["valid"] else "fail",
            "Audit metrics export validates." if metrics_validation["valid"] else "Audit metrics export failed validation.",
            metrics_validation,
            weight=2,
        ),
        _gate(
            "metrics_dashboard_payload",
            "pass" if dashboard.get("record_count") == len(records) and dashboard.get("adapter_breakdown") else "fail",
            "Metrics dashboard payload includes records and adapter breakdown."
            if dashboard.get("record_count") == len(records) and dashboard.get("adapter_breakdown")
            else "Metrics dashboard payload is incomplete.",
            {
                "record_count": dashboard.get("record_count"),
                "adapters": sorted(item.get("id") for item in dashboard.get("adapter_breakdown", []) if isinstance(item, dict)),
            },
        ),
        _gate(
            "aix_drift_report",
            "pass" if isinstance(drift.get("issues"), list) and isinstance(drift.get("metrics"), dict) else "fail",
            "AIx drift report is generated." if isinstance(drift.get("issues"), list) and isinstance(drift.get("metrics"), dict) else "AIx drift report is incomplete.",
            {"valid": drift.get("valid"), "errors": drift.get("errors"), "record_count": drift.get("record_count")},
        ),
        _gate(
            "audit_metrics_docs",
            "pass" if docs_exist else "fail",
            "Audit and observability docs are present." if docs_exist else "Audit and observability docs are missing.",
            {"path": str(docs_path)},
        ),
    ]
    return _surface("audit_metrics", "Audit/Metrics", gates)


def _docs_surface():
    required_docs = [
        "README.md",
        "docs/try-demo/index.md",
        "docs/try-demo/index.html",
        "docs/integrate-runtime/index.md",
        "docs/integrate-runtime/index.html",
        "docs/build-adapter/index.md",
        "docs/build-adapter/index.html",
        "docs/getting-started.md",
        "docs/hosted-demo.md",
        "docs/adapter-gallery.md",
        "docs/adapter-gallery/index.html",
        "docs/adapter-gallery/app.js",
        "docs/adapter-gallery/app.css",
        "docs/adapter-gallery/data.json",
        "docs/enterprise-family.md",
        "docs/enterprise/index.html",
        "docs/personal-productivity/index.html",
        "docs/government-civic/index.html",
        "docs/families/data.json",
        "docs/families/family-pack.css",
        "docs/integration-recipes.md",
        "docs/adapter-integration-sdk.md",
        "docs/agent-integration.md",
        "docs/docker-http-bridge.md",
        "docs/github-action.md",
        "docs/local-desktop-browser-demos.md",
        "docs/metrics-dashboard.md",
        "docs/pilot-evaluation-kit.md",
        "docs/pilot-surface-certification.md",
        "docs/production-certification.md",
        "docs/design-partner-pilots.md",
        "docs/shadow-mode.md",
        "docs/starter-pilot-kits.md",
        "docs/index.html",
        "docs/demo/index.html",
        "docs/demo/app.js",
        "docs/demo/app.css",
        "docs/demo/scenarios.json",
    ]
    missing = []
    for item in required_docs:
        exists, _ = _path_exists(item)
        if not exists:
            missing.append(item)
    gates = [
        _gate(
            "public_docs_bundle",
            "pass" if not missing else "fail",
            "Public docs cover setup, integrations, pilot kits, shadow mode, metrics, and certification."
            if not missing
            else "Public docs bundle is missing required pages.",
            {"missing": missing, "doc_count": len(required_docs) - len(missing)},
            weight=2,
        )
    ]
    return _surface("docs", "Docs", gates)


def _contract_freeze_surface(gallery_path, evidence_registry_path):
    report = contract_freeze.contract_freeze_report(
        gallery_path=gallery_path,
        evidence_registry_path=evidence_registry_path,
    )
    gates = [
        _gate(
            "contract_freeze",
            "pass" if report["valid"] else "fail",
            "Contract freeze passes." if report["valid"] else "Contract freeze failed.",
            report["summary"],
        )
    ]
    return _surface("contract_freeze", "Contract Freeze", gates)


def pilot_readiness_report(
    *,
    gallery_path=None,
    evidence_registry_path=None,
    cli_commands=None,
):
    gallery_path = pathlib.Path(gallery_path or ROOT / "examples" / "adapter_gallery.json")
    evidence_registry_path = pathlib.Path(evidence_registry_path or ROOT / "examples" / "evidence_registry.json")
    surfaces = [
        _cli_surface(cli_commands=cli_commands),
        _python_api_surface(),
        _http_bridge_surface(),
        _adapters_surface(gallery_path),
        _agent_event_surface(evidence_registry_path),
        _workflow_surface(evidence_registry_path),
        _skills_surface(),
        _evidence_surface(evidence_registry_path),
        _audit_metrics_surface(),
        _docs_surface(),
        _contract_freeze_surface(gallery_path, evidence_registry_path),
    ]
    failed = [surface for surface in surfaces if not surface["ready"]]
    warnings = sum(surface["summary"]["warnings"] for surface in surfaces)
    gate_count = sum(surface["summary"]["gates"] for surface in surfaces)
    max_score = sum(surface["max_score"] for surface in surfaces)
    score = sum(surface["score"] for surface in surfaces)
    score_percent = round((score / max_score) * 100, 1) if max_score else 0.0
    readiness_level = _readiness_level(score_percent, len(failed), warnings)
    valid = readiness_level != "not_pilot_ready"
    return {
        "pilot_certification_version": PILOT_CERTIFICATION_VERSION,
        "valid": valid,
        "ready": valid,
        "summary": {
            "status": "pass" if valid else "fail",
            "readiness_level": readiness_level,
            "score": round(score, 2),
            "max_score": max_score,
            "score_percent": score_percent,
            "pilot_ready_threshold": PILOT_READY_SCORE_THRESHOLD,
            "surfaces": len(surfaces),
            "gates": gate_count,
            "failures": len(failed),
            "warnings": warnings,
        },
        "surfaces": surfaces,
    }
