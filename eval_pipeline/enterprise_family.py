"""Enterprise family package and certification checks for AANA."""

from __future__ import annotations

import json
import pathlib

from eval_pipeline import adapter_gallery, agent_api, evidence_integrations, production_certification


ROOT = pathlib.Path(__file__).resolve().parents[1]
ENTERPRISE_FAMILY_VERSION = "0.1"

ENTERPRISE_CORE_ADAPTERS = (
    "crm_support_reply",
    "email_send_guardrail",
    "ticket_update_checker",
    "data_export_guardrail",
    "access_permission_change",
    "code_change_review",
    "deployment_readiness",
    "incident_response_update",
)

ENTERPRISE_EVIDENCE_CONNECTORS = {
    "crm": "crm_support",
    "ticketing": "ticketing",
    "email": "email_send",
    "iam": "iam",
    "ci_github": "ci",
    "deployment": "deployment",
    "billing": "billing",
    "data_warehouse_export": "data_export",
}

ENTERPRISE_AGENT_SKILLS = {
    "support_draft_review": "examples/openclaw/aana-support-reply-guardrail-skill/SKILL.md",
    "release_deployment_gate": "examples/openclaw/aana-release-readiness-check-skill/SKILL.md",
    "code_pr_review": "examples/openclaw/aana-code-change-review-skill/SKILL.md",
    "access_change_approval": "examples/openclaw/aana-access-change-approval-skill/SKILL.md",
    "incident_communications": "examples/openclaw/aana-incident-communications-skill/SKILL.md",
}

ENTERPRISE_PILOT_SURFACES = {
    "docker_bridge": ("Dockerfile", "docker-compose.yml", "docs/docker-http-bridge.md"),
    "github_action": (".github/actions/aana-guardrails/action.yml", "docs/github-action.md"),
    "web_playground": ("web/playground/index.html", "docs/web-playground.md", "docs/enterprise/index.html"),
    "shadow_mode": ("docs/shadow-mode.md",),
    "metrics_dashboard": ("web/dashboard/index.html", "docs/metrics-dashboard.md"),
    "redacted_audit_export": (
        "eval_outputs/starter_pilot_kits/enterprise/audit.jsonl",
        "eval_outputs/starter_pilot_kits/enterprise/metrics.json",
        "eval_outputs/starter_pilot_kits/enterprise/report.json",
    ),
}

DEFAULT_STARTER_KIT = ROOT / "examples" / "starter_pilot_kits" / "enterprise"
DEFAULT_CERTIFICATION_POLICY = ROOT / "examples" / "enterprise_certification_policy.json"
DEFAULT_EVIDENCE_REGISTRY = ROOT / "examples" / "evidence_registry.json"
DEFAULT_MOCK_FIXTURES = ROOT / "examples" / "evidence_mock_connector_fixtures.json"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"

RISK_TIER_MINIMUMS = {
    "elevated": {"accept": 0.88, "revise": 0.68, "defer": 0.52},
    "high": {"accept": 0.91, "revise": 0.72, "defer": 0.56},
    "strict": {"accept": 0.94, "revise": 0.78, "defer": 0.62},
}


