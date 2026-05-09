"""Production-candidate evidence-pack governance for AANA public claims."""

from __future__ import annotations

import json
import pathlib
from typing import Any


PRODUCTION_EVIDENCE_PACK_VERSION = "0.1"
EXACT_PRODUCTION_CANDIDATE_CLAIM = "AANA is production-candidate as an audit/control/verification/correction layer."
EXACT_NOT_PROVEN_ENGINE_CLAIM = "AANA is not yet proven as a raw agent-performance engine."
REQUIRED_LIMITATION_KEYS = {"failures", "false_positives", "latency", "unsupported_domains"}


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _read_report(root: pathlib.Path, report_path: Any) -> tuple[str, list[dict[str, str]]]:
    if not _has_text(report_path):
        return "", [_issue("error", "report_path", "Evidence pack must reference a Markdown report path.")]
    path = root / str(report_path)
    if not path.exists():
        return "", [_issue("error", "report_path", f"Report path does not exist: {report_path}")]
    return path.read_text(encoding="utf-8"), []


def validate_production_candidate_evidence_pack(
    manifest: dict[str, Any],
    *,
    root: str | pathlib.Path = ".",
    require_existing_artifacts: bool = False,
) -> dict[str, Any]:
    """Validate the production-candidate evidence-pack manifest and report."""

    issues: list[dict[str, str]] = []
    root_path = pathlib.Path(root)

    if manifest.get("schema_version") != PRODUCTION_EVIDENCE_PACK_VERSION:
        issues.append(_issue("error", "schema_version", f"schema_version must be {PRODUCTION_EVIDENCE_PACK_VERSION}."))

    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        issues.append(_issue("error", "claim_boundary", "Manifest must include a claim_boundary object."))
        boundary = {}
    if boundary.get("production_candidate_layer") != EXACT_PRODUCTION_CANDIDATE_CLAIM:
        issues.append(
            _issue(
                "error",
                "claim_boundary.production_candidate_layer",
                "Production-candidate claim must use the exact approved language.",
            )
        )
    if boundary.get("not_proven_engine") != EXACT_NOT_PROVEN_ENGINE_CLAIM:
        issues.append(_issue("error", "claim_boundary.not_proven_engine", "Raw-agent-performance boundary must use the exact approved language."))

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        issues.append(_issue("error", "policy", "Manifest must include a policy object."))
        policy = {}
    required_true = (
        "require_failures_section",
        "require_false_positives_section",
        "require_latency_section",
        "require_unsupported_domains_section",
        "never_merge_probe_results_into_public_claims",
        "require_measured_non_probe_results_for_benchmark_claims",
    )
    for key in required_true:
        if policy.get(key) is not True:
            issues.append(_issue("error", f"policy.{key}", "Policy flag must be true."))
    if policy.get("allow_raw_agent_performance_claim") is not False:
        issues.append(_issue("error", "policy.allow_raw_agent_performance_claim", "Raw agent-performance claims must remain blocked."))

    tasks = manifest.get("implementation_tasks")
    if not _nonempty_list(tasks):
        issues.append(_issue("error", "implementation_tasks", "Manifest must include completed implementation tasks."))
    else:
        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                issues.append(_issue("error", f"implementation_tasks[{index}]", "Task must be an object."))
                continue
            if not _has_text(task.get("task")):
                issues.append(_issue("error", f"implementation_tasks[{index}].task", "Task text is required."))
            if task.get("status") != "completed":
                issues.append(_issue("error", f"implementation_tasks[{index}].status", "Task must be completed."))

    limitations = manifest.get("limitations")
    if not isinstance(limitations, dict):
        issues.append(_issue("error", "limitations", "Manifest must include limitations."))
        limitations = {}
    for key in sorted(REQUIRED_LIMITATION_KEYS):
        if not _nonempty_list(limitations.get(key)):
            issues.append(_issue("error", f"limitations.{key}", "Limitation list must be non-empty."))

    report_text, report_issues = _read_report(root_path, manifest.get("report_path"))
    issues.extend(report_issues)
    if report_text:
        if EXACT_PRODUCTION_CANDIDATE_CLAIM not in report_text:
            issues.append(_issue("error", "report", "Report must include the exact production-candidate claim."))
        if EXACT_NOT_PROVEN_ENGINE_CLAIM not in report_text:
            issues.append(_issue("error", "report", "Report must include the exact not-proven raw-agent-engine claim."))
        sections = manifest.get("required_report_sections")
        if not _nonempty_list(sections):
            issues.append(_issue("error", "required_report_sections", "Manifest must list required report sections."))
        else:
            for section in sections:
                if not _has_text(section):
                    issues.append(_issue("error", "required_report_sections", "Required section entries must be non-empty strings."))
                elif str(section) not in report_text:
                    issues.append(_issue("error", "report", f"Report is missing required section: {section}"))

    artifacts = manifest.get("required_artifacts")
    if not _nonempty_list(artifacts):
        issues.append(_issue("error", "required_artifacts", "Manifest must list evidence artifacts."))
    elif require_existing_artifacts:
        for index, artifact in enumerate(artifacts):
            if not _has_text(artifact):
                issues.append(_issue("error", f"required_artifacts[{index}]", "Artifact path must be a non-empty string."))
            elif not (root_path / str(artifact)).exists():
                issues.append(_issue("error", f"required_artifacts[{index}]", f"Evidence artifact does not exist: {artifact}"))

    if manifest.get("evidence_status") != "production_candidate_control_layer_only":
        issues.append(
            _issue(
                "error",
                "evidence_status",
                "Evidence status must be production_candidate_control_layer_only.",
            )
        )

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "required_artifact_count": len(artifacts) if isinstance(artifacts, list) else 0,
        "required_section_count": len(manifest.get("required_report_sections", [])) if isinstance(manifest.get("required_report_sections"), list) else 0,
    }


def load_manifest(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Production-candidate evidence-pack manifest must be a JSON object.")
    return payload


__all__ = [
    "EXACT_NOT_PROVEN_ENGINE_CLAIM",
    "EXACT_PRODUCTION_CANDIDATE_CLAIM",
    "PRODUCTION_EVIDENCE_PACK_VERSION",
    "load_manifest",
    "validate_production_candidate_evidence_pack",
]
