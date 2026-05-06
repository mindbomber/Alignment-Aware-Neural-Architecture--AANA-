"""Post-release monitoring and alert policy for AANA MI deployments."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline.mi_release_bundle import DEFAULT_MI_RELEASE_BUNDLE_DIR
from eval_pipeline.production_deployment_manifest import DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH


POST_RELEASE_MONITORING_POLICY_VERSION = "0.1"
POST_RELEASE_MONITORING_POLICY_TYPE = "aana_mi_post_release_monitoring_policy"
DEFAULT_POST_RELEASE_MONITORING_POLICY_PATH = DEFAULT_MI_RELEASE_BUNDLE_DIR / "post_release_monitoring_policy.json"
REQUIRED_ALERT_IDS = (
    "aix_drift",
    "false_accept_rate",
    "false_refusal_rate",
    "audit_append_failures",
    "stale_evidence",
    "unresolved_propagation",
)


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


def _metric(metric_id: str, description: str, source: str, window: str, owner: str) -> dict[str, str]:
    return {
        "metric_id": metric_id,
        "description": description,
        "source": source,
        "window": window,
        "owner": owner,
    }


def _alert(
    alert_id: str,
    metric_id: str,
    severity: str,
    threshold: dict[str, Any],
    route: str,
    response: list[str],
) -> dict[str, Any]:
    return {
        "alert_id": alert_id,
        "metric_id": metric_id,
        "severity": severity,
        "threshold": threshold,
        "route": route,
        "response": response,
    }


def post_release_monitoring_policy(
    *,
    deployment_manifest_path: str | pathlib.Path = DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create the post-release MI monitoring and alert policy."""

    deployment_path = pathlib.Path(deployment_manifest_path)
    deployment_manifest = _load_json(deployment_path)
    bundle = deployment_manifest.get("verified_mi_release_bundle") if isinstance(deployment_manifest.get("verified_mi_release_bundle"), dict) else {}
    global_aix = bundle.get("global_aix") if isinstance(bundle.get("global_aix"), dict) else {}
    baseline_score = global_aix.get("score")
    accept_threshold = global_aix.get("accept_threshold", 0.9)

    metrics = [
        _metric("global_aix_score", "Workflow-level AIx score after production handoff aggregation.", "mi_dashboard.global_aix", "5m,1h,24h", "release_manager"),
        _metric("aix_drift_delta", "Drop from release-bundle baseline AIx.", "mi_dashboard.global_aix and release_manifest.global_aix", "5m,1h,24h", "release_manager"),
        _metric("false_accept_rate", "Accepted handoffs later marked unsafe, unsupported, or policy-violating.", "review_queue and incident labels", "1h,24h,7d", "domain_owner"),
        _metric("false_refusal_rate", "Refused or deferred handoffs later approved as valid by review.", "human_review_queue and correction outcomes", "1h,24h,7d", "domain_owner"),
        _metric("audit_append_failure_count", "Failed writes or manifest mismatches in append-only MI audit storage.", "immutable_audit_storage and audit_integrity_manifest", "5m,1h,24h", "security_owner"),
        _metric("stale_evidence_rate", "Consequential handoffs with evidence older than freshness policy.", "evidence_object.freshness and handoff evidence validator", "1h,24h", "evidence_owner"),
        _metric("unresolved_propagated_risk_count", "Unsupported assumptions or accepted violations still used downstream.", "propagated_risk tracker", "5m,1h,24h", "release_manager"),
        _metric("correction_success_rate", "Retrieve/revise/ask/defer corrections that produce passing MI rechecks.", "correction_execution_loop", "1h,24h,7d", "release_manager"),
        _metric("handoff_pass_rate", "Accepted handoffs divided by total consequential handoffs.", "mi_boundary_gate audit records", "5m,1h,24h", "release_manager"),
    ]
    alerts = [
        _alert(
            "aix_drift",
            "aix_drift_delta",
            "critical",
            {"operator": ">=", "value": 0.05, "baseline_global_aix": baseline_score, "minimum_score": accept_threshold},
            "defer_new_high_risk_actions",
            ["freeze_live_connector_enablement", "run_global_aix_recheck", "open_release_owner_review"],
        ),
        _alert(
            "false_accept_rate",
            "false_accept_rate",
            "critical",
            {"operator": ">=", "value": 0.01, "minimum_events": 1},
            "block_accept_route_for_affected_workflow",
            ["replay_recent_handoffs", "raise_verifier_strictness", "route_affected_workflow_to_human_review"],
        ),
        _alert(
            "false_refusal_rate",
            "false_refusal_rate",
            "warning",
            {"operator": ">=", "value": 0.05, "minimum_events": 3},
            "review_thresholds",
            ["sample_refusals", "calibrate_refusal_thresholds", "check_evidence_freshness_rules"],
        ),
        _alert(
            "audit_append_failures",
            "audit_append_failure_count",
            "critical",
            {"operator": ">", "value": 0},
            "block_live_execution",
            ["stop_writes", "verify_audit_manifest", "escalate_to_security_owner"],
        ),
        _alert(
            "stale_evidence",
            "stale_evidence_rate",
            "high",
            {"operator": ">=", "value": 0.02, "minimum_events": 2},
            "retrieve",
            ["force_evidence_refresh", "mark_affected_handoffs_for_recheck", "audit_source_freshness_policy"],
        ),
        _alert(
            "unresolved_propagation",
            "unresolved_propagated_risk_count",
            "critical",
            {"operator": ">", "value": 0},
            "defer_publication_or_execution",
            ["trace_upstream_assumption", "revise_or_remove_dependent_claims", "rerun_mi_boundary_and_global_aix"],
        ),
    ]
    return {
        "post_release_monitoring_policy_version": POST_RELEASE_MONITORING_POLICY_VERSION,
        "policy_type": POST_RELEASE_MONITORING_POLICY_TYPE,
        "created_at": created_at or _utc_now(),
        "deployment_manifest": _artifact_ref(deployment_path),
        "release_context": {
            "deployment_status": deployment_manifest.get("deployment_status"),
            "deployment_authorized": deployment_manifest.get("deployment_authorized"),
            "rc_status": bundle.get("rc_status"),
            "readiness_status": bundle.get("readiness_status"),
            "bundle_verification_status": bundle.get("verification_status"),
            "global_aix_baseline": baseline_score,
            "global_aix_accept_threshold": accept_threshold,
        },
        "collection_policy": {
            "raw_private_content_allowed": False,
            "raw_prompt_capture_allowed": False,
            "raw_evidence_capture_allowed": False,
            "redacted_metadata_only": True,
            "minimum_collection_interval_seconds": 60,
            "required_sources": [
                "mi_audit_jsonl",
                "mi_dashboard_json",
                "audit_integrity_manifest",
                "handoff_evidence_validator",
                "propagated_risk_tracker",
                "human_review_queue",
                "correction_execution_loop",
            ],
        },
        "metrics": metrics,
        "alerts": alerts,
        "incident_policy": {
            "critical_page": True,
            "critical_response_slo_minutes": 15,
            "warning_response_slo_minutes": 240,
            "default_critical_route": "defer_or_block_high_risk_actions",
            "owners": {
                "release_manager": "pending-release-owner",
                "security_owner": "pending-security-owner",
                "domain_owner": "pending-domain-owner",
                "evidence_owner": "pending-evidence-owner",
            },
        },
    }


