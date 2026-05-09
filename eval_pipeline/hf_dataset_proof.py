"""Governance for HF dataset proof reports.

The proof report is intentionally narrower than a benchmark leaderboard claim:
it ties public statements to measured adapter-family artifacts and requires
explicit limitations.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any


HF_DATASET_PROOF_VERSION = "0.1"
REQUIRED_PROOF_AXES = {
    "false_positive_control",
    "unsafe_recall",
    "groundedness",
    "private_public_read_routing",
}
REQUIRED_POLICY_FLAGS = {
    "no_hype_claims",
    "no_raw_agent_performance_claim",
    "requires_split_isolation",
    "requires_limitations",
    "requires_measured_artifacts",
}


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _load_json(root: pathlib.Path, path: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    artifact = root / path
    if not artifact.exists():
        return {}, [_issue("error", path, f"Artifact does not exist: {path}")]
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [_issue("error", path, f"Artifact could not be loaded as JSON: {type(exc).__name__}")]
    if not isinstance(payload, dict):
        return {}, [_issue("error", path, "Artifact must be a JSON object.")]
    return payload, []


def _metric_value(root: pathlib.Path, artifact: str, metric: str) -> tuple[float | None, list[dict[str, str]]]:
    payload, issues = _load_json(root, artifact)
    if issues:
        return None, issues
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return None, [_issue("error", artifact, "Artifact must contain a metrics object.")]
    value = metrics.get(metric)
    if not isinstance(value, int | float):
        return None, [_issue("error", f"{artifact}.metrics.{metric}", "Required metric is missing or non-numeric.")]
    return float(value), []


def validate_hf_dataset_proof_report(
    manifest: dict[str, Any],
    *,
    root: str | pathlib.Path = ".",
    require_existing_artifacts: bool = False,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    root_path = pathlib.Path(root)

    if manifest.get("schema_version") != HF_DATASET_PROOF_VERSION:
        issues.append(_issue("error", "schema_version", f"schema_version must be {HF_DATASET_PROOF_VERSION}."))

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        issues.append(_issue("error", "policy", "Manifest must include a policy object."))
        policy = {}
    for flag in sorted(REQUIRED_POLICY_FLAGS):
        if policy.get(flag) is not True:
            issues.append(_issue("error", f"policy.{flag}", "Policy flag must be true."))
    public_language_rule = str(policy.get("public_language_rule", "")).lower()
    uses_comparative_language = "lower" in public_language_rule or "higher" in public_language_rule
    requires_paired_baseline = "paired baseline" in public_language_rule or "paired baseline artifacts" in public_language_rule
    if uses_comparative_language and not requires_paired_baseline:
        issues.append(_issue("error", "policy.public_language_rule", "Public language rule must not promise comparative deltas without paired baselines."))

    proof_axes = manifest.get("proof_axes")
    if not isinstance(proof_axes, list) or not proof_axes:
        issues.append(_issue("error", "proof_axes", "Manifest must include proof axes."))
        proof_axes = []
    seen_axes = set()
    artifact_metric_checks = 0
    for axis_index, axis in enumerate(proof_axes):
        base = f"proof_axes[{axis_index}]"
        if not isinstance(axis, dict):
            issues.append(_issue("error", base, "Proof axis must be an object."))
            continue
        axis_id = axis.get("id")
        if not _has_text(axis_id):
            issues.append(_issue("error", f"{base}.id", "Proof axis id is required."))
        else:
            seen_axes.add(str(axis_id))
        if not _has_text(axis.get("claim")):
            issues.append(_issue("error", f"{base}.claim", "Proof axis claim is required."))
        if not _nonempty_list(axis.get("metrics")):
            issues.append(_issue("error", f"{base}.metrics", "Proof axis must list metrics."))
            continue
        for metric_index, metric_ref in enumerate(axis["metrics"]):
            metric_base = f"{base}.metrics[{metric_index}]"
            if not isinstance(metric_ref, dict):
                issues.append(_issue("error", metric_base, "Metric reference must be an object."))
                continue
            artifact = metric_ref.get("artifact")
            metric = metric_ref.get("metric")
            threshold = metric_ref.get("threshold")
            direction = metric_ref.get("direction")
            if not _has_text(artifact) or not _has_text(metric):
                issues.append(_issue("error", metric_base, "Metric reference needs artifact and metric."))
                continue
            if direction not in {"at_least", "at_most"}:
                issues.append(_issue("error", f"{metric_base}.direction", "Metric direction must be at_least or at_most."))
                continue
            if not isinstance(threshold, int | float):
                issues.append(_issue("error", f"{metric_base}.threshold", "Metric threshold must be numeric."))
                continue
            if require_existing_artifacts:
                value, metric_issues = _metric_value(root_path, str(artifact), str(metric))
                issues.extend(metric_issues)
                if value is None:
                    continue
                artifact_metric_checks += 1
                if direction == "at_least" and value < float(threshold):
                    issues.append(_issue("error", metric_base, f"Metric {metric}={value} is below threshold {threshold}."))
                if direction == "at_most" and value > float(threshold):
                    issues.append(_issue("error", metric_base, f"Metric {metric}={value} is above threshold {threshold}."))

    missing_axes = sorted(REQUIRED_PROOF_AXES - seen_axes)
    if missing_axes:
        issues.append(_issue("error", "proof_axes", f"Missing required proof axes: {missing_axes}."))

    limitations = manifest.get("limitations")
    if not _nonempty_list(limitations):
        issues.append(_issue("error", "limitations", "Manifest must include limitations."))

    report_path = manifest.get("report_path")
    if not _has_text(report_path):
        issues.append(_issue("error", "report_path", "Manifest must reference a public report path."))
    elif require_existing_artifacts and not (root_path / str(report_path)).exists():
        issues.append(_issue("error", "report_path", f"Report path does not exist: {report_path}"))

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "proof_axis_count": len(proof_axes),
        "artifact_metric_checks": artifact_metric_checks,
    }


def load_manifest(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("HF dataset proof report must be a JSON object.")
    return payload


__all__ = ["HF_DATASET_PROOF_VERSION", "load_manifest", "validate_hf_dataset_proof_report"]
