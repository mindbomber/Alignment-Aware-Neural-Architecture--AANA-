"""DataPerf and Dynabench audit wrappers for AANA evidence readiness."""

from __future__ import annotations

import datetime
import json
import pathlib
from typing import Any

from eval_pipeline import croissant_evidence


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATAPERF_DYNABENCH_AUDIT_VERSION = "0.1"
DATAPERF_DYNABENCH_PROFILE_TYPE = "aana_dataperf_dynabench_audit_profile"
DEFAULT_DATAPERF_DYNABENCH_PROFILE_PATH = ROOT / "examples" / "dataperf_dynabench_audit_profile.json"
DEFAULT_DATAPERF_DYNABENCH_BENCHMARK_PATH = ROOT / "examples" / "dataperf_dynabench_benchmark_summary.json"
DEFAULT_DATAPERF_DYNABENCH_REPORT_PATH = ROOT / "eval_outputs" / "dataperf_dynabench" / "audit-report.json"
CLAIM_BOUNDARY = (
    "DataPerf/Dynabench audit output is dataset and benchmark-readiness evidence only; "
    "it is not regulated deployment approval, production certification, or dataset legal certification."
)


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: str | pathlib.Path) -> dict[str, Any]:
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _write_json(path: str | pathlib.Path, payload: dict[str, Any]) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _issue(level: str, code: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "code": code, "path": path, "message": message}


def _normalize_gap(gap: dict[str, Any]) -> dict[str, str]:
    field = str(gap.get("field") or gap.get("path") or "$")
    return _issue(
        str(gap.get("level", "warning")),
        str(gap.get("code") or f"dataset_{field}"),
        field,
        str(gap.get("message", "Evidence gap.")),
    )


def _section(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) else default


def default_dataperf_dynabench_profile() -> dict[str, Any]:
    """Return the default lower-priority DataPerf/Dynabench audit profile."""

    return {
        "profile_type": DATAPERF_DYNABENCH_PROFILE_TYPE,
        "profile_version": DATAPERF_DYNABENCH_AUDIT_VERSION,
        "product": "AANA AIx Audit",
        "surfaces": ["dataperf", "dynabench"],
        "priority": "lower_than_medperf_croissant",
        "claim_boundary": CLAIM_BOUNDARY,
        "dataset_quality_checks": {
            "require_provenance": True,
            "require_license": True,
            "require_distribution": True,
            "require_intended_use": True,
            "privacy_policy_required_for_sensitive_fields": True,
        },
        "benchmark_coverage_thresholds": {
            "minimum_task_count": 1,
            "minimum_split_count": 2,
            "minimum_metric_count": 1,
            "minimum_baseline_count": 1,
            "minimum_adversarial_coverage": 0.2,
        },
        "drift_thresholds": {
            "max_distribution_shift": 0.2,
            "max_label_shift": 0.15,
            "max_quality_regression": 0.05,
            "max_staleness_days_standard": 365,
            "max_staleness_days_elevated": 180,
            "max_staleness_days_high": 90,
        },
        "risk_tier_rules": [
            {
                "tier": "high",
                "conditions": [
                    "sensitive_fields_without_privacy_policy",
                    "large_drift",
                    "missing_license",
                    "missing_provenance",
                    "regulated_or_rights_impacting_domain",
                ],
            },
            {
                "tier": "elevated",
                "conditions": [
                    "moderate_drift",
                    "low_adversarial_coverage",
                    "missing_baseline",
                    "dynamic_collection_without_review",
                ],
            },
            {"tier": "standard", "conditions": ["complete_metadata", "adequate_coverage", "low_drift"]},
        ],
    }


