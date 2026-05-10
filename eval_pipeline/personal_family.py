"""Personal productivity family package and certification checks for AANA."""

from __future__ import annotations

import json
import pathlib

from eval_pipeline import adapter_gallery, agent_api, evidence_integrations


ROOT = pathlib.Path(__file__).resolve().parents[1]
PEER_REVIEW_EVIDENCE = ROOT / "docs" / "evidence" / "peer_review"
PERSONAL_FAMILY_VERSION = "0.1"

PERSONAL_CORE_ADAPTERS = (
    "email_send_guardrail",
    "calendar_scheduling",
    "file_operation_guardrail",
    "booking_purchase_guardrail",
    "research_answer_grounding",
    "publication_check",
    "meeting_summary_checker",
)

PERSONAL_EVIDENCE_CONNECTORS = {
    "local_files": "workspace_files",
    "email_draft_metadata": "email_send",
    "calendar_freebusy": "calendar",
    "browser_cart_quote": "browser_cart_quote",
    "citation_source_registry": "citation_source_registry",
    "local_approval_state": "local_approval",
}

PERSONAL_AGENT_SKILLS = {
    "before_i_send": "examples/openclaw/aana-email-send-guardrail-skill/SKILL.md",
    "before_i_delete_move_write": "examples/openclaw/aana-file-operation-guardrail-skill/SKILL.md",
    "before_i_book_buy": "examples/openclaw/aana-purchase-booking-guardrail-skill/SKILL.md",
    "before_i_answer_with_citations": "examples/openclaw/aana-research-grounding-skill/SKILL.md",
    "before_i_schedule": "examples/openclaw/aana-calendar-scheduling-guardrail-skill/SKILL.md",
}

PERSONAL_DEMO_ARTIFACTS = {
    "browser_ui": ("web/demos/index.html", "web/demos/app.js", "web/demos/app.css"),
    "scenario_bundle": ("examples/local_action_demos.json",),
    "demo_docs": ("docs/local-desktop-browser-demos.md",),
}

DEFAULT_STARTER_KIT = ROOT / "examples" / "starter_pilot_kits" / "personal_productivity"
DEFAULT_CERTIFICATION_POLICY = ROOT / "examples" / "personal_certification_policy.json"
DEFAULT_EVIDENCE_REGISTRY = ROOT / "examples" / "evidence_registry.json"
DEFAULT_MOCK_FIXTURES = ROOT / "examples" / "evidence_mock_connector_fixtures.json"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"