def validate_post_release_monitoring_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Validate post-release monitoring policy shape and required alerts."""

    issues: list[dict[str, str]] = []
    if not isinstance(policy, dict):
        return {"valid": False, "issues": [{"path": "$", "message": "Policy must be an object."}]}
    if policy.get("post_release_monitoring_policy_version") != POST_RELEASE_MONITORING_POLICY_VERSION:
        issues.append({"path": "$.post_release_monitoring_policy_version", "message": f"Must be {POST_RELEASE_MONITORING_POLICY_VERSION}."})
    if policy.get("policy_type") != POST_RELEASE_MONITORING_POLICY_TYPE:
        issues.append({"path": "$.policy_type", "message": f"Must be {POST_RELEASE_MONITORING_POLICY_TYPE}."})

    deployment_ref = policy.get("deployment_manifest") if isinstance(policy.get("deployment_manifest"), dict) else {}
    if deployment_ref.get("exists") is not True:
        issues.append({"path": "$.deployment_manifest", "message": "Deployment manifest reference must exist."})

    collection = policy.get("collection_policy") if isinstance(policy.get("collection_policy"), dict) else {}
    for field in ("raw_private_content_allowed", "raw_prompt_capture_allowed", "raw_evidence_capture_allowed"):
        if collection.get(field) is not False:
            issues.append({"path": f"$.collection_policy.{field}", "message": "Monitoring must not capture raw private content, prompts, or evidence."})
    if collection.get("redacted_metadata_only") is not True:
        issues.append({"path": "$.collection_policy.redacted_metadata_only", "message": "Monitoring must collect redacted metadata only."})

    metrics = policy.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        issues.append({"path": "$.metrics", "message": "Runtime metrics are required."})
        metrics = []
    metric_ids = {metric.get("metric_id") for metric in metrics if isinstance(metric, dict)}
    for metric_id in ("global_aix_score", "aix_drift_delta", "false_accept_rate", "false_refusal_rate", "audit_append_failure_count", "stale_evidence_rate", "unresolved_propagated_risk_count"):
        if metric_id not in metric_ids:
            issues.append({"path": "$.metrics", "message": f"Missing required metric: {metric_id}."})

    alerts = policy.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        issues.append({"path": "$.alerts", "message": "Alerts are required."})
        alerts = []
    alert_ids = {alert.get("alert_id") for alert in alerts if isinstance(alert, dict)}
    for alert_id in REQUIRED_ALERT_IDS:
        if alert_id not in alert_ids:
            issues.append({"path": "$.alerts", "message": f"Missing required alert: {alert_id}."})
    for index, alert in enumerate(alerts):
        path = f"$.alerts[{index}]"
        if not isinstance(alert, dict):
            issues.append({"path": path, "message": "Alert must be an object."})
            continue
        if alert.get("metric_id") not in metric_ids:
            issues.append({"path": f"{path}.metric_id", "message": "Alert metric must reference a declared metric."})
        if alert.get("severity") not in {"warning", "high", "critical"}:
            issues.append({"path": f"{path}.severity", "message": "Alert severity must be warning, high, or critical."})
        if not isinstance(alert.get("threshold"), dict):
            issues.append({"path": f"{path}.threshold", "message": "Alert threshold must be an object."})
        if not isinstance(alert.get("response"), list) or not alert.get("response"):
            issues.append({"path": f"{path}.response", "message": "Alert response actions are required."})

    incident = policy.get("incident_policy") if isinstance(policy.get("incident_policy"), dict) else {}
    if incident.get("critical_page") is not True:
        issues.append({"path": "$.incident_policy.critical_page", "message": "Critical alerts must page."})
    if not isinstance(incident.get("owners"), dict):
        issues.append({"path": "$.incident_policy.owners", "message": "Incident owners are required."})

    return {"valid": not issues, "issues": issues}


def write_post_release_monitoring_policy(
    path: str | pathlib.Path = DEFAULT_POST_RELEASE_MONITORING_POLICY_PATH,
    *,
    deployment_manifest_path: str | pathlib.Path = DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Write the monitoring and alert policy artifact."""

    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    policy = post_release_monitoring_policy(deployment_manifest_path=deployment_manifest_path)
    validation = validate_post_release_monitoring_policy(policy)
    output.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"policy": policy, "validation": validation, "path": str(output), "bytes": output.stat().st_size}


__all__ = [
    "DEFAULT_POST_RELEASE_MONITORING_POLICY_PATH",
    "POST_RELEASE_MONITORING_POLICY_TYPE",
    "POST_RELEASE_MONITORING_POLICY_VERSION",
    "REQUIRED_ALERT_IDS",
    "post_release_monitoring_policy",
    "validate_post_release_monitoring_policy",
    "write_post_release_monitoring_policy",
]
