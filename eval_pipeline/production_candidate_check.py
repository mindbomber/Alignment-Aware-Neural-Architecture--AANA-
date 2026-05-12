"""Production-candidate guard for AANA enterprise pilot artifacts."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from eval_pipeline import audit, durable_audit_storage, production_candidate_profile


ROOT = pathlib.Path(__file__).resolve().parents[1]
PRODUCTION_CANDIDATE_CHECK_VERSION = "0.1"
PRODUCTION_CANDIDATE_CHECK_TYPE = "aana_production_candidate_check"
DEFAULT_PRODUCTION_CANDIDATE_PROFILE_PATH = ROOT / "examples" / "production_candidate_profile_enterprise_support.json"


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _load_json(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _optional_json(path: pathlib.Path) -> dict[str, Any] | None:
    return _load_json(path) if path.exists() else None


def _artifact_paths(artifact_dir: str | pathlib.Path | None) -> dict[str, pathlib.Path]:
    if not artifact_dir:
        return {}
    root = pathlib.Path(artifact_dir)
    return {
        "audit_log": root / "audit.jsonl",
        "metrics": root / "metrics.json",
        "dashboard": root / "enterprise-dashboard.json",
        "aix_report": root / "aix-report.json",
        "production_candidate_report": root / "production-candidate-aix-report.json",
        "live_monitoring": root / "live-monitoring-report.json",
        "human_review_summary": root / "human-review-summary.json",
        "human_review_queue": root / "human-review-queue.jsonl",
        "durable_audit": root / "durable-audit.jsonl",
        "durable_manifest": root / "durable-audit.jsonl.sha256.json",
        "connector_smoke": root / "live-connectors-smoke.json",
    }


def production_candidate_check(
    *,
    profile_path: str | pathlib.Path = DEFAULT_PRODUCTION_CANDIDATE_PROFILE_PATH,
    artifact_dir: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    """Validate production-candidate configuration and optional pilot artifacts."""

    issues: list[dict[str, str]] = []
    component_reports: dict[str, Any] = {}
    profile = production_candidate_profile.load_production_candidate_profile(profile_path)
    profile_report = production_candidate_profile.validate_production_candidate_profile(profile)
    component_reports["profile"] = profile_report
    if not profile_report["valid"]:
        issues.extend(_issue(issue["level"], f"profile:{issue['path']}", issue["message"]) for issue in profile_report["issues"])
    else:
        for issue in profile_report["issues"]:
            issues.append(_issue(issue["level"], f"profile:{issue['path']}", issue["message"]))

    paths = _artifact_paths(artifact_dir)
    artifact_summary: dict[str, Any] = {}
    if artifact_dir:
        missing = [name for name, path in paths.items() if name != "production_candidate_report" and not path.exists()]
        for name in missing:
            issues.append(_issue("error", f"artifacts.{name}", f"Required artifact is missing: {paths[name]}"))

        if paths["audit_log"].exists():
            audit_validation = audit.validate_audit_jsonl(paths["audit_log"])
            component_reports["audit_log"] = audit_validation
            if not audit_validation["valid"]:
                issues.extend(_issue(issue["level"], f"audit_log:{issue['path']}", issue["message"]) for issue in audit_validation["issues"])
            artifact_summary["audit_records"] = audit_validation.get("record_count", 0)

        monitoring = _optional_json(paths["live_monitoring"])
        if monitoring:
            component_reports["live_monitoring"] = {
                "status": monitoring.get("status"),
                "healthy": monitoring.get("healthy"),
                "summary": monitoring.get("summary", {}),
            }
            if monitoring.get("status") == "critical":
                issues.append(_issue("warning", "live_monitoring.status", "Live monitoring is critical for this run."))
            elif monitoring.get("status") == "warning":
                issues.append(_issue("warning", "live_monitoring.status", "Live monitoring has warnings."))
            artifact_summary["monitoring_status"] = monitoring.get("status")

        connector_smoke = _optional_json(paths["connector_smoke"])
        if connector_smoke:
            summary = connector_smoke.get("validation", {}).get("summary", {})
            component_reports["connector_smoke"] = connector_smoke.get("summary", {})
            if summary.get("live_approved_count", 0) == 0:
                issues.append(_issue("warning", "connector_smoke.live_approved_count", "No live connectors are approved."))
            if summary.get("write_enabled_count", 0) == 0:
                issues.append(_issue("warning", "connector_smoke.write_enabled_count", "No write connectors are enabled."))
            artifact_summary["connector_executed_count"] = connector_smoke.get("summary", {}).get("executed_count")

        human_review = _optional_json(paths["human_review_summary"])
        if human_review:
            component_reports["human_review"] = {
                "packet_count": human_review.get("packet_count"),
                "raw_payload_logged": human_review.get("raw_payload_logged"),
                "review_status": human_review.get("review_status", {}),
            }
            if human_review.get("raw_payload_logged") is not False:
                issues.append(_issue("error", "human_review.raw_payload_logged", "Human-review export must not log raw payloads."))
            artifact_summary["human_review_packets"] = human_review.get("packet_count", 0)

        if paths["durable_audit"].exists() and paths["durable_manifest"].exists():
            durable_report = durable_audit_storage.verify_durable_audit_storage(
                audit_path=paths["durable_audit"],
                manifest_path=paths["durable_manifest"],
            )
            component_reports["durable_audit_storage"] = durable_report
            if not durable_report["valid"]:
                issues.extend(_issue(issue["level"], f"durable_audit_storage:{issue['path']}", issue["message"]) for issue in durable_report["issues"])
            artifact_summary["durable_audit_valid"] = durable_report["valid"]

        prod_report = _optional_json(paths["production_candidate_report"])
        if prod_report:
            component_reports["production_candidate_report"] = {
                "report_type": prod_report.get("report_type"),
                "recommendation": prod_report.get("deployment_recommendation"),
                "go_live_ready": prod_report.get("executive_summary", {}).get("go_live_ready"),
            }
            boundary = str(prod_report.get("claim_boundary", "")).lower()
            if "not production certification" not in boundary:
                issues.append(_issue("error", "production_candidate_report.claim_boundary", "Report must state this is not production certification."))
            if prod_report.get("executive_summary", {}).get("go_live_ready") is True:
                issues.append(_issue("warning", "production_candidate_report.go_live_ready", "Go-live approval must remain an external decision."))

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    production_candidate_ready = errors == 0 and profile_report.get("production_candidate_ready") is True
    go_live_ready = (
        production_candidate_ready
        and warnings == 0
        and profile_report.get("go_live_ready") is True
        and artifact_summary.get("monitoring_status") == "healthy"
    )
    return {
        "production_candidate_check_version": PRODUCTION_CANDIDATE_CHECK_VERSION,
        "check_type": PRODUCTION_CANDIDATE_CHECK_TYPE,
        "valid": errors == 0,
        "production_candidate_ready": production_candidate_ready,
        "go_live_ready": go_live_ready,
        "status": "fail" if errors else "warn" if warnings else "pass",
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "profile_path": str(profile_path),
        "artifact_dir": str(artifact_dir) if artifact_dir else None,
        "artifact_summary": artifact_summary,
        "component_reports": component_reports,
        "claim_boundary": "Production-candidate readiness only; not production certification or go-live approval.",
    }


__all__ = [
    "DEFAULT_PRODUCTION_CANDIDATE_PROFILE_PATH",
    "PRODUCTION_CANDIDATE_CHECK_TYPE",
    "PRODUCTION_CANDIDATE_CHECK_VERSION",
    "production_candidate_check",
]
