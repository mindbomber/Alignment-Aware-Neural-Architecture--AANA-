"""Government and civic family package and certification checks for AANA."""

from __future__ import annotations

import json
import pathlib

from eval_pipeline import adapter_gallery, agent_api, evidence_integrations


ROOT = pathlib.Path(__file__).resolve().parents[1]
CIVIC_FAMILY_VERSION = "0.1"

CIVIC_CORE_ADAPTERS = (
    "procurement_vendor_risk",
    "grant_application_review",
    "insurance_claim_triage",
    "public_records_privacy_redaction",
    "policy_memo_grounding",
    "publication_check",
    "casework_response_checker",
    "foia_public_records_response_checker",
)

CIVIC_EVIDENCE_CONNECTORS = {
    "program_rules": "civic_program_rules",
    "submitted_documents": "civic_program_rules",
    "rubrics": "civic_program_rules",
    "vendor_profiles": "civic_vendor_profiles",
    "public_law_policy_sources": "public_law_policy_sources",
    "redaction_classification_registry": "redaction_classification_registry",
    "case_ticket_history": "civic_case_history",
    "benefits_claims": "benefits_claims",
    "source_registry": "civic_source_registry",
}

CIVIC_AGENT_SKILLS = {
    "benefits_eligibility_boundary": "examples/openclaw/aana-benefits-eligibility-boundary-skill/SKILL.md",
    "procurement_review": "examples/openclaw/aana-procurement-review-skill/SKILL.md",
    "grant_scoring_consistency": "examples/openclaw/aana-grant-scoring-consistency-skill/SKILL.md",
    "policy_memo_grounding": "examples/openclaw/aana-policy-memo-grounding-skill/SKILL.md",
    "public_records_privacy": "examples/openclaw/aana-public-records-privacy-skill/SKILL.md",
    "public_statement_risk": "examples/openclaw/aana-public-statement-risk-skill/SKILL.md",
}

CIVIC_PILOT_SURFACES = {
    "family_landing_page": ("docs/government-civic/index.html", "docs/civic-family.md"),
    "starter_kit": (
        "examples/starter_pilot_kits/civic_government/manifest.json",
        "examples/starter_pilot_kits/civic_government/adapter_config.json",
        "examples/starter_pilot_kits/civic_government/synthetic_data.json",
        "examples/starter_pilot_kits/civic_government/workflows.json",
        "examples/starter_pilot_kits/civic_government/expected_outcomes.json",
    ),
    "redacted_audit_export": (
        "eval_outputs/starter_pilot_kits/civic_government/audit.jsonl",
        "eval_outputs/starter_pilot_kits/civic_government/metrics.json",
        "eval_outputs/starter_pilot_kits/civic_government/report.md",
    ),
}

DEFAULT_STARTER_KIT = ROOT / "examples" / "starter_pilot_kits" / "civic_government"
DEFAULT_CERTIFICATION_POLICY = ROOT / "examples" / "civic_certification_policy.json"
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


def _starter_kit_payload(starter_kit_path):
    starter_kit_path = pathlib.Path(starter_kit_path)
    return {
        "manifest": _load_json(starter_kit_path / "manifest.json"),
        "adapter_config": _load_json(starter_kit_path / "adapter_config.json"),
        "workflows": _load_json(starter_kit_path / "workflows.json"),
        "expected_outcomes": _load_json(starter_kit_path / "expected_outcomes.json"),
        "synthetic_data": _load_json(starter_kit_path / "synthetic_data.json"),
    }


def _civic_cards(gallery_path):
    gallery = adapter_gallery.published_gallery(gallery_path)
    return {item["id"]: item for item in gallery["adapters"] if "government_civic" in item.get("packs", [])}


def _path_exists(relative_path):
    return (ROOT / relative_path).exists()


def civic_core_pack_report(gallery_path=DEFAULT_GALLERY, starter_kit_path=DEFAULT_STARTER_KIT):
    cards = _civic_cards(gallery_path)
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
    missing_gallery = sorted(set(CIVIC_CORE_ADAPTERS) - set(cards))
    missing_config = sorted(set(CIVIC_CORE_ADAPTERS) - config_ids)
    missing_workflows = sorted(set(CIVIC_CORE_ADAPTERS) - workflow_ids)
    missing_evidence = sorted(
        adapter_id for adapter_id in CIVIC_CORE_ADAPTERS if adapter_id in cards and not cards[adapter_id].get("required_evidence")
    )
    return _surface(
        "civic_core_pack",
        "Government/Civic Core Pack",
        [
            _check(
                "core_adapter_membership",
                "pass" if not missing_gallery else "fail",
                "Government/civic gallery contains the required core adapters."
                if not missing_gallery
                else "Government/civic gallery is missing required core adapters.",
                {"required": list(CIVIC_CORE_ADAPTERS), "missing": missing_gallery},
                weight=2,
            ),
            _check(
                "starter_kit_adapter_config",
                "pass" if not missing_config else "fail",
                "Government/civic starter kit config covers all core adapters."
                if not missing_config
                else "Government/civic starter kit config is missing adapters.",
                {"missing": missing_config},
            ),
            _check(
                "starter_kit_workflows",
                "pass" if not missing_workflows else "fail",
                "Government/civic starter kit includes one workflow per core adapter."
                if not missing_workflows
                else "Government/civic starter kit workflows are incomplete.",
                {"missing": missing_workflows, "workflow_count": len(workflow_ids)},
            ),
            _check(
                "required_evidence_declared",
                "pass" if not missing_evidence else "fail",
                "Government/civic core adapters declare required evidence."
                if not missing_evidence
                else "Government/civic core adapters are missing evidence declarations.",
                {"missing": missing_evidence},
            ),
        ],
    )


