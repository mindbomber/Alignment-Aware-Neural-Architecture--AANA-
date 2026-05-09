"""Cross-domain adapter-family validation governance."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from eval_pipeline.hf_dataset_registry import validate_hf_dataset_registry


CROSS_DOMAIN_VALIDATION_VERSION = "0.1"
REQUIRED_FAMILIES = {
    "privacy_security",
    "research_grounded_qa",
    "customer_support",
    "finance",
    "ecommerce_retail",
    "agent_tool_use_mcp",
}
ALLOWED_EXTERNAL_USES = {"heldout_validation", "external_reporting"}
REQUIRED_RESULT_METRICS = {
    "privacy_security": {"unsafe_recall", "safe_allow_rate", "false_positive_rate"},
    "research_grounded_qa": {"unsupported_claim_recall", "answerable_safe_allow_rate", "over_refusal_rate"},
    "customer_support": {"unsafe_recall", "safe_allow_rate"},
    "finance": {"unsafe_recall", "safe_allow_rate"},
    "ecommerce_retail": {"unsafe_recall", "safe_allow_rate"},
    "agent_tool_use_mcp": {"unsafe_action_recall", "safe_allow_rate", "schema_failure_rate"},
}


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _split_key(dataset_name: str, split_use: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        dataset_name,
        str(split_use.get("config", "")),
        str(split_use.get("split", "")),
        str(split_use.get("allowed_use", "")),
    )


def registry_external_splits(registry: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    output: set[tuple[str, str, str, str]] = set()
    for dataset in registry.get("datasets", []):
        dataset_name = str(dataset.get("dataset_name") or "")
        for split_use in dataset.get("split_uses", []):
            if split_use.get("allowed_use") in ALLOWED_EXTERNAL_USES:
                output.add(_split_key(dataset_name, split_use))
    return output


def validate_cross_domain_adapter_family_validation(
    manifest: dict[str, Any],
    registry: dict[str, Any],
    *,
    root: str | pathlib.Path = ".",
    require_existing_artifacts: bool = False,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    root_path = pathlib.Path(root)

    if manifest.get("schema_version") != CROSS_DOMAIN_VALIDATION_VERSION:
        issues.append(_issue("error", "schema_version", f"schema_version must be {CROSS_DOMAIN_VALIDATION_VERSION}."))

    registry_report = validate_hf_dataset_registry(registry)
    if not registry_report["valid"]:
        issues.append(_issue("error", "registry", "HF dataset registry must validate before cross-domain family validation can pass."))

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        issues.append(_issue("error", "policy", "Manifest must include a policy object."))
        policy = {}
    if policy.get("require_external_hf_heldout_before_stronger_claims") is not True:
        issues.append(
            _issue(
                "error",
                "policy.require_external_hf_heldout_before_stronger_claims",
                "Policy must require each adapter family to pass an external HF held-out set before stronger claims.",
            )
        )
    if policy.get("stronger_claim_boundary") not in {"blocked_until_external_hf_heldout_passes", "external_hf_heldout_required"}:
        issues.append(
            _issue(
                "error",
                "policy.stronger_claim_boundary",
                "Policy must block stronger claims until external HF held-out validation passes.",
            )
        )

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

    registered_external = registry_external_splits(registry)
    families = manifest.get("families")
    if not isinstance(families, list):
        issues.append(_issue("error", "families", "Manifest must include a families list."))
        families = []

    seen_families: set[str] = set()
    passed_families: set[str] = set()
    for family_index, family in enumerate(families):
        base = f"families[{family_index}]"
        if not isinstance(family, dict):
            issues.append(_issue("error", base, "Family entry must be an object."))
            continue
        family_id = str(family.get("family_id") or "")
        if family_id in seen_families:
            issues.append(_issue("error", f"{base}.family_id", f"Duplicate family id: {family_id}"))
        seen_families.add(family_id)
        if family_id not in REQUIRED_FAMILIES:
            issues.append(_issue("error", f"{base}.family_id", f"family_id must be one of {sorted(REQUIRED_FAMILIES)}."))
        if not _has_text(family.get("adapter_family")):
            issues.append(_issue("error", f"{base}.adapter_family", "Adapter family name is required."))

        datasets = family.get("datasets")
        if not _nonempty_list(datasets):
            issues.append(_issue("error", f"{base}.datasets", "Each family must map to at least one HF dataset split."))
            datasets = []
        external_pass = False
        for dataset_index, dataset in enumerate(datasets):
            dataset_base = f"{base}.datasets[{dataset_index}]"
            if not isinstance(dataset, dict):
                issues.append(_issue("error", dataset_base, "Dataset mapping must be an object."))
                continue
            for key in ("dataset_name", "config", "split", "allowed_use"):
                if not _has_text(dataset.get(key)):
                    issues.append(_issue("error", f"{dataset_base}.{key}", "Field is required."))
            allowed_use = dataset.get("allowed_use")
            if allowed_use not in ALLOWED_EXTERNAL_USES:
                issues.append(_issue("error", f"{dataset_base}.allowed_use", f"allowed_use must be one of {sorted(ALLOWED_EXTERNAL_USES)}."))
            key = (str(dataset.get("dataset_name")), str(dataset.get("config")), str(dataset.get("split")), str(dataset.get("allowed_use")))
            if key not in registered_external:
                issues.append(_issue("error", dataset_base, f"Dataset split is not registered as external/held-out in HF registry: {key}"))
            if dataset.get("validation_status") == "pass":
                external_pass = True

        result = family.get("validation_result")
        if not isinstance(result, dict):
            issues.append(_issue("error", f"{base}.validation_result", "Each family needs a validation_result object."))
            result = {}
        if result.get("status") != "pass":
            issues.append(_issue("error", f"{base}.validation_result.status", "Family validation must pass before stronger claims are allowed."))
        if not _has_text(result.get("artifact")):
            issues.append(_issue("error", f"{base}.validation_result.artifact", "Validation artifact path is required."))
        elif require_existing_artifacts and not (root_path / str(result.get("artifact"))).exists():
            issues.append(_issue("error", f"{base}.validation_result.artifact", f"Validation artifact does not exist: {result.get('artifact')}"))
        metrics = result.get("metrics")
        if not isinstance(metrics, dict) or not metrics:
            issues.append(_issue("error", f"{base}.validation_result.metrics", "Validation result must include measured metrics."))
            metrics = {}
        for metric_key in REQUIRED_RESULT_METRICS.get(family_id, set()):
            value = metrics.get(metric_key)
            if not isinstance(value, (int, float)):
                issues.append(_issue("error", f"{base}.validation_result.metrics.{metric_key}", "Required metric must be numeric."))

        if external_pass and result.get("status") == "pass":
            passed_families.add(family_id)

    missing = sorted(REQUIRED_FAMILIES - seen_families)
    for family_id in missing:
        issues.append(_issue("error", "families", f"Missing required adapter family: {family_id}"))
    not_passed = sorted(REQUIRED_FAMILIES - passed_families)
    for family_id in not_passed:
        issues.append(_issue("error", "families", f"Family has not passed an external HF held-out set: {family_id}"))

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "family_count": len(families),
        "passed_family_count": len(passed_families),
        "required_family_count": len(REQUIRED_FAMILIES),
    }


def load_manifest(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Cross-domain adapter family validation manifest must be a JSON object.")
    return payload


__all__ = [
    "CROSS_DOMAIN_VALIDATION_VERSION",
    "REQUIRED_FAMILIES",
    "load_manifest",
    "validate_cross_domain_adapter_family_validation",
]

