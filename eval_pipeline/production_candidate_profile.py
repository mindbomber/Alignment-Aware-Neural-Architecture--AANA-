"""Production-candidate configuration profile for AANA enterprise support."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from eval_pipeline import enterprise_connector_readiness, enterprise_live_connectors, live_monitoring, production, runtime_human_review


ROOT = pathlib.Path(__file__).resolve().parents[1]
PRODUCTION_CANDIDATE_PROFILE_VERSION = "0.1"
PRODUCTION_CANDIDATE_PROFILE_TYPE = "aana_production_candidate_profile"
DEFAULT_PRODUCTION_CANDIDATE_PROFILE_PATH = ROOT / "examples" / "production_candidate_profile_enterprise_support.json"


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _load_json(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _repo_path(path: str | pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(path)
    return path if path.is_absolute() else ROOT / path


def _write_json(path: str | pathlib.Path, payload: dict[str, Any]) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_production_candidate_profile() -> dict[str, Any]:
    """Return the default enterprise-support production-candidate profile."""

    return {
        "production_candidate_profile_version": PRODUCTION_CANDIDATE_PROFILE_VERSION,
        "profile_type": PRODUCTION_CANDIDATE_PROFILE_TYPE,
        "profile_id": "enterprise_support_email_ticket_candidate",
        "product": "AANA Runtime + AANA AIx Audit",
        "product_bundle": "enterprise_ops_pilot",
        "wedge": "customer support + email send + ticket update",
        "status": "production_candidate_config",
        "claim_boundary": "Production-candidate configuration only; not production certification or go-live approval.",
        "runtime": {
            "default_mode": "shadow",
            "supported_modes": ["dry_run", "shadow", "enforce"],
            "fail_closed_execution": True,
            "direct_execution_rule": {
                "gate_decision": "pass",
                "recommended_action": "accept",
                "hard_blockers": 0,
                "aix_hard_blockers": 0,
                "validation_errors": 0,
            },
            "shadow_mode_writes_disabled": True,
        },
        "artifacts": {
            "deployment_manifest": "examples/production_deployment_internal_pilot.json",
            "governance_policy": "examples/human_governance_policy_internal_pilot.json",
            "observability_policy": "examples/observability_policy.json",
            "audit_retention_policy": "examples/audit_retention_policy_internal_pilot.json",
            "durable_audit_storage": "examples/durable_audit_storage.json",
            "human_review_export": "examples/human_review_queue_export.json",
            "live_monitoring": "examples/live_monitoring_metrics.json",
            "incident_response_plan": "examples/incident_response_plan_internal_pilot.json",
            "connector_readiness": "examples/enterprise_ops_connector_readiness.json",
            "live_connector_config": "examples/enterprise_support_live_connectors.json",
            "aix_audit_kit": "examples/starter_pilot_kits/enterprise",
        },
        "connectors": {
            "required": ["crm_support", "email_send", "ticketing"],
            "live_approval_required": True,
            "write_enabled_requires_live_approval": True,
            "default_config_allows_external_calls": False,
        },
        "human_review": {
            "required_for": ["defer", "refuse", "hard_blocker", "irreversible_send", "customer_visible_ticket_update"],
            "queue": "support_human_review",
            "override_policy": "Overrides must be reviewer-approved and written to redacted audit metadata.",
        },
        "monitoring": {
            "required_metrics": [
                "gate_decision_count",
                "recommended_action_count",
                "aix_score_average",
                "aix_hard_blocker_count",
                "connector_failure_count",
                "evidence_freshness_failure_count",
                "latency",
                "shadow_would_action_count",
            ],
            "drift_check_required": True,
            "dashboard_source_of_truth": "redacted_audit_metrics",
        },
        "promotion_requirements": [
            "Live connector manifests are approved by customer system owners.",
            "Immutable audit retention is configured outside local JSONL.",
            "Human-review queue and SLA are staffed.",
            "Security review covers connector credentials and runtime deployment.",
            "Shadow-mode results meet customer-defined success criteria.",
            "Incident response and rollback paths are tested.",
        ],
    }


def load_production_candidate_profile(path: str | pathlib.Path = DEFAULT_PRODUCTION_CANDIDATE_PROFILE_PATH) -> dict[str, Any]:
    return _load_json(path)


def _validate_artifact(profile: dict[str, Any], key: str, issues: list[dict[str, str]]) -> pathlib.Path | None:
    artifacts = profile.get("artifacts") if isinstance(profile.get("artifacts"), dict) else {}
    value = artifacts.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(_issue("error", f"artifacts.{key}", "Artifact path is required."))
        return None
    path = _repo_path(value)
    if not path.exists():
        issues.append(_issue("error", f"artifacts.{key}", f"Artifact path does not exist: {value}"))
        return None
    return path


def validate_production_candidate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Validate the production-candidate profile and linked config artifacts."""

    issues: list[dict[str, str]] = []
    component_reports: dict[str, Any] = {}
    if not isinstance(profile, dict):
        return {
            "valid": False,
            "production_candidate_ready": False,
            "go_live_ready": False,
            "errors": 1,
            "warnings": 0,
            "issues": [_issue("error", "$", "Production-candidate profile must be a JSON object.")],
            "component_reports": {},
        }

    if profile.get("production_candidate_profile_version") != PRODUCTION_CANDIDATE_PROFILE_VERSION:
        issues.append(_issue("error", "production_candidate_profile_version", f"Must be {PRODUCTION_CANDIDATE_PROFILE_VERSION}."))
    if profile.get("profile_type") != PRODUCTION_CANDIDATE_PROFILE_TYPE:
        issues.append(_issue("error", "profile_type", f"Must be {PRODUCTION_CANDIDATE_PROFILE_TYPE}."))
    if profile.get("product_bundle") != "enterprise_ops_pilot":
        issues.append(_issue("error", "product_bundle", "The first production-candidate profile must target enterprise_ops_pilot."))
    if "not production certification" not in str(profile.get("claim_boundary", "")).lower():
        issues.append(_issue("error", "claim_boundary", "Claim boundary must state this is not production certification."))

    runtime = profile.get("runtime") if isinstance(profile.get("runtime"), dict) else {}
    if runtime.get("fail_closed_execution") is not True:
        issues.append(_issue("error", "runtime.fail_closed_execution", "Runtime execution must be fail-closed."))
    if runtime.get("shadow_mode_writes_disabled") is not True:
        issues.append(_issue("error", "runtime.shadow_mode_writes_disabled", "Shadow mode must disable writes."))
    rule = runtime.get("direct_execution_rule") if isinstance(runtime.get("direct_execution_rule"), dict) else {}
    expected_rule = {
        "gate_decision": "pass",
        "recommended_action": "accept",
        "hard_blockers": 0,
        "aix_hard_blockers": 0,
        "validation_errors": 0,
    }
    for key, expected in expected_rule.items():
        if rule.get(key) != expected:
            issues.append(_issue("error", f"runtime.direct_execution_rule.{key}", f"Direct execution requires {key}={expected!r}."))

    deployment_path = _validate_artifact(profile, "deployment_manifest", issues)
    if deployment_path:
        report = production.validate_deployment_manifest(_load_json(deployment_path))
        component_reports["deployment_manifest"] = report
        if not report["valid"]:
            issues.extend(_issue(issue["level"], f"deployment_manifest:{issue['path']}", issue["message"]) for issue in report["issues"])
        elif not report["production_ready"]:
            issues.append(_issue("warning", "deployment_manifest", "Deployment manifest is valid but has production-readiness warnings."))

    governance_path = _validate_artifact(profile, "governance_policy", issues)
    if governance_path:
        report = production.validate_governance_policy(_load_json(governance_path))
        component_reports["governance_policy"] = report
        if not report["valid"]:
            issues.extend(_issue(issue["level"], f"governance_policy:{issue['path']}", issue["message"]) for issue in report["issues"])
        elif not report["production_ready"]:
            issues.append(_issue("warning", "governance_policy", "Governance policy is valid but has production-readiness warnings."))

    observability_path = _validate_artifact(profile, "observability_policy", issues)
    if observability_path:
        report = production.validate_observability_policy(_load_json(observability_path))
        component_reports["observability_policy"] = report
        if not report["valid"]:
            issues.extend(_issue(issue["level"], f"observability_policy:{issue['path']}", issue["message"]) for issue in report["issues"])
        elif not report["production_ready"]:
            issues.append(_issue("warning", "observability_policy", "Observability policy is valid but has production-readiness warnings."))

    readiness_path = _validate_artifact(profile, "connector_readiness", issues)
    if readiness_path:
        plan = _load_json(readiness_path)
        report = enterprise_connector_readiness.validate_enterprise_connector_readiness_plan(plan)
        component_reports["connector_readiness"] = report
        if not report["valid"]:
            issues.extend(_issue(issue["level"], f"connector_readiness:{issue['path']}", issue["message"]) for issue in report["issues"])

    live_config_path = _validate_artifact(profile, "live_connector_config", issues)
    if live_config_path:
        live_config = enterprise_live_connectors.load_enterprise_live_connector_config(live_config_path)
        report = enterprise_live_connectors.validate_enterprise_live_connector_config(live_config)
        component_reports["live_connector_config"] = report
        if not report["valid"]:
            issues.extend(_issue(issue["level"], f"live_connector_config:{issue['path']}", issue["message"]) for issue in report["issues"])
        summary = report.get("summary", {})
        if summary.get("live_approved_count", 0) < len(enterprise_live_connectors.SUPPORT_ACTION_CONNECTOR_IDS):
            issues.append(_issue("warning", "live_connector_config", "Not all support/email/ticket connectors are live-approved yet."))
        if summary.get("write_enabled_count", 0) == 0:
            issues.append(_issue("warning", "live_connector_config", "No support/email/ticket write connectors are enabled yet."))

    durable_path = _validate_artifact(profile, "durable_audit_storage", issues)
    if durable_path:
        from eval_pipeline import durable_audit_storage

        report = durable_audit_storage.validate_durable_audit_storage_config(_load_json(durable_path))
        component_reports["durable_audit_storage"] = report
        if not report["valid"]:
            issues.extend(_issue(issue["level"], f"durable_audit_storage:{issue['path']}", issue["message"]) for issue in report["issues"])

    human_review_export_path = _validate_artifact(profile, "human_review_export", issues)
    if human_review_export_path:
        report = runtime_human_review.validate_human_review_export_config(_load_json(human_review_export_path))
        component_reports["human_review_export"] = report
        if not report["valid"]:
            issues.extend(_issue(issue["level"], f"human_review_export:{issue['path']}", issue["message"]) for issue in report["issues"])

    live_monitoring_path = _validate_artifact(profile, "live_monitoring", issues)
    if live_monitoring_path:
        report = live_monitoring.validate_live_monitoring_config(_load_json(live_monitoring_path))
        component_reports["live_monitoring"] = report
        if not report["valid"]:
            issues.extend(_issue(issue["level"], f"live_monitoring:{issue['path']}", issue["message"]) for issue in report["issues"])

    for key in ("audit_retention_policy", "incident_response_plan", "aix_audit_kit"):
        _validate_artifact(profile, key, issues)

    connectors = profile.get("connectors") if isinstance(profile.get("connectors"), dict) else {}
    required = set(connectors.get("required") or [])
    missing_required = sorted(set(enterprise_live_connectors.SUPPORT_ACTION_CONNECTOR_IDS) - required)
    if missing_required:
        issues.append(_issue("error", "connectors.required", "Missing required production-candidate connector IDs: " + ", ".join(missing_required)))
    if connectors.get("default_config_allows_external_calls") is not False:
        issues.append(_issue("error", "connectors.default_config_allows_external_calls", "Default profile must not allow external calls."))

    promotion = profile.get("promotion_requirements")
    if not isinstance(promotion, list) or len(promotion) < 5:
        issues.append(_issue("error", "promotion_requirements", "Profile must list concrete promotion requirements."))

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    live_summary = component_reports.get("live_connector_config", {}).get("summary", {})
    go_live_ready = (
        errors == 0
        and warnings == 0
        and live_summary.get("live_approved_count") == len(enterprise_live_connectors.SUPPORT_ACTION_CONNECTOR_IDS)
        and live_summary.get("write_enabled_count", 0) >= 2
    )
    return {
        "valid": errors == 0,
        "production_candidate_ready": errors == 0,
        "go_live_ready": go_live_ready,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "component_reports": component_reports,
        "summary": {
            "profile_id": profile.get("profile_id"),
            "product_bundle": profile.get("product_bundle"),
            "wedge": profile.get("wedge"),
            "status": profile.get("status"),
            "promotion_requirement_count": len(promotion) if isinstance(promotion, list) else 0,
        },
    }


def write_production_candidate_profile(path: str | pathlib.Path = DEFAULT_PRODUCTION_CANDIDATE_PROFILE_PATH) -> dict[str, Any]:
    profile = default_production_candidate_profile()
    validation = validate_production_candidate_profile(profile)
    _write_json(path, profile)
    return {"path": str(path), "profile": profile, "validation": validation}


__all__ = [
    "DEFAULT_PRODUCTION_CANDIDATE_PROFILE_PATH",
    "PRODUCTION_CANDIDATE_PROFILE_TYPE",
    "PRODUCTION_CANDIDATE_PROFILE_VERSION",
    "default_production_candidate_profile",
    "load_production_candidate_profile",
    "validate_production_candidate_profile",
    "write_production_candidate_profile",
]
