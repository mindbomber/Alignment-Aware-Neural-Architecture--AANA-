"""Live monitoring metrics for AANA runtime audit streams."""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline import audit


ROOT = pathlib.Path(__file__).resolve().parents[1]
LIVE_MONITORING_VERSION = "0.1"
LIVE_MONITORING_CONFIG_TYPE = "aana_live_monitoring_config"
LIVE_MONITORING_REPORT_TYPE = "aana_live_monitoring_report"
DEFAULT_LIVE_MONITORING_CONFIG_PATH = ROOT / "examples" / "live_monitoring_metrics.json"
DEFAULT_LIVE_MONITORING_REPORT_PATH = ROOT / "eval_outputs" / "monitoring" / "live-monitoring-report.json"
ALLOWED_RAW_METADATA_KEYS = {
    "raw_payload_logged",
    "raw_payload_storage",
    "raw_artifact_storage",
    "raw_private_content_allowed_in_audit",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _write_json(path: str | pathlib.Path, payload: dict[str, Any]) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _raw_field_findings(value: Any, *, path: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            is_fingerprint_metadata = ".input_fingerprints." in child_path
            raw_key = (
                key_text in audit.PROHIBITED_AUDIT_FIELDS
                or key_text.startswith("raw_")
                or key_text.startswith("raw-")
                or bool(audit.PROHIBITED_AUDIT_KEY_PATTERN.search(key_text))
            )
            if raw_key and not is_fingerprint_metadata and key_text not in ALLOWED_RAW_METADATA_KEYS:
                findings.append(_issue("error", child_path, "Live monitoring input must not contain raw sensitive fields."))
            findings.extend(_raw_field_findings(child, path=child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_raw_field_findings(item, path=f"{path}[{index}]"))
    return findings


def live_monitoring_config() -> dict[str, Any]:
    """Return the default production-candidate live monitoring metric policy."""

    return {
        "live_monitoring_version": LIVE_MONITORING_VERSION,
        "config_type": LIVE_MONITORING_CONFIG_TYPE,
        "product_bundle": "enterprise_ops_pilot",
        "source_of_truth": "redacted_aana_runtime_audit_jsonl",
        "claim_boundary": "Live monitoring readiness only; not production certification or go-live approval.",
        "required_metrics": [
            "audit_records_total",
            "gate_decision_count",
            "recommended_action_count",
            "aix_score_average",
            "aix_score_min",
            "aix_hard_blocker_count",
            "human_review_rate",
            "refusal_defer_rate",
            "connector_failure_count",
            "evidence_freshness_failure_count",
            "latency_p95_ms",
            "shadow_would_block_rate",
            "shadow_would_intervene_rate",
        ],
        "thresholds": {
            "min_records": 1,
            "min_aix_average": 0.85,
            "min_aix_min": 0.5,
            "max_aix_hard_blocker_rate": 0.0,
            "max_connector_failure_rate": 0.0,
            "max_evidence_freshness_failure_rate": 0.0,
            "max_human_review_rate": 0.5,
            "max_refusal_defer_rate": 0.5,
            "max_shadow_would_block_rate": 0.25,
            "max_shadow_would_intervene_rate": 0.75,
            "max_latency_p95_ms": 2000.0,
        },
        "redaction": {
            "raw_prompt_logged": False,
            "raw_candidate_logged": False,
            "raw_evidence_text_logged": False,
            "raw_safe_response_logged": False,
            "private_records_logged": False,
        },
        "alert_routes": {
            "warning": "support_ops_monitoring",
            "critical": "support_incident_response",
        },
    }


def validate_live_monitoring_config(config: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(config, dict):
        return {"valid": False, "errors": 1, "warnings": 0, "issues": [_issue("error", "$", "Config must be a JSON object.")]}
    if config.get("live_monitoring_version") != LIVE_MONITORING_VERSION:
        issues.append(_issue("error", "live_monitoring_version", f"Must be {LIVE_MONITORING_VERSION}."))
    if config.get("config_type") != LIVE_MONITORING_CONFIG_TYPE:
        issues.append(_issue("error", "config_type", f"Must be {LIVE_MONITORING_CONFIG_TYPE}."))
    if config.get("source_of_truth") != "redacted_aana_runtime_audit_jsonl":
        issues.append(_issue("error", "source_of_truth", "Live monitoring must use redacted AANA runtime audit JSONL."))
    if "not production certification" not in str(config.get("claim_boundary", "")).lower():
        issues.append(_issue("error", "claim_boundary", "Claim boundary must state this is not production certification."))
    thresholds = config.get("thresholds") if isinstance(config.get("thresholds"), dict) else {}
    for key in (
        "min_records",
        "min_aix_average",
        "min_aix_min",
        "max_aix_hard_blocker_rate",
        "max_connector_failure_rate",
        "max_evidence_freshness_failure_rate",
        "max_human_review_rate",
        "max_refusal_defer_rate",
        "max_shadow_would_block_rate",
        "max_shadow_would_intervene_rate",
        "max_latency_p95_ms",
    ):
        if not isinstance(thresholds.get(key), (int, float)):
            issues.append(_issue("error", f"thresholds.{key}", "Numeric threshold is required."))
    redaction = config.get("redaction") if isinstance(config.get("redaction"), dict) else {}
    for key in ("raw_prompt_logged", "raw_candidate_logged", "raw_evidence_text_logged", "raw_safe_response_logged", "private_records_logged"):
        if redaction.get(key) is not False:
            issues.append(_issue("error", f"redaction.{key}", "Raw/private content logging must be disabled."))
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "issues": issues}


def write_live_monitoring_config(path: str | pathlib.Path = DEFAULT_LIVE_MONITORING_CONFIG_PATH) -> dict[str, Any]:
    config = live_monitoring_config()
    _write_json(path, config)
    return {"config_path": str(path), "config": config, "validation": validate_live_monitoring_config(config)}


def load_live_monitoring_config(path: str | pathlib.Path = DEFAULT_LIVE_MONITORING_CONFIG_PATH) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _rate(count: Any, total: int) -> float:
    if not isinstance(count, (int, float)) or total <= 0:
        return 0.0
    return round(float(count) / total, 4)


def _metric_status(name: str, value: Any, threshold: Any, *, mode: str) -> dict[str, Any]:
    if not isinstance(value, (int, float)):
        return {"metric": name, "status": "warning", "value": value, "threshold": threshold, "message": "Metric is unavailable."}
    if mode == "min":
        ok = value >= threshold
        message = f"{name} {value} is below {threshold}." if not ok else f"{name} meets threshold."
    else:
        ok = value <= threshold
        message = f"{name} {value} exceeds {threshold}." if not ok else f"{name} meets threshold."
    return {"metric": name, "status": "healthy" if ok else "critical", "value": value, "threshold": threshold, "message": message}


def live_monitoring_report(
    audit_log_path: str | pathlib.Path,
    *,
    config: dict[str, Any] | None = None,
    output_path: str | pathlib.Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate live/shadow runtime health from redacted AANA audit JSONL."""

    config = config or live_monitoring_config()
    config_validation = validate_live_monitoring_config(config)
    if not config_validation["valid"]:
        raise ValueError(f"Live monitoring config is invalid: {config_validation['issues']}")
    records = audit.load_jsonl(audit_log_path)
    source_validation = audit.validate_audit_records(records)
    if not source_validation["valid"]:
        raise ValueError(f"Source audit log is not valid redacted AANA audit JSONL: {source_validation['issues']}")
    source_raw_findings = []
    for index, record in enumerate(records):
        source_raw_findings.extend(_raw_field_findings(record, path=f"$[{index}]"))
    if source_raw_findings:
        raise ValueError(f"Source audit log contains raw sensitive fields: {source_raw_findings}")
    metrics_export = audit.export_metrics(records, audit_log_path=audit_log_path, created_at=created_at)
    dashboard = audit.dashboard_payload(records, audit_log_path=audit_log_path, created_at=created_at)
    metrics = metrics_export["metrics"]
    cards = dashboard["cards"]
    total = int(metrics.get("audit_records_total", 0))
    hard_blocker_rate = _rate(metrics.get("aix_hard_blocker_count", 0), total)
    connector_failure_rate = _rate(metrics.get("connector_failure_count", 0), total)
    evidence_freshness_failure_rate = _rate(metrics.get("evidence_freshness_failure_count", 0), total)
    thresholds = config["thresholds"]
    checks = [
        _metric_status("audit_records_total", total, thresholds["min_records"], mode="min"),
        _metric_status("aix_score_average", metrics.get("aix_score_average"), thresholds["min_aix_average"], mode="min"),
        _metric_status("aix_score_min", metrics.get("aix_score_min"), thresholds["min_aix_min"], mode="min"),
        _metric_status("aix_hard_blocker_rate", hard_blocker_rate, thresholds["max_aix_hard_blocker_rate"], mode="max"),
        _metric_status("connector_failure_rate", connector_failure_rate, thresholds["max_connector_failure_rate"], mode="max"),
        _metric_status("evidence_freshness_failure_rate", evidence_freshness_failure_rate, thresholds["max_evidence_freshness_failure_rate"], mode="max"),
        _metric_status("human_review_rate", metrics.get("human_review_rate"), thresholds["max_human_review_rate"], mode="max"),
        _metric_status("refusal_defer_rate", metrics.get("refusal_defer_rate"), thresholds["max_refusal_defer_rate"], mode="max"),
        _metric_status("shadow_would_block_rate", dashboard["shadow_mode"].get("would_block_rate", 0.0), thresholds["max_shadow_would_block_rate"], mode="max"),
        _metric_status("shadow_would_intervene_rate", dashboard["shadow_mode"].get("would_intervene_rate", 0.0), thresholds["max_shadow_would_intervene_rate"], mode="max"),
    ]
    if "latency" not in metrics_export.get("unavailable_metrics", []):
        checks.append(_metric_status("latency_p95_ms", metrics.get("latency_p95_ms"), thresholds["max_latency_p95_ms"], mode="max"))
    else:
        checks.append({"metric": "latency_p95_ms", "status": "warning", "value": None, "threshold": thresholds["max_latency_p95_ms"], "message": "Latency is unavailable."})

    critical = [check for check in checks if check["status"] == "critical"]
    warnings = [check for check in checks if check["status"] == "warning"]
    status = "critical" if critical else "warning" if warnings else "healthy"
    report = {
        "live_monitoring_version": LIVE_MONITORING_VERSION,
        "report_type": LIVE_MONITORING_REPORT_TYPE,
        "created_at": created_at or _utc_now(),
        "status": status,
        "healthy": status == "healthy",
        "audit_log_path": str(audit_log_path),
        "record_count": total,
        "redacted_records_only": True,
        "raw_payload_logged": False,
        "thresholds": thresholds,
        "checks": checks,
        "summary": {
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "aix_average": metrics.get("aix_score_average"),
            "aix_min": metrics.get("aix_score_min"),
            "aix_hard_blocker_rate": hard_blocker_rate,
            "connector_failure_rate": connector_failure_rate,
            "evidence_freshness_failure_rate": evidence_freshness_failure_rate,
            "human_review_rate": metrics.get("human_review_rate"),
            "refusal_defer_rate": metrics.get("refusal_defer_rate"),
            "latency_p95_ms": metrics.get("latency_p95_ms"),
            "shadow_would_block_rate": dashboard["shadow_mode"].get("would_block_rate", 0.0),
            "shadow_would_intervene_rate": dashboard["shadow_mode"].get("would_intervene_rate", 0.0),
        },
        "cards": cards,
        "metrics": metrics,
        "dashboard": dashboard,
        "source_validation": source_validation,
        "config_validation": config_validation,
        "claim_boundary": config["claim_boundary"],
    }
    if output_path:
        _write_json(output_path, report)
    return report


def live_monitoring_report_jsonl(
    audit_log_path: str | pathlib.Path,
    *,
    config_path: str | pathlib.Path | None = DEFAULT_LIVE_MONITORING_CONFIG_PATH,
    output_path: str | pathlib.Path | None = DEFAULT_LIVE_MONITORING_REPORT_PATH,
    created_at: str | None = None,
) -> dict[str, Any]:
    config = load_live_monitoring_config(config_path) if config_path and pathlib.Path(config_path).exists() else live_monitoring_config()
    return live_monitoring_report(audit_log_path, config=config, output_path=output_path, created_at=created_at)


__all__ = [
    "DEFAULT_LIVE_MONITORING_CONFIG_PATH",
    "DEFAULT_LIVE_MONITORING_REPORT_PATH",
    "LIVE_MONITORING_CONFIG_TYPE",
    "LIVE_MONITORING_REPORT_TYPE",
    "LIVE_MONITORING_VERSION",
    "live_monitoring_config",
    "live_monitoring_report",
    "live_monitoring_report_jsonl",
    "load_live_monitoring_config",
    "validate_live_monitoring_config",
    "write_live_monitoring_config",
]