def _load_json(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def _path_exists(relative_path):
    path = ROOT / relative_path
    return path.exists(), path


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


def _enterprise_cards(gallery_path):
    gallery = adapter_gallery.published_gallery(gallery_path)
    return {item["id"]: item for item in gallery["adapters"] if "enterprise" in item.get("packs", [])}


def enterprise_core_pack_report(gallery_path=DEFAULT_GALLERY, starter_kit_path=DEFAULT_STARTER_KIT):
    cards = _enterprise_cards(gallery_path)
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
    missing_gallery = sorted(set(ENTERPRISE_CORE_ADAPTERS) - set(cards))
    missing_config = sorted(set(ENTERPRISE_CORE_ADAPTERS) - config_ids)
    missing_workflows = sorted(set(ENTERPRISE_CORE_ADAPTERS) - workflow_ids)
    missing_evidence = sorted(
        adapter_id for adapter_id in ENTERPRISE_CORE_ADAPTERS if adapter_id in cards and not cards[adapter_id].get("required_evidence")
    )
    return _surface(
        "enterprise_core_pack",
        "Enterprise Core Pack",
        [
            _check(
                "core_adapter_membership",
                "pass" if not missing_gallery else "fail",
                "Enterprise gallery contains the required core adapters."
                if not missing_gallery
                else "Enterprise gallery is missing required core adapters.",
                {"required": list(ENTERPRISE_CORE_ADAPTERS), "missing": missing_gallery},
                weight=2,
            ),
            _check(
                "starter_kit_adapter_config",
                "pass" if not missing_config else "fail",
                "Enterprise starter kit config covers all core adapters."
                if not missing_config
                else "Enterprise starter kit config is missing adapters.",
                {"missing": missing_config},
            ),
            _check(
                "starter_kit_workflows",
                "pass" if not missing_workflows else "fail",
                "Enterprise starter kit includes one workflow per core adapter."
                if not missing_workflows
                else "Enterprise starter kit workflows are incomplete.",
                {"missing": missing_workflows, "workflow_count": len(workflow_ids)},
            ),
            _check(
                "required_evidence_declared",
                "pass" if not missing_evidence else "fail",
                "Enterprise core adapters declare required evidence."
                if not missing_evidence
                else "Enterprise core adapters are missing evidence declarations.",
                {"missing": missing_evidence},
            ),
        ],
    )


def enterprise_connector_report(evidence_registry_path=DEFAULT_EVIDENCE_REGISTRY, mock_fixtures_path=DEFAULT_MOCK_FIXTURES):
    registry = agent_api.load_evidence_registry(evidence_registry_path)
    coverage = evidence_integrations.integration_coverage_report(registry=registry)
    covered = {
        item.get("integration_id")
        for item in coverage.get("integrations", [])
        if isinstance(item, dict) and item.get("registry_covered")
    }
    required = set(ENTERPRISE_EVIDENCE_CONNECTORS.values())
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
        "enterprise_evidence_connectors",
        "Enterprise Evidence Connectors",
        [
            _check(
                "connector_contracts",
                "pass" if not missing_stubs else "fail",
                "Enterprise evidence connector contracts are present."
                if not missing_stubs
                else "Enterprise evidence connector contracts are missing.",
                {"required": ENTERPRISE_EVIDENCE_CONNECTORS, "missing": missing_stubs},
                weight=2,
            ),
            _check(
                "registry_coverage",
                "pass" if not missing_registry else "fail",
                "Evidence registry covers enterprise connector source IDs."
                if not missing_registry
                else "Evidence registry is missing enterprise connector source IDs.",
                {"missing": missing_registry},
            ),
            _check(
                "mock_connector_fixtures",
                "pass" if mock.get("valid") and not failing_mocks else "fail",
                "Enterprise mock connectors normalize fresh redacted evidence."
                if mock.get("valid") and not failing_mocks
                else "Enterprise mock connector fixtures failed.",
                {"failing": failing_mocks, "connector_count": mock.get("connector_count")},
            ),
        ],
    )


def enterprise_agent_skills_report():
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
    for skill_id, relative_path in ENTERPRISE_AGENT_SKILLS.items():
        path = ROOT / relative_path
        if not path.exists():
            missing_files.append(relative_path)
            continue
        text = path.read_text(encoding="utf-8")
        absent = [term for term in required_terms if term not in text]
        if absent:
            missing_terms[skill_id] = absent
    return _surface(
        "enterprise_agent_skills",
        "Enterprise Agent Skills",
        [
            _check(
                "skill_files",
                "pass" if not missing_files else "fail",
                "Enterprise agent skills are present." if not missing_files else "Enterprise agent skills are missing.",
                {"skills": ENTERPRISE_AGENT_SKILLS, "missing": missing_files},
                weight=2,
            ),
            _check(
                "runtime_result_boundary",
                "pass" if not missing_terms else "fail",
                "Enterprise skills include AANA runtime result handling."
                if not missing_terms
                else "Enterprise skills are missing runtime result handling terms.",
                {"missing_terms": missing_terms},
            ),
        ],
    )


def enterprise_pilot_surface_report():
    missing = {}
    for surface_id, paths in ENTERPRISE_PILOT_SURFACES.items():
        absent = []
        for relative_path in paths:
            exists, _ = _path_exists(relative_path)
            if not exists:
                absent.append(relative_path)
        if absent:
            missing[surface_id] = absent
    audit_path = ROOT / "eval_outputs" / "starter_pilot_kits" / "enterprise" / "audit.jsonl"
    audit_report = {"valid": False, "redacted": False, "record_count": 0}
    if audit_path.exists():
        records = agent_api.load_audit_records(audit_path)
        validation = agent_api.validate_audit_records(records)
        redaction = agent_api.audit_redaction_report(records)
        audit_report = {
            "valid": validation.get("valid") and redaction.get("valid"),
            "redacted": redaction.get("valid"),
            "record_count": len(records),
            "validation": validation,
            "redaction": redaction,
        }
    return _surface(
        "enterprise_pilot_surface",
        "Enterprise Pilot Surface",
        [
            _check(
                "surface_artifacts",
                "pass" if not missing else "fail",
                "Enterprise pilot surfaces are packaged."
                if not missing
                else "Enterprise pilot surface artifacts are missing.",
                {"missing": missing},
                weight=2,
            ),
            _check(
                "redacted_audit_export",
                "pass" if audit_report.get("valid") else "fail",
                "Enterprise starter kit produced a valid redacted audit export."
                if audit_report.get("valid")
                else "Enterprise redacted audit export is missing or invalid.",
                audit_report,
            ),
        ],
    )


