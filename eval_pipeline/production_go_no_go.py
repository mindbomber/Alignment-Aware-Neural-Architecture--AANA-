"""Final production go/no-go gate for AANA MI release artifacts."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline.human_signoff import DEFAULT_HUMAN_SIGNOFF_PATH, validate_human_signoff_record
from eval_pipeline.mi_release_bundle import DEFAULT_MI_RELEASE_BUNDLE_DIR
from eval_pipeline.mi_release_bundle_verification import DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH
from eval_pipeline.post_release_monitoring import (
    DEFAULT_POST_RELEASE_MONITORING_POLICY_PATH,
    validate_post_release_monitoring_policy,
)
from eval_pipeline.production_deployment_manifest import (
    DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH,
    validate_production_deployment_manifest,
)
from eval_pipeline.production_dry_run import DEFAULT_PRODUCTION_DRY_RUN_REPORT_PATH


PRODUCTION_GO_NO_GO_VERSION = "0.1"
PRODUCTION_GO_NO_GO_REPORT_TYPE = "aana_mi_production_go_no_go_report"
DEFAULT_PRODUCTION_GO_NO_GO_REPORT_PATH = DEFAULT_MI_RELEASE_BUNDLE_DIR / "production_go_no_go_report.json"
DEFAULT_RELEASE_MANIFEST_PATH = DEFAULT_MI_RELEASE_BUNDLE_DIR / "release_manifest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _artifact_ref(path: pathlib.Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": _sha256_file(path) if path.exists() else None,
        "bytes": path.stat().st_size if path.exists() else None,
    }


def _decision(name: str, status: str, details: str, *, required_for_go: bool = True) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "required_for_go": required_for_go,
        "details": details,
    }


def production_go_no_go_report(
    *,
    release_manifest_path: str | pathlib.Path = DEFAULT_RELEASE_MANIFEST_PATH,
    bundle_verification_path: str | pathlib.Path = DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH,
    human_signoff_path: str | pathlib.Path = DEFAULT_HUMAN_SIGNOFF_PATH,
    deployment_manifest_path: str | pathlib.Path = DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH,
    monitoring_policy_path: str | pathlib.Path = DEFAULT_POST_RELEASE_MONITORING_POLICY_PATH,
    dry_run_report_path: str | pathlib.Path = DEFAULT_PRODUCTION_DRY_RUN_REPORT_PATH,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Combine final production release controls into one go/no-go report."""

    release_path = pathlib.Path(release_manifest_path)
    verification_path = pathlib.Path(bundle_verification_path)
    signoff_path = pathlib.Path(human_signoff_path)
    deployment_path = pathlib.Path(deployment_manifest_path)
    monitoring_path = pathlib.Path(monitoring_policy_path)
    dry_run_path = pathlib.Path(dry_run_report_path)

    release_manifest = _load_json(release_path)
    verification = _load_json(verification_path)
    signoff = _load_json(signoff_path)
    deployment = _load_json(deployment_path)
    monitoring = _load_json(monitoring_path)
    dry_run = _load_json(dry_run_path)

    signoff_validation = validate_human_signoff_record(signoff)
    deployment_validation = validate_production_deployment_manifest(deployment)
    monitoring_validation = validate_post_release_monitoring_policy(monitoring)
    global_aix = release_manifest.get("global_aix") if isinstance(release_manifest.get("global_aix"), dict) else {}
    global_aix_score = global_aix.get("score")
    global_aix_threshold = global_aix.get("accept_threshold", 0.0)

    decisions = [
        _decision("release_candidate", release_manifest.get("rc_status"), "Release candidate status from verified bundle."),
        _decision("production_readiness", release_manifest.get("readiness_status"), "Production readiness status from verified bundle."),
        _decision("release_bundle_verification", verification.get("status"), f"issues={verification.get('issue_count')} artifacts={verification.get('artifact_count')}"),
        _decision("global_aix", "pass" if isinstance(global_aix_score, (int, float)) and float(global_aix_score) >= float(global_aix_threshold) else "block", f"score={global_aix_score} threshold={global_aix_threshold}"),
        _decision("human_signoff", signoff.get("decision"), f"valid={signoff_validation['valid']} reviewer={signoff.get('reviewer', {}).get('id')}"),
        _decision("deployment_manifest", deployment.get("deployment_status"), f"valid={deployment_validation['valid']} blockers={len(deployment.get('blockers', []))}"),
        _decision("monitoring_policy", "pass" if monitoring_validation["valid"] else "block", f"alerts={len(monitoring.get('alerts', []))} metrics={len(monitoring.get('metrics', []))}"),
        _decision("production_dry_run", dry_run.get("status"), f"unresolved={dry_run.get('unresolved_item_count')} live_actions={dry_run.get('live_external_actions_attempted')}"),
    ]

    blockers: list[dict[str, str]] = []
    if release_manifest.get("rc_status") != "pass":
        blockers.append({"code": "release_candidate_not_pass", "source": "release_manifest", "required_action": "rerun and pass the MI release candidate."})
    if release_manifest.get("readiness_status") != "ready":
        blockers.append({"code": "readiness_not_ready", "source": "release_manifest", "required_action": "resolve production readiness blockers."})
    if verification.get("status") != "pass":
        blockers.append({"code": "release_bundle_verification_not_pass", "source": "release_bundle_verification", "required_action": "repair bundle verification issues."})
    if not isinstance(global_aix_score, (int, float)) or float(global_aix_score) < float(global_aix_threshold):
        blockers.append({"code": "global_aix_below_threshold", "source": "release_manifest", "required_action": "resolve workflow drift and rerun global AIx."})
    if not signoff_validation["valid"]:
        blockers.append({"code": "human_signoff_invalid", "source": "human_signoff", "required_action": "repair human signoff record."})
    if signoff.get("decision") != "approved":
        blockers.append({"code": "human_signoff_not_approved", "source": "human_signoff", "required_action": "obtain domain-owner approval before production go."})
    if not deployment_validation["valid"]:
        blockers.append({"code": "deployment_manifest_invalid", "source": "production_deployment_manifest", "required_action": "repair deployment manifest validation issues."})
    if deployment.get("deployment_authorized") is not True:
        blockers.append({"code": "deployment_not_authorized", "source": "production_deployment_manifest", "required_action": "resolve deployment manifest blockers before live deployment."})
    if not monitoring_validation["valid"]:
        blockers.append({"code": "monitoring_policy_invalid", "source": "post_release_monitoring_policy", "required_action": "repair monitoring policy before production go."})
    if dry_run.get("live_external_actions_attempted") is not False:
        blockers.append({"code": "dry_run_attempted_live_actions", "source": "production_dry_run_report", "required_action": "rerun dry run with live external actions disabled."})
    if dry_run.get("status") != "pass":
        blockers.append({"code": "production_dry_run_not_pass", "source": "production_dry_run_report", "required_action": "resolve dry-run unresolved items."})

    status = "go" if not blockers else "no_go"
    return {
        "production_go_no_go_version": PRODUCTION_GO_NO_GO_VERSION,
        "report_type": PRODUCTION_GO_NO_GO_REPORT_TYPE,
        "created_at": created_at or _utc_now(),
        "status": status,
        "go": status == "go",
        "blocker_count": len(blockers),
        "blockers": blockers,
        "artifact_refs": {
            "release_manifest": _artifact_ref(release_path),
            "release_bundle_verification": _artifact_ref(verification_path),
            "human_signoff": _artifact_ref(signoff_path),
            "production_deployment_manifest": _artifact_ref(deployment_path),
            "post_release_monitoring_policy": _artifact_ref(monitoring_path),
            "production_dry_run_report": _artifact_ref(dry_run_path),
        },
        "decisions": decisions,
        "summary": {
            "rc_status": release_manifest.get("rc_status"),
            "readiness_status": release_manifest.get("readiness_status"),
            "bundle_verification_status": verification.get("status"),
            "human_signoff_decision": signoff.get("decision"),
            "deployment_status": deployment.get("deployment_status"),
            "deployment_authorized": deployment.get("deployment_authorized"),
            "monitoring_policy_valid": monitoring_validation["valid"],
            "dry_run_status": dry_run.get("status"),
            "dry_run_unresolved_item_count": dry_run.get("unresolved_item_count"),
            "live_external_actions_attempted": dry_run.get("live_external_actions_attempted"),
            "global_aix_score": global_aix_score,
            "global_aix_accept_threshold": global_aix_threshold,
        },
    }


