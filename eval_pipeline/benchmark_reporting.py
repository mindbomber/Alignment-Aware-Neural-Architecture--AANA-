"""Benchmark reporting validation for public AANA claims."""

from __future__ import annotations

import json
import pathlib
from typing import Any


BENCHMARK_REPORTING_POLICY_VERSION = "0.1"
ALLOWED_RUN_TYPES = {"general", "diagnostic_probe", "mixed"}
PUBLIC_CLAIM_FORBIDDEN_RUN_TYPES = {"diagnostic_probe", "mixed"}


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _validate_report(report: dict[str, Any], index: int) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    base = f"benchmark_reports[{index}]"

    for key in ("report_id", "benchmark", "summary", "scope_label"):
        if not _has_text(report.get(key)):
            issues.append(_issue("error", f"{base}.{key}", "Field must be a non-empty string."))

    run_type = report.get("run_type")
    if run_type not in ALLOWED_RUN_TYPES:
        issues.append(_issue("error", f"{base}.run_type", f"run_type must be one of {sorted(ALLOWED_RUN_TYPES)}."))

    public_claim = bool(report.get("public_claim"))
    includes_probe_results = bool(report.get("includes_probe_results"))
    public_claim_eligible = bool(report.get("public_claim_eligible"))

    if public_claim and run_type in PUBLIC_CLAIM_FORBIDDEN_RUN_TYPES:
        issues.append(_issue("error", f"{base}.public_claim", "Public AANA claims cannot use diagnostic_probe or mixed benchmark reports."))
    if public_claim and includes_probe_results:
        issues.append(_issue("error", f"{base}.includes_probe_results", "Public AANA claims must exclude probe results from all reported metrics."))
    if public_claim and not public_claim_eligible:
        issues.append(_issue("error", f"{base}.public_claim_eligible", "Public claims require public_claim_eligible=true."))
    if includes_probe_results and public_claim_eligible:
        issues.append(_issue("error", f"{base}.public_claim_eligible", "Reports that include probe results cannot be public-claim eligible."))

    if report.get("uses_allow_benchmark_probes") is True and public_claim:
        issues.append(_issue("error", f"{base}.uses_allow_benchmark_probes", "Runs using --allow-benchmark-probes cannot support public claims."))

    if public_claim:
        caveats = report.get("limitations")
        if not _is_nonempty_list(caveats):
            issues.append(_issue("error", f"{base}.limitations", "Public benchmark claims require explicit limitations."))
        if "diagnostic" in str(report.get("summary", "")).lower() and "public" in str(report.get("scope_label", "")).lower():
            issues.append(_issue("warning", f"{base}.summary", "Summary uses diagnostic language while marked as a public claim; verify scope is clear."))

    if report.get("probe_results_policy") != "excluded_from_public_claims":
        issues.append(
            _issue(
                "error",
                f"{base}.probe_results_policy",
                "probe_results_policy must be excluded_from_public_claims.",
            )
        )

    artifacts = report.get("artifacts")
    if not isinstance(artifacts, dict):
        issues.append(_issue("error", f"{base}.artifacts", "Artifacts must be an object."))
    else:
        for key in ("primary_results", "probe_results"):
            if key in artifacts and not isinstance(artifacts[key], list):
                issues.append(_issue("error", f"{base}.artifacts.{key}", "Artifact groups must be lists."))
        if public_claim and artifacts.get("probe_results"):
            issues.append(_issue("error", f"{base}.artifacts.probe_results", "Public-claim reports must not attach probe results as claim evidence."))

    return issues


def validate_benchmark_reporting_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if manifest.get("schema_version") != BENCHMARK_REPORTING_POLICY_VERSION:
        issues.append(_issue("error", "schema_version", f"schema_version must be {BENCHMARK_REPORTING_POLICY_VERSION}."))

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        issues.append(_issue("error", "policy", "Manifest must include a policy object."))
    else:
        if policy.get("never_merge_probe_results_into_public_claims") is not True:
            issues.append(_issue("error", "policy.never_merge_probe_results_into_public_claims", "Policy must forbid merging probe results into public claims."))
        if policy.get("require_scope_label") is not True:
            issues.append(_issue("error", "policy.require_scope_label", "Policy must require a scope label."))

    reports = manifest.get("benchmark_reports")
    if not isinstance(reports, list):
        issues.append(_issue("error", "benchmark_reports", "Manifest must include a benchmark_reports list."))
        reports = []

    seen_ids: set[str] = set()
    for index, report in enumerate(reports):
        if not isinstance(report, dict):
            issues.append(_issue("error", f"benchmark_reports[{index}]", "Benchmark report must be an object."))
            continue
        report_id = str(report.get("report_id", ""))
        if report_id and report_id in seen_ids:
            issues.append(_issue("error", f"benchmark_reports[{index}].report_id", f"Duplicate report id: {report_id}"))
        seen_ids.add(report_id)
        issues.extend(_validate_report(report, index))

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "report_count": len(reports),
    }


def load_manifest(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Benchmark reporting manifest must be a JSON object.")
    return payload


__all__ = [
    "BENCHMARK_REPORTING_POLICY_VERSION",
    "load_manifest",
    "validate_benchmark_reporting_manifest",
]