def _load_json(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def _check(check_id, status, message, details=None, weight=1):
    return {
        "id": check_id,
        "status": status,
        "message": message,
        "details": details or {},
        "weight": weight,
        "score": weight if status == "pass" else 0,
    }


def _surface(surface_id, title, checks):
    failures = [item for item in checks if item["status"] == "fail"]
    max_score = sum(item.get("weight", 1) for item in checks)
    score = sum(item.get("score", 0) for item in checks)
    score_percent = round((score / max_score) * 100, 1) if max_score else 0.0
    return {
        "surface_id": surface_id,
        "title": title,
        "status": "fail" if failures else "pass",
        "ready": not failures,
        "score": score,
        "max_score": max_score,
        "score_percent": score_percent,
        "summary": {
            "checks": len(checks),
            "failures": len(failures),
            "score_percent": score_percent,
        },
        "checks": checks,
    }


def _path_exists(relative_path):
    return (ROOT / relative_path).exists()


def _starter_kit_payload(starter_kit_path):
    starter_kit_path = pathlib.Path(starter_kit_path)
    return {
        "manifest": _load_json(starter_kit_path / "manifest.json"),
        "adapter_config": _load_json(starter_kit_path / "adapter_config.json"),
        "workflows": _load_json(starter_kit_path / "workflows.json"),
        "expected_outcomes": _load_json(starter_kit_path / "expected_outcomes.json"),
        "synthetic_data": _load_json(starter_kit_path / "synthetic_data.json"),
    }


def _personal_cards(gallery_path):
    gallery = adapter_gallery.published_gallery(gallery_path)
    return {item["id"]: item for item in gallery["adapters"] if "personal_productivity" in item.get("packs", [])}


def personal_core_pack_report(gallery_path=DEFAULT_GALLERY, starter_kit_path=DEFAULT_STARTER_KIT):
    cards = _personal_cards(gallery_path)
    starter = _starter_kit_payload(starter_kit_path)
    config_ids = {
        item.get("adapter_id")
        for item in starter["adapter_config"].get("adapters", [])
        if isinstance(item, dict)
    }
    workflow_ids = {
        item.get("adapter_id")
        for item in starter["workflows"].get("workflows", [])
        if isinstance(item, dict)
    }
    missing_gallery = sorted(set(PERSONAL_CORE_ADAPTERS) - set(cards))
    missing_config = sorted(set(PERSONAL_CORE_ADAPTERS) - config_ids)
    missing_workflows = sorted(set(PERSONAL_CORE_ADAPTERS) - workflow_ids)
    missing_evidence = sorted(
        adapter_id for adapter_id in PERSONAL_CORE_ADAPTERS if adapter_id in cards and not cards[adapter_id].get("required_evidence")
    )
    return _surface(
        "personal_core_pack",
        "Personal Core Pack",
        [
            _check(
                "core_adapter_membership",
                "pass" if not missing_gallery else "fail",
                "Personal gallery contains the required core adapters."
                if not missing_gallery
                else "Personal gallery is missing required core adapters.",
                {"required": list(PERSONAL_CORE_ADAPTERS), "missing": missing_gallery},
                weight=2,
            ),
            _check(
                "starter_kit_adapter_config",
                "pass" if not missing_config else "fail",
                "Personal starter kit config covers all core adapters."
                if not missing_config
                else "Personal starter kit config is missing adapters.",
                {"missing": missing_config},
            ),
            _check(
                "starter_kit_workflows",
                "pass" if not missing_workflows else "fail",
                "Personal starter kit includes one workflow per core adapter."
                if not missing_workflows
                else "Personal starter kit workflows are incomplete.",
                {"missing": missing_workflows, "workflow_count": len(workflow_ids)},
            ),
            _check(
                "required_evidence_declared",
                "pass" if not missing_evidence else "fail",
                "Personal core adapters declare required evidence."
                if not missing_evidence
                else "Personal core adapters are missing evidence declarations.",
                {"missing": missing_evidence},
            ),
        ],
    )


def personal_connector_report(evidence_registry_path=DEFAULT_EVIDENCE_REGISTRY, mock_fixtures_path=DEFAULT_MOCK_FIXTURES):
    registry = agent_api.load_evidence_registry(evidence_registry_path)
    coverage = evidence_integrations.integration_coverage_report(registry=registry)
    covered = {
        item.get("integration_id")
        for item in coverage.get("integrations", [])
        if isinstance(item, dict) and item.get("registry_covered")
    }
    required = set(PERSONAL_EVIDENCE_CONNECTORS.values())
    missing_stubs = sorted(
        integration_id
        for integration_id in required
        if not any(stub.integration_id == integration_id for stub in evidence_integrations.all_integration_stubs())
    )
    missing_registry = sorted(required - covered)
    fixtures = evidence_integrations.load_mock_connector_fixtures(mock_fixtures_path)
    mock = evidence_integrations.mock_connector_matrix(
        fixtures=fixtures,
        integration_ids=sorted(required),
        now="2026-05-05T01:00:00Z",
    )
    failing_mocks = [
        item["integration_id"]
        for item in mock.get("reports", [])
        if isinstance(item, dict) and not item.get("valid")
    ]
    return _surface(
        "personal_evidence_connectors",
        "Personal Evidence Connectors",
        [
            _check(
                "connector_contracts",
                "pass" if not missing_stubs else "fail",
                "Personal evidence connector contracts are present."
                if not missing_stubs
                else "Personal evidence connector contracts are missing.",
                {"required": PERSONAL_EVIDENCE_CONNECTORS, "missing": missing_stubs},
                weight=2,
            ),
            _check(
                "registry_coverage",
                "pass" if not missing_registry else "fail",
                "Evidence registry covers personal connector source IDs."
                if not missing_registry
                else "Evidence registry is missing personal connector source IDs.",
                {"missing": missing_registry},
            ),
            _check(
                "mock_connector_fixtures",
                "pass" if mock.get("valid") and not failing_mocks else "fail",
                "Personal mock connectors normalize fresh redacted evidence."
                if mock.get("valid") and not failing_mocks
                else "Personal mock connector fixtures failed.",
                {"failing": failing_mocks, "connector_count": mock.get("connector_count")},
            ),
        ],
    )


def personal_agent_skills_report():
    required_terms = [
        "## AANA Runtime Result Handling",
        "`gate_decision`",
        "`recommended_action`",
        "`aix.hard_blockers`",
        "`candidate_aix`",
        "redacted decision metadata",
    ]
    missing_files = []
    missing_terms = {}
    for skill_id, relative_path in PERSONAL_AGENT_SKILLS.items():
        path = ROOT / relative_path
        if not path.exists():
            missing_files.append(relative_path)
            continue
        text = path.read_text(encoding="utf-8")
        absent = [term for term in required_terms if term not in text]
        if absent:
            missing_terms[skill_id] = absent
    return _surface(
        "personal_agent_skills",
        "Personal Agent Skills",
        [
            _check(
                "skill_files",
                "pass" if not missing_files else "fail",
                "Personal agent skills are present." if not missing_files else "Personal agent skills are missing.",
                {"skills": PERSONAL_AGENT_SKILLS, "missing": missing_files},
                weight=2,
            ),
            _check(
                "runtime_result_boundary",
                "pass" if not missing_terms else "fail",
                "Personal skills include AANA runtime result handling."
                if not missing_terms
                else "Personal skills are missing runtime result handling terms.",
                {"missing_terms": missing_terms},
            ),
        ],
    )


def personal_demo_surface_report():
    missing = {}
    for surface_id, paths in PERSONAL_DEMO_ARTIFACTS.items():
        absent = [relative_path for relative_path in paths if not _path_exists(relative_path)]
        if absent:
            missing[surface_id] = absent
    demos = _load_json(ROOT / "examples" / "local_action_demos.json")
    demo_ids = {item.get("adapter_id") for item in demos.get("demos", []) if isinstance(item, dict)}
    missing_demos = sorted(set(PERSONAL_CORE_ADAPTERS) - demo_ids)
    index = (ROOT / "web" / "demos" / "index.html").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "local-desktop-browser-demos.md").read_text(encoding="utf-8")
    missing_tabs = [
        demo.get("id")
        for demo in demos.get("demos", [])
        if isinstance(demo, dict) and f'data-demo="{demo.get("id")}"' not in index
    ]
    local_only_terms = [
        "synthetic evidence",
        "same redacted audit record",
        "real pilots",
        "direct action blocked",
    ]
    missing_terms = [term for term in local_only_terms if term not in docs]
    return _surface(
        "personal_demo_app",
        "Personal Demo App",
        [
            _check(
                "demo_artifacts",
                "pass" if not missing else "fail",
                "Personal browser demo artifacts are packaged."
                if not missing
                else "Personal browser demo artifacts are missing.",
                {"missing": missing},
                weight=2,
            ),
            _check(
                "core_demo_scenarios",
                "pass" if not missing_demos else "fail",
                "Personal demo scenarios cover the core adapters."
                if not missing_demos
                else "Personal demo scenarios are missing core adapters.",
                {"missing": missing_demos, "demo_count": len(demos.get("demos", []))},
            ),
            _check(
                "browser_tabs",
                "pass" if not missing_tabs else "fail",
                "Personal browser UI exposes each local demo."
                if not missing_tabs
                else "Personal browser UI is missing demo tabs.",
                {"missing": missing_tabs},
            ),
            _check(
                "local_only_guidance",
                "pass" if not missing_terms else "fail",
                "Personal demo docs state local-only synthetic evidence and no direct action by default."
                if not missing_terms
                else "Personal demo docs are missing local-only guidance.",
                {"missing_terms": missing_terms},
            ),
        ],
    )