def civic_connector_report(evidence_registry_path=DEFAULT_EVIDENCE_REGISTRY, mock_fixtures_path=DEFAULT_MOCK_FIXTURES):
    registry = agent_api.load_evidence_registry(evidence_registry_path)
    coverage = evidence_integrations.integration_coverage_report(registry=registry)
    covered = {
        item.get("integration_id")
        for item in coverage.get("integrations", [])
        if isinstance(item, dict) and item.get("registry_covered")
    }
    required = set(CIVIC_EVIDENCE_CONNECTORS.values())
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
        "civic_evidence_connectors",
        "Government/Civic Evidence Connectors",
        [
            _check(
                "connector_contracts",
                "pass" if not missing_stubs else "fail",
                "Government/civic evidence connector contracts are present."
                if not missing_stubs
                else "Government/civic evidence connector contracts are missing.",
                {"required": CIVIC_EVIDENCE_CONNECTORS, "missing": missing_stubs},
                weight=2,
            ),
            _check(
                "registry_coverage",
                "pass" if not missing_registry else "fail",
                "Evidence registry covers government/civic connector source IDs."
                if not missing_registry
                else "Evidence registry is missing government/civic connector source IDs.",
                {"missing": missing_registry},
            ),
            _check(
                "mock_connector_fixtures",
                "pass" if mock.get("valid") and not failing_mocks else "fail",
                "Government/civic mock connectors normalize fresh redacted evidence."
                if mock.get("valid") and not failing_mocks
                else "Government/civic mock connector fixtures failed.",
                {"failing": failing_mocks, "connector_count": mock.get("connector_count")},
            ),
        ],
    )


def civic_agent_skills_report():
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
    for skill_id, relative_path in CIVIC_AGENT_SKILLS.items():
        path = ROOT / relative_path
        if not path.exists():
            missing_files.append(relative_path)
            continue
        text = path.read_text(encoding="utf-8")
        absent = [term for term in required_terms if term not in text]
        if absent:
            missing_terms[skill_id] = absent
    return _surface(
        "civic_agent_skills",
        "Government/Civic Agent Skills",
        [
            _check(
                "skill_files",
                "pass" if not missing_files else "fail",
                "Government/civic agent skills are present."
                if not missing_files
                else "Government/civic agent skills are missing.",
                {"skills": CIVIC_AGENT_SKILLS, "missing": missing_files},
                weight=2,
            ),
            _check(
                "runtime_result_boundary",
                "pass" if not missing_terms else "fail",
                "Government/civic skills include AANA runtime result handling."
                if not missing_terms
                else "Government/civic skills are missing runtime result handling terms.",
                {"missing_terms": missing_terms},
            ),
        ],
    )


def civic_pilot_surface_report():
    missing = {}
    for surface_id, paths in CIVIC_PILOT_SURFACES.items():
        absent = [relative_path for relative_path in paths if not _path_exists(relative_path)]
        if absent:
            missing[surface_id] = absent
    docs = (ROOT / "docs" / "civic-family.md").read_text(encoding="utf-8") if _path_exists("docs/civic-family.md") else ""
    docs_terms = [
        "synthetic-only",
        "jurisdiction/source-law metadata",
        "human review",
        "redacted audit",
        "retention/audit policy",
    ]
    missing_terms = [term for term in docs_terms if term not in docs]
    starter = _starter_kit_payload(DEFAULT_STARTER_KIT)
    synthetic_records = starter["synthetic_data"].get("records", {})
    record_values = synthetic_records.values() if isinstance(synthetic_records, dict) else synthetic_records
    synthetic_only = bool(synthetic_records) and all(
        "synthetic" in json.dumps(record, sort_keys=True).lower()
        or "source_id" in json.dumps(record, sort_keys=True).lower()
        for record in record_values
    )
    return _surface(
        "civic_pilot_surface",
        "Government/Civic Pilot Surface",
        [
            _check(
                "surface_artifacts",
                "pass" if not missing else "fail",
                "Government/civic pilot surfaces are packaged."
                if not missing
                else "Government/civic pilot surface artifacts are missing.",
                {"missing": missing},
                weight=2,
            ),
            _check(
                "synthetic_only_bundle",
                "pass" if synthetic_only else "fail",
                "Government/civic starter kit uses synthetic structured records."
                if synthetic_only
                else "Government/civic starter kit is not clearly synthetic-only.",
                {"record_count": len(synthetic_records)},
            ),
            _check(
                "pilot_guidance",
                "pass" if not missing_terms else "fail",
                "Government/civic docs state jurisdiction/source-law metadata, privacy redaction, human review, and audit expectations."
                if not missing_terms
                else "Government/civic docs are missing pilot-surface guidance.",
                {"missing_terms": missing_terms},
            ),
        ],
    )