def validate_dataperf_dynabench_profile(profile: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(profile, dict):
        return {"valid": False, "errors": 1, "warnings": 0, "issues": [_issue("error", "invalid_profile", "$", "Profile must be a JSON object.")]}
    if profile.get("profile_type") != DATAPERF_DYNABENCH_PROFILE_TYPE:
        issues.append(_issue("error", "profile_type", "profile_type", f"Must be {DATAPERF_DYNABENCH_PROFILE_TYPE}."))
    if profile.get("profile_version") != DATAPERF_DYNABENCH_AUDIT_VERSION:
        issues.append(_issue("error", "profile_version", "profile_version", f"Must be {DATAPERF_DYNABENCH_AUDIT_VERSION}."))
    surfaces = set(profile.get("surfaces") or [])
    if not {"dataperf", "dynabench"}.issubset(surfaces):
        issues.append(_issue("error", "surfaces", "surfaces", "Profile must cover dataperf and dynabench."))
    if "not regulated deployment approval" not in str(profile.get("claim_boundary", "")).lower():
        issues.append(_issue("error", "claim_boundary", "claim_boundary", "Claim boundary must state this is not regulated deployment approval."))
    for key in ("dataset_quality_checks", "benchmark_coverage_thresholds", "drift_thresholds", "risk_tier_rules"):
        if not profile.get(key):
            issues.append(_issue("error", f"missing_{key}", key, f"Missing required profile section: {key}."))
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "issues": issues}


