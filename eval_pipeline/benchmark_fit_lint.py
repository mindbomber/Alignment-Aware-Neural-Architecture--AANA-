"""Lint for benchmark-answer fitting in general AANA paths."""

from __future__ import annotations

import fnmatch
import json
import pathlib
from typing import Any


BENCHMARK_FIT_LINT_VERSION = "0.1"


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def _repo_files(root: pathlib.Path, include_patterns: list[str], allow_patterns: list[str]) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for pattern in include_patterns:
        files.extend(path for path in root.glob(pattern) if path.is_file())
    unique = sorted(set(files))
    return [
        path
        for path in unique
        if not _matches(path.relative_to(root).as_posix(), allow_patterns)
    ]


def _literal_groups(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    groups = manifest.get("forbidden_literal_groups", [])
    return groups if isinstance(groups, list) else []


def validate_benchmark_fit_manifest(manifest: dict[str, Any], *, root: str | pathlib.Path = ".") -> dict[str, Any]:
    root_path = pathlib.Path(root)
    issues: list[dict[str, str]] = []
    if manifest.get("schema_version") != BENCHMARK_FIT_LINT_VERSION:
        issues.append(_issue("error", "schema_version", f"schema_version must be {BENCHMARK_FIT_LINT_VERSION}."))

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        issues.append(_issue("error", "policy", "Manifest must include a policy object."))
        policy = {}
    if policy.get("decision_rule") != "reject_answer_known_benchmark_fits_from_general_path":
        issues.append(
            _issue(
                "error",
                "policy.decision_rule",
                "Decision rule must reject changes that improve benchmark score by knowing the answer.",
            )
        )

    include_patterns = policy.get("scan_include", [])
    allow_patterns = policy.get("allowed_literal_paths", [])
    if not isinstance(include_patterns, list) or not include_patterns:
        issues.append(_issue("error", "policy.scan_include", "scan_include must be a non-empty list."))
        include_patterns = []
    if not isinstance(allow_patterns, list):
        issues.append(_issue("error", "policy.allowed_literal_paths", "allowed_literal_paths must be a list."))
        allow_patterns = []

    groups = _literal_groups(manifest)
    if not groups:
        issues.append(_issue("error", "forbidden_literal_groups", "At least one forbidden literal group is required."))

    required_surfaces = policy.get("required_adapter_family_surfaces", [])
    if isinstance(required_surfaces, list):
        for required in required_surfaces:
            if not any(fnmatch.fnmatch(str(pattern), str(required)) or fnmatch.fnmatch(str(required), str(pattern)) for pattern in include_patterns):
                issues.append(
                    _issue(
                        "error",
                        "policy.scan_include",
                        f"scan_include must cover adapter-family surface: {required}",
                    )
                )
    else:
        issues.append(_issue("error", "policy.required_adapter_family_surfaces", "required_adapter_family_surfaces must be a list when provided."))

    scanned_files = _repo_files(root_path, [str(pattern) for pattern in include_patterns], [str(pattern) for pattern in allow_patterns])
    findings: list[dict[str, str]] = []
    for path in scanned_files:
        rel_path = path.relative_to(root_path).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for group in groups:
            literals = group.get("literals", [])
            if not isinstance(literals, list):
                issues.append(_issue("error", f"forbidden_literal_groups.{group.get('id', '<missing>')}.literals", "literals must be a list."))
                continue
            for literal in literals:
                literal_text = str(literal)
                if literal_text and literal_text in text:
                    findings.append(
                        {
                            "path": rel_path,
                            "group": str(group.get("id", "unknown")),
                            "literal": literal_text,
                            "message": "Known benchmark-answer literal found in a general path.",
                        }
                    )

    for finding in findings:
        issues.append(
            _issue(
                "error",
                finding["path"],
                f"{finding['message']} group={finding['group']} literal={finding['literal']!r}",
            )
        )

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "scanned_file_count": len(scanned_files),
        "finding_count": len(findings),
    }


def load_manifest(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Benchmark-fit lint manifest must be a JSON object.")
    return payload


__all__ = ["BENCHMARK_FIT_LINT_VERSION", "load_manifest", "validate_benchmark_fit_manifest"]
