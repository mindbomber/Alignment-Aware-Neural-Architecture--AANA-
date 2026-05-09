"""Held-out validation gate for AANA adapter improvements."""

from __future__ import annotations

import fnmatch
import json
import pathlib
from typing import Any


ADAPTER_HELDOUT_VALIDATION_VERSION = "0.1"
ALLOWED_SPLITS = {"held_out", "blind", "external", "maintainer_eval"}
BLOCKED_SPLITS = {"train", "training", "dev", "tuned", "calibration", "prompt_tuning"}
ALLOWED_LABEL_VISIBILITY = {"hidden_from_gate", "benchmark_maintainer", "human_reviewed", "public_benchmark_labels_hidden"}
ADAPTER_IMPROVEMENT_PATTERNS = (
    "examples/*_adapter.json",
    "examples/hf_dataset_validation_registry.json",
    "examples/cross_domain_adapter_family_validation.json",
    "examples/production_candidate_evidence_pack.json",
    "examples/starter_pilot_kits/**/adapter_config.json",
    "examples/tau2/aana_contract_agent.py",
    "examples/tau2/aana_tau2_adapter_config.json",
    "eval_pipeline/adapter_runner/**",
    "eval_pipeline/agent_tool_use_control.py",
    "eval_pipeline/benchmark_*.py",
    "eval_pipeline/hf_dataset_registry.py",
    "eval_pipeline/cross_domain_adapter_family_validation.py",
    "eval_pipeline/production_candidate_evidence_pack.py",
    "scripts/run_agent_tool_use_control_eval.py",
    "scripts/validate_cross_domain_adapter_families.py",
    "scripts/validate_production_candidate_evidence_pack.py",
    "scripts/validate_benchmark_*.py",
    "scripts/validate_hf_dataset_registry.py",
    "docs/families/**",
    "docs/adapter-gallery/**",
)
METRIC_KEYS = {
    "task_success",
    "pass1",
    "action_check_pass_rate",
    "unsafe_recall",
    "safe_allow_rate",
    "false_positive_rate",
    "schema_failure_rate",
}


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _matches_adapter_improvement_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in ADAPTER_IMPROVEMENT_PATTERNS)