def _aix_threshold_report(cards):
    issues = []
    for adapter_id in ENTERPRISE_CORE_ADAPTERS:
        card = cards.get(adapter_id, {})
        aix = card.get("aix", {}) if isinstance(card.get("aix"), dict) else {}
        tier = aix.get("risk_tier")
        thresholds = aix.get("thresholds", {}) if isinstance(aix.get("thresholds"), dict) else {}
        minimums = RISK_TIER_MINIMUMS.get(tier)
        if not minimums:
            issues.append({"adapter_id": adapter_id, "issue": f"unsupported risk tier {tier!r}"})
            continue
        for key, minimum in minimums.items():
            value = thresholds.get(key)
            if not isinstance(value, (int, float)) or value < minimum:
                issues.append({"adapter_id": adapter_id, "threshold": key, "actual": value, "minimum": minimum})
    return {"valid": not issues, "issues": issues}


def enterprise_certification_report(
    *,
    gallery_path=DEFAULT_GALLERY,
    starter_kit_path=DEFAULT_STARTER_KIT,
    evidence_registry_path=DEFAULT_EVIDENCE_REGISTRY,
    mock_fixtures_path=DEFAULT_MOCK_FIXTURES,
    certification_policy_path=DEFAULT_CERTIFICATION_POLICY,
):
    cards = _enterprise_cards(gallery_path)
    policy = _load_json(certification_policy_path)
    policy_report = production_certification.validate_certification_policy(policy)
    aix_report = _aix_threshold_report(cards)
    surfaces = [
        enterprise_core_pack_report(gallery_path=gallery_path, starter_kit_path=starter_kit_path),
        enterprise_connector_report(evidence_registry_path=evidence_registry_path, mock_fixtures_path=mock_fixtures_path),
        enterprise_agent_skills_report(),
        enterprise_pilot_surface_report(),
        _surface(
            "enterprise_certification",
            "Enterprise Certification",
            [
                _check(
                    "certification_policy",
                    "pass" if policy_report.get("valid") else "fail",
                    "Enterprise production certification policy is defined."
                    if policy_report.get("valid")
                    else "Enterprise production certification policy is invalid.",
                    policy_report,
                    weight=2,
                ),
                _check(
                    "aix_thresholds",
                    "pass" if aix_report["valid"] else "fail",
                    "Enterprise adapters meet risk-tier AIx threshold floors."
                    if aix_report["valid"]
                    else "Enterprise adapters do not meet risk-tier AIx threshold floors.",
                    aix_report,
                ),
                _check(
                    "shadow_mode_pass_window",
                    "pass"
                    if policy.get("shadow_mode", {}).get("minimum_duration_days", 0) >= production_certification.MIN_SHADOW_DURATION_DAYS
                    and policy.get("shadow_mode", {}).get("minimum_records", 0) >= production_certification.MIN_SHADOW_RECORDS
                    else "fail",
                    "Enterprise certification declares a production shadow-mode pass window.",
                    {
                        "minimum_duration_days": policy.get("shadow_mode", {}).get("minimum_duration_days"),
                        "minimum_records": policy.get("shadow_mode", {}).get("minimum_records"),
                    },
                ),
            ],
        ),
    ]
    failures = [surface for surface in surfaces if not surface["ready"]]
    max_score = sum(surface["max_score"] for surface in surfaces)
    score = sum(surface["score"] for surface in surfaces)
    score_percent = round((score / max_score) * 100, 1) if max_score else 0.0
    return {
        "enterprise_family_version": ENTERPRISE_FAMILY_VERSION,
        "valid": not failures,
        "ready": not failures,
        "summary": {
            "status": "pass" if not failures else "fail",
            "readiness_level": "enterprise_phase2_ready" if not failures else "not_enterprise_phase2_ready",
            "score": score,
            "max_score": max_score,
            "score_percent": score_percent,
            "surfaces": len(surfaces),
            "failures": len(failures),
        },
        "core_adapters": list(ENTERPRISE_CORE_ADAPTERS),
        "evidence_connectors": ENTERPRISE_EVIDENCE_CONNECTORS,
        "agent_skills": ENTERPRISE_AGENT_SKILLS,
        "surfaces": surfaces,
    }
