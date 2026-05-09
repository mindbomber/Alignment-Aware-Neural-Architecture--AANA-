"""Validation for Hugging Face dataset use in AANA adapter work."""

from __future__ import annotations

import json
import pathlib
from collections import defaultdict
from typing import Any


HF_DATASET_REGISTRY_VERSION = "0.1"
ALLOWED_USES = {"calibration", "heldout_validation", "external_reporting"}
ALLOWED_SPLIT_PURPOSES = {"tuning", "validation", "public_claim", "smoke", "audit"}
REQUIRED_DATASET_FIELDS = {
    "dataset_name",
    "license",
    "task_type",
    "adapter_families",
    "split_uses",
}
REQUIRED_SPLIT_FIELDS = {"config", "split", "allowed_use", "split_purpose", "adapter_family"}


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _split_key(dataset_name: str, split_use: dict[str, Any]) -> tuple[str, str, str]:
    return (
        dataset_name,
        str(split_use.get("config", "")),
        str(split_use.get("split", "")),
    )


def validate_hf_dataset_registry(registry: dict[str, Any]) -> dict[str, Any]:
    """Validate the HF dataset registry and split-isolation policy."""

    issues: list[dict[str, str]] = []
    if registry.get("schema_version") != HF_DATASET_REGISTRY_VERSION:
        issues.append(_issue("error", "schema_version", f"schema_version must be {HF_DATASET_REGISTRY_VERSION}."))

    policy = registry.get("policy")
    if not isinstance(policy, dict):
        issues.append(_issue("error", "policy", "Registry must include a policy object."))
        policy = {}
    if policy.get("never_use_same_split_for_tuning_and_public_claims") is not True:
        issues.append(
            _issue(
                "error",
                "policy.never_use_same_split_for_tuning_and_public_claims",
                "Policy must forbid using the same split for calibration/tuning and external reporting/public claims.",
            )
        )
    allowed_uses = policy.get("allowed_uses")
    if set(allowed_uses or []) != ALLOWED_USES:
        issues.append(_issue("error", "policy.allowed_uses", f"allowed_uses must be exactly {sorted(ALLOWED_USES)}."))

    tasks = registry.get("implementation_tasks")
    if not _nonempty_list(tasks):
        issues.append(_issue("error", "implementation_tasks", "Registry must include a non-empty implementation task list."))
    else:
        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                issues.append(_issue("error", f"implementation_tasks[{index}]", "Task must be an object."))
                continue
            if not _has_text(task.get("task")):
                issues.append(_issue("error", f"implementation_tasks[{index}].task", "Task description must be non-empty."))
            if task.get("status") != "completed":
                issues.append(_issue("error", f"implementation_tasks[{index}].status", "Implementation task must be marked completed."))

    datasets = registry.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        issues.append(_issue("error", "datasets", "Registry must include a non-empty datasets list."))
        datasets = []

    seen_datasets: set[str] = set()
    split_uses_by_key: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    split_purposes_by_key: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    external_reporting_count = 0
    calibration_count = 0
    heldout_count = 0

    for dataset_index, dataset in enumerate(datasets):
        base = f"datasets[{dataset_index}]"
        if not isinstance(dataset, dict):
            issues.append(_issue("error", base, "Dataset entry must be an object."))
            continue
        missing_fields = sorted(REQUIRED_DATASET_FIELDS - set(dataset))
        for field in missing_fields:
            issues.append(_issue("error", f"{base}.{field}", "Required dataset field is missing."))

        dataset_name = str(dataset.get("dataset_name", ""))
        if not _has_text(dataset_name) or "/" not in dataset_name:
            issues.append(_issue("error", f"{base}.dataset_name", "Dataset name must be a Hugging Face repo id such as namespace/name."))
        elif dataset_name in seen_datasets:
            issues.append(_issue("error", f"{base}.dataset_name", f"Duplicate dataset entry: {dataset_name}"))
        seen_datasets.add(dataset_name)

        for field in ("license", "task_type"):
            if not _has_text(dataset.get(field)):
                issues.append(_issue("error", f"{base}.{field}", "Field must be a non-empty string."))
        if not _nonempty_list(dataset.get("adapter_families")):
            issues.append(_issue("error", f"{base}.adapter_families", "adapter_families must be a non-empty list."))

        split_uses = dataset.get("split_uses")
        if not isinstance(split_uses, list) or not split_uses:
            issues.append(_issue("error", f"{base}.split_uses", "split_uses must be a non-empty list."))
            continue
        for split_index, split_use in enumerate(split_uses):
            split_base = f"{base}.split_uses[{split_index}]"
            if not isinstance(split_use, dict):
                issues.append(_issue("error", split_base, "split use must be an object."))
                continue
            for field in sorted(REQUIRED_SPLIT_FIELDS - set(split_use)):
                issues.append(_issue("error", f"{split_base}.{field}", "Required split-use field is missing."))
            for field in ("config", "split", "adapter_family"):
                if not _has_text(split_use.get(field)):
                    issues.append(_issue("error", f"{split_base}.{field}", "Field must be a non-empty string."))
            allowed_use = split_use.get("allowed_use")
            if allowed_use not in ALLOWED_USES:
                issues.append(_issue("error", f"{split_base}.allowed_use", f"allowed_use must be one of {sorted(ALLOWED_USES)}."))
            split_purpose = split_use.get("split_purpose")
            if split_purpose not in ALLOWED_SPLIT_PURPOSES:
                issues.append(_issue("error", f"{split_base}.split_purpose", f"split_purpose must be one of {sorted(ALLOWED_SPLIT_PURPOSES)}."))

            if allowed_use == "external_reporting":
                external_reporting_count += 1
            elif allowed_use == "calibration":
                calibration_count += 1
            elif allowed_use == "heldout_validation":
                heldout_count += 1

            key = _split_key(dataset_name, split_use)
            split_uses_by_key[key].add(str(allowed_use))
            split_purposes_by_key[key].add(str(split_purpose))

    for (dataset_name, config, split), uses in sorted(split_uses_by_key.items()):
        if "calibration" in uses and "external_reporting" in uses:
            issues.append(
                _issue(
                    "error",
                    f"datasets.{dataset_name}.{config}.{split}",
                    "The same dataset/config/split cannot be used for both calibration and external_reporting.",
                )
            )
    for (dataset_name, config, split), purposes in sorted(split_purposes_by_key.items()):
        if "tuning" in purposes and "public_claim" in purposes:
            issues.append(
                _issue(
                    "error",
                    f"datasets.{dataset_name}.{config}.{split}",
                    "The same dataset/config/split cannot be used for both tuning and public claims.",
                )
            )

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "dataset_count": len(datasets),
        "split_use_counts": {
            "calibration": calibration_count,
            "heldout_validation": heldout_count,
            "external_reporting": external_reporting_count,
        },
    }


def load_registry(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("HF dataset registry must be a JSON object.")
    return payload


__all__ = ["HF_DATASET_REGISTRY_VERSION", "load_registry", "validate_hf_dataset_registry"]
