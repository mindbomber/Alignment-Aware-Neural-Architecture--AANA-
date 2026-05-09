"""Repo-level gate for adapter generalization governance."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from eval_pipeline.adapter_generalization_config import load_adapter_generalization_config, validate_adapter_generalization_config
from eval_pipeline.adapter_heldout_validation import load_manifest as load_heldout_manifest
from eval_pipeline.adapter_heldout_validation import validate_adapter_heldout_manifest
from eval_pipeline.benchmark_fit_lint import load_manifest as load_benchmark_fit_manifest
from eval_pipeline.benchmark_fit_lint import validate_benchmark_fit_manifest
from eval_pipeline.benchmark_reporting import load_manifest as load_benchmark_reporting_manifest
from eval_pipeline.benchmark_reporting import validate_benchmark_reporting_manifest


ADAPTER_GENERALIZATION_GATE_VERSION = "aana.adapter_generalization_gate.v1"


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def load_manifest(path: str | pathlib.Path) -> dict[str, Any]:
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Adapter generalization manifest must be a JSON object.")
    return payload


def validate_adapter_generalization_gate(
    manifest: dict[str, Any],
    *,
    root: str | pathlib.Path = ".",
    require_existing_artifacts: bool = False,
) -> dict[str, Any]:
    root_path = pathlib.Path(root)
    issues: list[dict[str, str]] = []
    if manifest.get("schema_version") != ADAPTER_GENERALIZATION_GATE_VERSION:
        issues.append(_issue("error", "schema_version", f"schema_version must be {ADAPTER_GENERALIZATION_GATE_VERSION}."))
    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        issues.append(_issue("error", "policy", "Manifest must include a policy object."))
        policy = {}
    expected_policy = {
        "default_workflow_scope": "general_non_probe",
        "require_config_backed_domain_hints": True,
        "require_heldout_after_every_adapter_improvement": True,
        "require_benchmark_fit_lint": True,
        "require_public_claim_probe_separation": True,
    }
    for key, expected in expected_policy.items():
        if policy.get(key) != expected:
            issues.append(_issue("error", f"policy.{key}", f"Policy must be {expected!r}."))

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        issues.append(_issue("error", "artifacts", "Manifest must include artifacts."))
        artifacts = {}
    required_artifacts = {
        "generalization_config",
        "heldout_validation_manifest",
        "benchmark_fit_lint_manifest",
        "benchmark_reporting_manifest",
        "generalization_audit_doc",
    }
    for key in sorted(required_artifacts):
        value = artifacts.get(key)
        if not isinstance(value, str) or not value:
            issues.append(_issue("error", f"artifacts.{key}", "Artifact path must be a non-empty string."))
            continue
        if require_existing_artifacts and not (root_path / value).exists():
            issues.append(_issue("error", f"artifacts.{key}", f"Artifact does not exist: {value}"))

    subreports: dict[str, Any] = {}
    try:
        config = load_adapter_generalization_config(root_path / artifacts["generalization_config"])
        subreports["generalization_config"] = validate_adapter_generalization_config(config)
        if not subreports["generalization_config"]["valid"]:
            issues.extend(_issue("error", f"generalization_config.{item['path']}", item["message"]) for item in subreports["generalization_config"]["issues"])
    except Exception as exc:
        issues.append(_issue("error", "generalization_config", str(exc)))

    try:
        heldout = load_heldout_manifest(root_path / artifacts["heldout_validation_manifest"])
        subreports["heldout_validation"] = validate_adapter_heldout_manifest(heldout, root=root_path, require_existing_artifacts=False)
        if not subreports["heldout_validation"]["valid"]:
            issues.extend(_issue("error", f"heldout_validation.{item['path']}", item["message"]) for item in subreports["heldout_validation"]["issues"] if item["level"] == "error")
    except Exception as exc:
        issues.append(_issue("error", "heldout_validation", str(exc)))

    try:
        lint_manifest = load_benchmark_fit_manifest(root_path / artifacts["benchmark_fit_lint_manifest"])
        subreports["benchmark_fit_lint"] = validate_benchmark_fit_manifest(lint_manifest, root=root_path)
        if not subreports["benchmark_fit_lint"]["valid"]:
            issues.extend(_issue("error", f"benchmark_fit_lint.{item['path']}", item["message"]) for item in subreports["benchmark_fit_lint"]["issues"] if item["level"] == "error")
    except Exception as exc:
        issues.append(_issue("error", "benchmark_fit_lint", str(exc)))

    try:
        reporting = load_benchmark_reporting_manifest(root_path / artifacts["benchmark_reporting_manifest"])
        subreports["benchmark_reporting"] = validate_benchmark_reporting_manifest(reporting)
        if not subreports["benchmark_reporting"]["valid"]:
            issues.extend(_issue("error", f"benchmark_reporting.{item['path']}", item["message"]) for item in subreports["benchmark_reporting"]["issues"] if item["level"] == "error")
    except Exception as exc:
        issues.append(_issue("error", "benchmark_reporting", str(exc)))

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "issues": issues, "subreports": subreports}


__all__ = ["ADAPTER_GENERALIZATION_GATE_VERSION", "load_manifest", "validate_adapter_generalization_gate"]