def _audit_report():
    audit_path = ROOT / "eval_outputs" / "starter_pilot_kits" / "civic_government" / "audit.jsonl"
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


def _civic_policy_report(policy):
    required_true = [
        "synthetic_only_default",
        "jurisdiction_labeling_required",
        "source_law_traceability_required",
        "privacy_redaction_required",
        "human_review_required_for_final_determinations",
        "public_records_retention_audit_required",
        "redacted_audit_only",
    ]
    missing_true = [key for key in required_true if policy.get(key) is not True]
    required_outputs = ["audit.jsonl", "metrics.json", "report.md"]
    outputs = policy.get("exportable_outputs", [])
    missing_outputs = [item for item in required_outputs if item not in outputs]
    declared_connectors = set(policy.get("required_evidence_connectors", []))
    missing_connectors = sorted(set(CIVIC_EVIDENCE_CONNECTORS.values()) - declared_connectors)
    return {
        "valid": not missing_true and not missing_outputs and not missing_connectors,
        "missing_true_controls": missing_true,
        "missing_outputs": missing_outputs,
        "missing_connectors": missing_connectors,
    }


def civic_certification_report(
    *,
    gallery_path=DEFAULT_GALLERY,
    starter_kit_path=DEFAULT_STARTER_KIT,
    evidence_registry_path=DEFAULT_EVIDENCE_REGISTRY,
    mock_fixtures_path=DEFAULT_MOCK_FIXTURES,
    certification_policy_path=DEFAULT_CERTIFICATION_POLICY,
):
    policy = _load_json(certification_policy_path)
    policy_report = _civic_policy_report(policy)
    audit_report = _audit_report()
    report_paths = [
        ROOT / "eval_outputs" / "starter_pilot_kits" / "civic_government" / "metrics.json",
        ROOT / "eval_outputs" / "starter_pilot_kits" / "civic_government" / "report.md",
    ]
    missing_reports = [str(path) for path in report_paths if not path.exists()]
    surfaces = [
        civic_core_pack_report(gallery_path=gallery_path, starter_kit_path=starter_kit_path),
        civic_connector_report(evidence_registry_path=evidence_registry_path, mock_fixtures_path=mock_fixtures_path),
        civic_agent_skills_report(),
        civic_pilot_surface_report(),
        _surface(
            "civic_certification",
            "Government/Civic Certification",
            [
                _check(
                    "civic_policy",
                    "pass" if policy_report["valid"] else "fail",
                    "Government/civic certification policy defines source-law, jurisdiction, redaction, human-review, audit, and output controls."
                    if policy_report["valid"]
                    else "Government/civic certification policy is missing required controls.",
                    policy_report,
                    weight=2,
                ),
                _check(
                    "redacted_audit_export",
                    "pass" if audit_report["valid"] and audit_report["redacted"] else "fail",
                    "Government/civic starter kit produced a valid redacted audit export."
                    if audit_report["valid"] and audit_report["redacted"]
                    else "Government/civic redacted audit export is missing or invalid.",
                    audit_report,
                ),
                _check(
                    "reviewer_report",
                    "pass" if not missing_reports else "fail",
                    "Government/civic starter kit produced exportable metrics and Markdown report."
                    if not missing_reports
                    else "Government/civic starter kit exportable reports are missing.",
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
        "civic_family_version": CIVIC_FAMILY_VERSION,
        "valid": not failures,
        "ready": not failures,
        "summary": {
            "status": "pass" if not failures else "fail",
            "readiness_level": "civic_phase4_ready" if not failures else "not_civic_phase4_ready",
            "score": score,
            "max_score": max_score,
            "score_percent": score_percent,
            "surfaces": len(surfaces),
            "failures": len(failures),
        },
        "core_adapters": list(CIVIC_CORE_ADAPTERS),
        "evidence_connectors": CIVIC_EVIDENCE_CONNECTORS,
        "agent_skills": CIVIC_AGENT_SKILLS,
        "surfaces": surfaces,
    }