def _audit_report():
    audit_path = PEER_REVIEW_EVIDENCE / "starter_pilot_kits" / "personal_productivity" / "audit.jsonl"
    if not audit_path.exists():
        return {"valid": False, "redacted": False, "record_count": 0, "audit_log": str(audit_path)}
    records = agent_api.load_audit_records(audit_path)
    validation = agent_api.validate_audit_records(records)
    redaction = agent_api.audit_redaction_report(records)
    return {
        "valid": validation.get("valid") and redaction.get("valid"),
        "redacted": redaction.get("valid"),
        "record_count": len(records),
        "audit_log": str(audit_path),
        "validation": validation,
        "redaction": redaction,
    }


def _personal_policy_report(policy):
    required_true = [
        "local_only_default",
        "shadow_mode_available",
        "no_irreversible_action_without_explicit_approval",
        "redacted_audit_only",
        "exportable_report_required",
    ]
    missing_true = [key for key in required_true if policy.get(key) is not True]
    required_outputs = ["audit.jsonl", "metrics.json", "report.md"]
    outputs = policy.get("exportable_outputs", [])
    missing_outputs = [item for item in required_outputs if item not in outputs]
    return {
        "valid": not missing_true and not missing_outputs,
        "missing_true_controls": missing_true,
        "missing_outputs": missing_outputs,
    }