def _validate_metrics(metrics: Any, base: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(metrics, dict) or not metrics:
        return [_issue("error", base, "Held-out validation must include measured metrics.")]
    if not any(key in metrics for key in METRIC_KEYS):
        issues.append(
            _issue(
                "error",
                base,
                "Metrics must include at least one held-out outcome such as task_success, pass1, action_check_pass_rate, unsafe_recall, safe_allow_rate, false_positive_rate, or schema_failure_rate.",
            )
        )
    for key, value in metrics.items():
        if not isinstance(value, (int, float)):
            issues.append(_issue("error", f"{base}.{key}", "Metric values must be numeric."))
        elif value < 0:
            issues.append(_issue("error", f"{base}.{key}", "Metric values cannot be negative."))
    return issues


def validate_adapter_improvement_record(
    record: dict[str, Any],
    *,
    index: int,
    root: str | pathlib.Path = ".",
    require_existing_artifacts: bool = False,
) -> list[dict[str, str]]:
    """Validate one adapter-improvement record."""

    issues: list[dict[str, str]] = []
    base = f"adapter_improvements[{index}]"
    root_path = pathlib.Path(root)

    for key in ("improvement_id", "adapter_id", "summary"):
        if not _has_text(record.get(key)):
            issues.append(_issue("error", f"{base}.{key}", "Field must be a non-empty string."))

    changed_paths = record.get("changed_paths")
    if not _is_nonempty_list(changed_paths) or not all(_has_text(path) for path in changed_paths):
        issues.append(_issue("error", f"{base}.changed_paths", "Adapter improvements must list changed adapter paths."))
    elif not any(_matches_adapter_improvement_path(path) for path in changed_paths):
        issues.append(
            _issue(
                "warning",
                f"{base}.changed_paths",
                "No changed path matches the known adapter-improvement surfaces; confirm this record is needed.",
            )
        )

    validation = record.get("heldout_validation")
    if not isinstance(validation, dict):
        issues.append(_issue("error", f"{base}.heldout_validation", "Every adapter improvement requires a held-out validation object."))
        return issues

    for key in ("task_set", "result_artifact", "notes"):
        if not _has_text(validation.get(key)):
            issues.append(_issue("error", f"{base}.heldout_validation.{key}", "Field must be a non-empty string."))

    split = validation.get("split")
    if split in BLOCKED_SPLITS:
        issues.append(_issue("error", f"{base}.heldout_validation.split", "Adapter validation cannot use training, tuning, dev, or calibration data."))
    elif split not in ALLOWED_SPLITS:
        issues.append(_issue("error", f"{base}.heldout_validation.split", f"Split must be one of {sorted(ALLOWED_SPLITS)}."))

    label_visibility = validation.get("label_visibility")
    if label_visibility not in ALLOWED_LABEL_VISIBILITY:
        issues.append(
            _issue(
                "error",
                f"{base}.heldout_validation.label_visibility",
                f"Label visibility must be one of {sorted(ALLOWED_LABEL_VISIBILITY)}.",
            )
        )

    if validation.get("status") != "pass":
        issues.append(_issue("error", f"{base}.heldout_validation.status", "Held-out validation must pass before the adapter improvement is treated as complete."))

    if validation.get("run_without_benchmark_probes") is not True:
        issues.append(
            _issue(
                "error",
                f"{base}.heldout_validation.run_without_benchmark_probes",
                "Held-out validation must run without benchmark probes unless the record is explicitly diagnostic-only.",
            )
        )

    issues.extend(_validate_metrics(validation.get("metrics"), f"{base}.heldout_validation.metrics"))

    if require_existing_artifacts:
        for key in ("task_set_path", "result_artifact"):
            value = validation.get(key)
            if _has_text(value) and not (root_path / value).exists():
                issues.append(_issue("error", f"{base}.heldout_validation.{key}", f"Referenced artifact does not exist: {value}"))

    return issues


def validate_adapter_heldout_manifest(
    manifest: dict[str, Any],
    *,
    root: str | pathlib.Path = ".",
    require_existing_artifacts: bool = False,
) -> dict[str, Any]:
    """Validate the repo-level held-out validation manifest."""

    issues: list[dict[str, str]] = []
    if manifest.get("schema_version") != ADAPTER_HELDOUT_VALIDATION_VERSION:
        issues.append(
            _issue(
                "error",
                "schema_version",
                f"schema_version must be {ADAPTER_HELDOUT_VALIDATION_VERSION}.",
            )
        )
    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        issues.append(_issue("error", "policy", "Manifest must include a policy object."))
    else:
        if policy.get("require_after_every_adapter_improvement") is not True:
            issues.append(_issue("error", "policy.require_after_every_adapter_improvement", "Policy must require held-out tasks after every adapter improvement."))
        if policy.get("allow_training_or_tuned_split") is not False:
            issues.append(_issue("error", "policy.allow_training_or_tuned_split", "Training or tuned splits must not satisfy held-out validation."))
        surfaces = policy.get("adapter_family_surfaces", [])
        if not isinstance(surfaces, list) or not surfaces:
            issues.append(_issue("error", "policy.adapter_family_surfaces", "Policy must list adapter-family surfaces covered by the held-out requirement."))
        else:
            missing = [pattern for pattern in ADAPTER_IMPROVEMENT_PATTERNS if pattern not in surfaces]
            for pattern in missing:
                issues.append(_issue("error", "policy.adapter_family_surfaces", f"Missing adapter-family surface: {pattern}"))

    records = manifest.get("adapter_improvements")
    if not isinstance(records, list):
        issues.append(_issue("error", "adapter_improvements", "Manifest must include an adapter_improvements list."))
        records = []

    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            issues.append(_issue("error", f"adapter_improvements[{index}]", "Adapter improvement record must be an object."))
            continue
        improvement_id = str(record.get("improvement_id", ""))
        if improvement_id and improvement_id in seen_ids:
            issues.append(_issue("error", f"adapter_improvements[{index}].improvement_id", f"Duplicate improvement id: {improvement_id}"))
        seen_ids.add(improvement_id)
        issues.extend(
            validate_adapter_improvement_record(
                record,
                index=index,
                root=root,
                require_existing_artifacts=require_existing_artifacts,
            )
        )

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "record_count": len(records),
    }


def load_manifest(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Held-out validation manifest must be a JSON object.")
    return payload


__all__ = [
    "ADAPTER_HELDOUT_VALIDATION_VERSION",
    "validate_adapter_heldout_manifest",
    "validate_adapter_improvement_record",
    "load_manifest",
]