def validate_production_go_no_go_report(report: dict[str, Any]) -> dict[str, Any]:
    """Validate final go/no-go report consistency."""

    issues: list[dict[str, str]] = []
    if not isinstance(report, dict):
        return {"valid": False, "issues": [{"path": "$", "message": "Report must be an object."}]}
    if report.get("production_go_no_go_version") != PRODUCTION_GO_NO_GO_VERSION:
        issues.append({"path": "$.production_go_no_go_version", "message": f"Must be {PRODUCTION_GO_NO_GO_VERSION}."})
    if report.get("report_type") != PRODUCTION_GO_NO_GO_REPORT_TYPE:
        issues.append({"path": "$.report_type", "message": f"Must be {PRODUCTION_GO_NO_GO_REPORT_TYPE}."})
    refs = report.get("artifact_refs") if isinstance(report.get("artifact_refs"), dict) else {}
    for name in ("release_manifest", "release_bundle_verification", "human_signoff", "production_deployment_manifest", "post_release_monitoring_policy", "production_dry_run_report"):
        ref = refs.get(name) if isinstance(refs.get(name), dict) else {}
        if ref.get("exists") is not True:
            issues.append({"path": f"$.artifact_refs.{name}", "message": f"{name} artifact must exist."})
    blockers = report.get("blockers")
    if not isinstance(blockers, list):
        issues.append({"path": "$.blockers", "message": "Blockers must be a list."})
        blockers = []
    if report.get("status") == "go" and blockers:
        issues.append({"path": "$.status", "message": "Go status cannot include blockers."})
    if report.get("status") == "no_go" and not blockers:
        issues.append({"path": "$.blockers", "message": "No-go status must include explicit blockers."})
    if report.get("go") != (report.get("status") == "go"):
        issues.append({"path": "$.go", "message": "go boolean must match status."})
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    if summary.get("live_external_actions_attempted") is not False:
        issues.append({"path": "$.summary.live_external_actions_attempted", "message": "Final gate requires a dry run with no live external actions."})
    return {"valid": not issues, "issues": issues}


def write_production_go_no_go_report(
    path: str | pathlib.Path = DEFAULT_PRODUCTION_GO_NO_GO_REPORT_PATH,
    **kwargs: Any,
) -> dict[str, Any]:
    """Write the final production go/no-go report artifact."""

    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = production_go_no_go_report(**kwargs)
    validation = validate_production_go_no_go_report(report)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report": report, "validation": validation, "path": str(output), "bytes": output.stat().st_size}


__all__ = [
    "DEFAULT_PRODUCTION_GO_NO_GO_REPORT_PATH",
    "PRODUCTION_GO_NO_GO_REPORT_TYPE",
    "PRODUCTION_GO_NO_GO_VERSION",
    "production_go_no_go_report",
    "validate_production_go_no_go_report",
    "write_production_go_no_go_report",
]