def personal_certification_report(
    *,
    gallery_path=DEFAULT_GALLERY,
    starter_kit_path=DEFAULT_STARTER_KIT,
    evidence_registry_path=DEFAULT_EVIDENCE_REGISTRY,
    mock_fixtures_path=DEFAULT_MOCK_FIXTURES,
    certification_policy_path=DEFAULT_CERTIFICATION_POLICY,
):
    policy = _load_json(certification_policy_path)
    policy_report = _personal_policy_report(policy)
    audit_report = _audit_report()
    report_paths = [
        PEER_REVIEW_EVIDENCE / "starter_pilot_kits" / "personal_productivity" / "metrics.json",
        PEER_REVIEW_EVIDENCE / "starter_pilot_kits" / "personal_productivity" / "report.md",
    ]
    missing_reports = [str(path) for path in report_paths if not path.exists()]
    surfaces = [
        personal_core_pack_report(gallery_path=gallery_path, starter_kit_path=starter_kit_path),
        personal_connector_report(evidence_registry_path=evidence_registry_path, mock_fixtures_path=mock_fixtures_path),
        personal_agent_skills_report(),
        personal_demo_surface_report(),
        _surface(
            "personal_certification",
            "Personal Certification",
            [
                _check(
                    "personal_safety_policy",
                    "pass" if policy_report["valid"] else "fail",
                    "Personal certification policy defines local-only, approval, redaction, shadow-mode, and export controls."
                    if policy_report["valid"]
                    else "Personal certification policy is missing required controls.",
                    policy_report,
                    weight=2,
                ),
                _check(
                    "redacted_audit_export",
                    "pass" if audit_report["valid"] and audit_report["redacted"] else "fail",
                    "Personal starter kit produced a valid redacted audit export."
                    if audit_report["valid"] and audit_report["redacted"]
                    else "Personal redacted audit export is missing or invalid.",
                    audit_report,
                ),
                _check(
                    "exportable_report",
                    "pass" if not missing_reports else "fail",
                    "Personal starter kit produced exportable metrics and Markdown report."
                    if not missing_reports
                    else "Personal starter kit exportable reports are missing.",
                    {"missing": missing_reports},
                ),
            ],
        ),
    ]
    failures = [surface for surface in surfaces if not surface["ready"]]
    max_score = sum(surface["max_score"] for surface in surfaces)
    score = sum(surface["score"] for surface in surfaces)
    score_percent = round((score / max_score) * 100, 1) if max_score else 0.0
    return {
        "personal_family_version": PERSONAL_FAMILY_VERSION,
        "valid": not failures,
        "ready": not failures,
        "summary": {
            "status": "pass" if not failures else "fail",
            "readiness_level": "personal_phase3_ready" if not failures else "not_personal_phase3_ready",
            "score": score,
            "max_score": max_score,
            "score_percent": score_percent,
            "surfaces": len(surfaces),
            "failures": len(failures),
        },
        "core_adapters": list(PERSONAL_CORE_ADAPTERS),
        "evidence_connectors": PERSONAL_EVIDENCE_CONNECTORS,
        "agent_skills": PERSONAL_AGENT_SKILLS,
        "surfaces": surfaces,
    }