def dataset_quality_audit(metadata: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or default_dataperf_dynabench_profile()
    summary = croissant_evidence.croissant_metadata_summary(metadata)
    gaps = [_normalize_gap(gap) for gap in summary["gap_report"]["gaps"]]
    sensitive_without_privacy = bool(summary["sensitive_fields"]) and any(gap["path"] == "privacyPolicy" for gap in gaps)
    quality_score = 1.0
    quality_score -= 0.18 * summary["gap_report"]["errors"]
    quality_score -= 0.08 * summary["gap_report"]["warnings"]
    if summary["record_set_count"] == 0:
        quality_score -= 0.1
        gaps.append(_issue("warning", "missing_record_sets", "recordSet", "Record sets are recommended for benchmark reproducibility."))
    if summary["field_count"] == 0:
        quality_score -= 0.1
        gaps.append(_issue("warning", "missing_fields", "recordSet.field", "Field metadata is recommended for quality and drift analysis."))
    quality_score = max(0.0, round(quality_score, 4))
    return {
        "dataset_name": summary["name"],
        "source_id": summary["source_id"],
        "quality_score": quality_score,
        "summary": summary,
        "evidence_gaps": gaps,
        "sensitive_without_privacy_policy": sensitive_without_privacy,
        "valid": quality_score >= 0.75 and summary["gap_report"]["errors"] == 0,
    }


def benchmark_coverage_summary(benchmark: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or default_dataperf_dynabench_profile()
    thresholds = _section(profile.get("benchmark_coverage_thresholds"))
    tasks = benchmark.get("tasks") if isinstance(benchmark.get("tasks"), list) else []
    splits = benchmark.get("splits") if isinstance(benchmark.get("splits"), list) else []
    metrics = benchmark.get("metrics") if isinstance(benchmark.get("metrics"), list) else []
    baselines = benchmark.get("baselines") if isinstance(benchmark.get("baselines"), list) else []
    adversarial = _number(benchmark.get("adversarial_coverage"), 0.0)
    gaps: list[dict[str, str]] = []
    if len(tasks) < int(thresholds.get("minimum_task_count", 1)):
        gaps.append(_issue("error", "missing_tasks", "tasks", "Benchmark should declare at least one task."))
    if len(splits) < int(thresholds.get("minimum_split_count", 2)):
        gaps.append(_issue("warning", "low_split_coverage", "splits", "Benchmark should include train/validation/test or equivalent splits."))
    if len(metrics) < int(thresholds.get("minimum_metric_count", 1)):
        gaps.append(_issue("error", "missing_metrics", "metrics", "Benchmark should declare at least one evaluation metric."))
    if len(baselines) < int(thresholds.get("minimum_baseline_count", 1)):
        gaps.append(_issue("warning", "missing_baseline", "baselines", "Benchmark should include at least one baseline or reference system."))
    if adversarial < float(thresholds.get("minimum_adversarial_coverage", 0.2)):
        gaps.append(_issue("warning", "low_adversarial_coverage", "adversarial_coverage", "Adversarial or dynamic coverage is below the profile threshold."))
    coverage_score = 1.0
    coverage_score -= 0.2 * sum(1 for gap in gaps if gap["level"] == "error")
    coverage_score -= 0.1 * sum(1 for gap in gaps if gap["level"] == "warning")
    coverage_score = max(0.0, round(coverage_score, 4))
    return {
        "benchmark_id": benchmark.get("benchmark_id", "dataperf_dynabench_benchmark"),
        "surface": benchmark.get("surface", "dataperf_dynabench"),
        "task_count": len(tasks),
        "split_count": len(splits),
        "metric_count": len(metrics),
        "baseline_count": len(baselines),
        "adversarial_coverage": adversarial,
        "coverage_score": coverage_score,
        "coverage_gaps": gaps,
        "valid": not any(gap["level"] == "error" for gap in gaps),
    }


def drift_risk_summary(benchmark: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or default_dataperf_dynabench_profile()
    thresholds = _section(profile.get("drift_thresholds"))
    drift = _section(benchmark.get("drift"))
    distribution_shift = _number(drift.get("distribution_shift"), 0.0)
    label_shift = _number(drift.get("label_shift"), 0.0)
    quality_regression = _number(drift.get("quality_regression"), 0.0)
    staleness_days = _number(drift.get("staleness_days"), 0.0)
    risks: list[dict[str, str]] = []
    if distribution_shift > float(thresholds.get("max_distribution_shift", 0.2)):
        risks.append(_issue("error", "large_distribution_shift", "drift.distribution_shift", "Distribution shift exceeds profile threshold."))
    if label_shift > float(thresholds.get("max_label_shift", 0.15)):
        risks.append(_issue("error", "large_label_shift", "drift.label_shift", "Label shift exceeds profile threshold."))
    if quality_regression > float(thresholds.get("max_quality_regression", 0.05)):
        risks.append(_issue("warning", "quality_regression", "drift.quality_regression", "Quality regression exceeds profile threshold."))
    if staleness_days > float(thresholds.get("max_staleness_days_elevated", 180)):
        risks.append(_issue("warning", "stale_dataset", "drift.staleness_days", "Dataset or benchmark evidence may be stale."))
    risk_score = min(1.0, round(max(distribution_shift, label_shift, quality_regression * 2, staleness_days / 365), 4))
    if any(risk["level"] == "error" for risk in risks):
        risk_level = "high"
    elif risks or risk_score >= 0.2:
        risk_level = "elevated"
    else:
        risk_level = "standard"
    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "distribution_shift": distribution_shift,
        "label_shift": label_shift,
        "quality_regression": quality_regression,
        "staleness_days": staleness_days,
        "drift_risks": risks,
    }


def risk_tier_recommendation(dataset_audit: dict[str, Any], coverage: dict[str, Any], drift: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
    regulated = bool(benchmark.get("regulated_domain") or benchmark.get("rights_impacting"))
    sensitive = bool(dataset_audit.get("summary", {}).get("sensitive_fields"))
    reasons: list[str] = []
    tier = "standard"
    if regulated:
        tier = "high"
        reasons.append("regulated_or_rights_impacting_domain")
    if dataset_audit.get("sensitive_without_privacy_policy"):
        tier = "high"
        reasons.append("sensitive_fields_without_privacy_policy")
    if drift["risk_level"] == "high":
        tier = "high"
        reasons.append("large_drift")
    if not dataset_audit["valid"]:
        tier = "high"
        reasons.append("dataset_quality_gaps")
    if tier != "high" and (not coverage["valid"] or drift["risk_level"] == "elevated" or coverage["coverage_score"] < 0.85):
        tier = "elevated"
        reasons.append("coverage_or_drift_review_needed")
    if not reasons:
        reasons.append("complete_metadata_adequate_coverage_low_drift")
    return {
        "risk_tier": tier,
        "reasons": sorted(set(reasons)),
        "recommendation": {
            "standard": "standard_dataset_benchmark_audit",
            "elevated": "elevated_review_before_runtime_use",
            "high": "high_risk_domain_owner_review_required",
        }[tier],
    }


def run_dataperf_dynabench_audit(
    *,
    metadata_path: str | pathlib.Path = croissant_evidence.DEFAULT_CROISSANT_METADATA_PATH,
    benchmark_path: str | pathlib.Path = DEFAULT_DATAPERF_DYNABENCH_BENCHMARK_PATH,
    profile_path: str | pathlib.Path = DEFAULT_DATAPERF_DYNABENCH_PROFILE_PATH,
    report_path: str | pathlib.Path = DEFAULT_DATAPERF_DYNABENCH_REPORT_PATH,
) -> dict[str, Any]:
    profile = _load_json(profile_path) if pathlib.Path(profile_path).exists() else default_dataperf_dynabench_profile()
    profile_validation = validate_dataperf_dynabench_profile(profile)
    metadata = _load_json(metadata_path)
    benchmark = _load_json(benchmark_path)
    dataset_audit = dataset_quality_audit(metadata, profile)
    coverage = benchmark_coverage_summary(benchmark, profile)
    drift = drift_risk_summary(benchmark, profile)
    tier = risk_tier_recommendation(dataset_audit, coverage, drift, benchmark)
    evidence_gaps = dataset_audit["evidence_gaps"] + coverage["coverage_gaps"] + drift["drift_risks"]
    errors = sum(1 for gap in evidence_gaps if gap["level"] == "error") + profile_validation["errors"]
    warnings = sum(1 for gap in evidence_gaps if gap["level"] == "warning") + profile_validation["warnings"]
    report = {
        "report_type": "aana_dataperf_dynabench_audit_report",
        "report_version": DATAPERF_DYNABENCH_AUDIT_VERSION,
        "created_at": _utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "valid": errors == 0,
        "profile_validation": profile_validation,
        "dataset_quality": dataset_audit,
        "benchmark_coverage": coverage,
        "evidence_gaps": evidence_gaps,
        "drift_risk": drift,
        "risk_tier_recommendation": tier,
        "summary": {
            "dataset": dataset_audit["dataset_name"],
            "benchmark_id": coverage["benchmark_id"],
            "risk_tier": tier["risk_tier"],
            "errors": errors,
            "warnings": warnings,
        },
    }
    _write_json(report_path, report)
    return report


def write_dataperf_dynabench_profile(path: str | pathlib.Path = DEFAULT_DATAPERF_DYNABENCH_PROFILE_PATH) -> dict[str, Any]:
    profile = default_dataperf_dynabench_profile()
    validation = validate_dataperf_dynabench_profile(profile)
    _write_json(path, profile)
    return {"path": str(path), "profile": profile, "validation": validation}


__all__ = [
    "CLAIM_BOUNDARY",
    "DATAPERF_DYNABENCH_AUDIT_VERSION",
    "DATAPERF_DYNABENCH_PROFILE_TYPE",
    "DEFAULT_DATAPERF_DYNABENCH_BENCHMARK_PATH",
    "DEFAULT_DATAPERF_DYNABENCH_PROFILE_PATH",
    "DEFAULT_DATAPERF_DYNABENCH_REPORT_PATH",
    "benchmark_coverage_summary",
    "dataset_quality_audit",
    "default_dataperf_dynabench_profile",
    "drift_risk_summary",
    "risk_tier_recommendation",
    "run_dataperf_dynabench_audit",
    "validate_dataperf_dynabench_profile",
    "write_dataperf_dynabench_profile",
]
