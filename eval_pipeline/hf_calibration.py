"""Split-safe Hugging Face calibration governance for AANA adapters."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from eval_pipeline.hf_dataset_registry import ALLOWED_USES, load_registry, validate_hf_dataset_registry


HF_CALIBRATION_PLAN_VERSION = "0.1"
REQUIRED_CALIBRATION_FAMILIES = {
    "privacy",
    "grounded_qa",
    "tool_use",
    "finance",
    "legal",
    "pharma",
    "devops",
    "support",
}
REQUIRED_CALIBRATION_METRICS = {
    "safe_allow_rate",
    "false_positive_rate",
    "unsafe_recall",
    "route_quality",
    "schema_failure_rate",
}
REQUIRED_POLICY_FLAGS = {
    "use_hf_datasets_for_false_positive_reduction",
    "preserve_unsafe_recall",
    "calibrate_per_family",
    "keep_calibration_splits_separate_from_reporting_splits",
}


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _split_key(source: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(source.get("dataset_name", "")),
        str(source.get("config", "")),
        str(source.get("split", "")),
    )


def _registry_split_uses(registry: dict[str, Any]) -> dict[tuple[str, str, str], set[str]]:
    split_uses: dict[tuple[str, str, str], set[str]] = {}
    for dataset in registry.get("datasets", []):
        dataset_name = str(dataset.get("dataset_name", ""))
        for split_use in dataset.get("split_uses", []):
            key = (
                dataset_name,
                str(split_use.get("config", "")),
                str(split_use.get("split", "")),
            )
            split_uses.setdefault(key, set()).add(str(split_use.get("allowed_use", "")))
    return split_uses


def _check_sources(
    *,
    issues: list[dict[str, str]],
    sources: Any,
    base: str,
    registered_uses: dict[tuple[str, str, str], set[str]],
    allowed_uses: set[str],
) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    if not _nonempty_list(sources):
        issues.append(_issue("error", base, "At least one dataset source is required."))
        return keys
    for index, source in enumerate(sources):
        source_base = f"{base}[{index}]"
        if not isinstance(source, dict):
            issues.append(_issue("error", source_base, "Dataset source must be an object."))
            continue
        for field in ("dataset_name", "config", "split", "allowed_use"):
            if not _has_text(source.get(field)):
                issues.append(_issue("error", f"{source_base}.{field}", "Field is required."))
        allowed_use = str(source.get("allowed_use", ""))
        if allowed_use not in allowed_uses:
            issues.append(_issue("error", f"{source_base}.allowed_use", f"allowed_use must be one of {sorted(allowed_uses)}."))
        key = _split_key(source)
        keys.add(key)
        registry_uses = registered_uses.get(key, set())
        if allowed_use not in registry_uses:
            issues.append(
                _issue(
                    "error",
                    source_base,
                    f"Dataset/config/split is not registered for {allowed_use}: {key}.",
                )
            )
    return keys


def validate_hf_calibration_plan(plan: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    """Validate per-family HF calibration split isolation and metric tracking."""

    issues: list[dict[str, str]] = []
    if plan.get("schema_version") != HF_CALIBRATION_PLAN_VERSION:
        issues.append(_issue("error", "schema_version", f"schema_version must be {HF_CALIBRATION_PLAN_VERSION}."))

    registry_report = validate_hf_dataset_registry(registry)
    if not registry_report["valid"]:
        issues.append(_issue("error", "registry", "HF dataset registry must validate before calibration plan can pass."))
    registered_uses = _registry_split_uses(registry)

    policy = plan.get("policy")
    if not isinstance(policy, dict):
        issues.append(_issue("error", "policy", "Calibration plan must include a policy object."))
        policy = {}
    for flag in sorted(REQUIRED_POLICY_FLAGS):
        if policy.get(flag) is not True:
            issues.append(_issue("error", f"policy.{flag}", "Policy flag must be true."))
    if set(policy.get("allowed_uses") or []) != ALLOWED_USES:
        issues.append(_issue("error", "policy.allowed_uses", f"allowed_uses must be exactly {sorted(ALLOWED_USES)}."))

    metrics = plan.get("required_metrics")
    if set(metrics or []) != REQUIRED_CALIBRATION_METRICS:
        issues.append(_issue("error", "required_metrics", f"required_metrics must be exactly {sorted(REQUIRED_CALIBRATION_METRICS)}."))

    families = plan.get("families")
    if not isinstance(families, list):
        issues.append(_issue("error", "families", "Calibration plan must include a families list."))
        families = []

    seen_families: set[str] = set()
    family_count = len(families)
    measured_family_count = 0
    for family_index, family in enumerate(families):
        base = f"families[{family_index}]"
        if not isinstance(family, dict):
            issues.append(_issue("error", base, "Family entry must be an object."))
            continue
        family_id = str(family.get("family_id", ""))
        if family_id in seen_families:
            issues.append(_issue("error", f"{base}.family_id", f"Duplicate family_id: {family_id}"))
        seen_families.add(family_id)
        if family_id not in REQUIRED_CALIBRATION_FAMILIES:
            issues.append(_issue("error", f"{base}.family_id", f"family_id must be one of {sorted(REQUIRED_CALIBRATION_FAMILIES)}."))

        calibration_keys = _check_sources(
            issues=issues,
            sources=family.get("calibration_sources"),
            base=f"{base}.calibration_sources",
            registered_uses=registered_uses,
            allowed_uses={"calibration"},
        )
        reporting_keys = _check_sources(
            issues=issues,
            sources=family.get("reporting_sources"),
            base=f"{base}.reporting_sources",
            registered_uses=registered_uses,
            allowed_uses={"heldout_validation", "external_reporting"},
        )
        leakage = sorted(calibration_keys & reporting_keys)
        for dataset_name, config, split in leakage:
            issues.append(
                _issue(
                    "error",
                    f"{base}.split_isolation",
                    f"Calibration and reporting cannot share dataset/config/split: {(dataset_name, config, split)}.",
                )
            )

        targets = family.get("targets")
        if not isinstance(targets, dict):
            issues.append(_issue("error", f"{base}.targets", "Each family must define numeric calibration targets."))
            targets = {}
        for metric in sorted(REQUIRED_CALIBRATION_METRICS):
            target = targets.get(metric)
            if not isinstance(target, int | float):
                issues.append(_issue("error", f"{base}.targets.{metric}", "Target metric must be numeric."))
                continue
            if metric in {"safe_allow_rate", "unsafe_recall", "route_quality"} and not 0.0 <= float(target) <= 1.0:
                issues.append(_issue("error", f"{base}.targets.{metric}", "Rate target must be between 0 and 1."))
            if metric in {"false_positive_rate", "schema_failure_rate"} and not 0.0 <= float(target) <= 1.0:
                issues.append(_issue("error", f"{base}.targets.{metric}", "Rate target must be between 0 and 1."))

        current_metrics = family.get("current_metrics")
        if current_metrics is not None:
            if not isinstance(current_metrics, dict):
                issues.append(_issue("error", f"{base}.current_metrics", "current_metrics must be an object when present."))
                current_metrics = {}
            else:
                measured_family_count += 1
            for metric in sorted(REQUIRED_CALIBRATION_METRICS):
                value = current_metrics.get(metric)
                if not isinstance(value, int | float):
                    issues.append(_issue("error", f"{base}.current_metrics.{metric}", "Current metric must be numeric when current_metrics is present."))
                    continue
                if not 0.0 <= float(value) <= 1.0:
                    issues.append(_issue("error", f"{base}.current_metrics.{metric}", "Current metric must be between 0 and 1."))

        if not _has_text(family.get("promotion_rule")):
            issues.append(_issue("error", f"{base}.promotion_rule", "Family must define a promotion rule."))

    missing_families = sorted(REQUIRED_CALIBRATION_FAMILIES - seen_families)
    for family_id in missing_families:
        issues.append(_issue("error", "families", f"Missing required calibration family: {family_id}"))

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "family_count": family_count,
        "required_family_count": len(REQUIRED_CALIBRATION_FAMILIES),
        "measured_family_count": measured_family_count,
    }


def load_plan(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("HF calibration plan must be a JSON object.")
    return payload


__all__ = [
    "HF_CALIBRATION_PLAN_VERSION",
    "REQUIRED_CALIBRATION_FAMILIES",
    "REQUIRED_CALIBRATION_METRICS",
    "load_plan",
    "load_registry",
    "validate_hf_calibration_plan",
]
