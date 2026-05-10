"""Evidence artifact manifest validation for AANA public-claim boundaries."""

from __future__ import annotations

import fnmatch
import json
import pathlib
import subprocess
from typing import Any

from eval_pipeline.benchmark_reporting import ALLOWED_RESULT_LABELS, PUBLIC_RESULT_LABELS


EVIDENCE_ARTIFACT_MANIFEST_VERSION = "aana.evidence_artifact_manifest.v1"
DEFAULT_MANIFEST = pathlib.Path("docs/evidence/artifact_manifest.json")
DEFAULT_COVERED_ROOT = pathlib.Path("docs/evidence")
IGNORED_EVIDENCE_FILES = {
    "docs/evidence/README.md",
    "docs/evidence/artifact_manifest.json",
}


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _as_posix(path: pathlib.Path | str) -> str:
    return pathlib.Path(path).as_posix()


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _tracked_evidence_files(root: pathlib.Path, covered_root: str) -> set[str]:
    completed = subprocess.run(
        ["git", "ls-files", covered_root],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    return {
        line.strip().replace("\\", "/")
        for line in completed.stdout.splitlines()
        if line.strip() and line.strip().replace("\\", "/") not in IGNORED_EVIDENCE_FILES
    }


def _matches(pattern: str, tracked_files: set[str]) -> set[str]:
    normalized = pattern.replace("\\", "/")
    return {path for path in tracked_files if fnmatch.fnmatchcase(path, normalized)}


def validate_evidence_artifact_manifest(
    manifest: dict[str, Any],
    *,
    root: str | pathlib.Path = ".",
    require_existing_artifacts: bool = True,
) -> dict[str, Any]:
    """Validate reviewed evidence artifact labels and public-claim eligibility."""

    root_path = pathlib.Path(root)
    issues: list[dict[str, str]] = []

    if manifest.get("schema_version") != EVIDENCE_ARTIFACT_MANIFEST_VERSION:
        issues.append(_issue("error", "schema_version", f"schema_version must be {EVIDENCE_ARTIFACT_MANIFEST_VERSION}."))

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        issues.append(_issue("error", "policy", "Manifest must include a policy object."))
        policy = {}

    if set(policy.get("allowed_result_labels") or []) != ALLOWED_RESULT_LABELS:
        issues.append(_issue("error", "policy.allowed_result_labels", f"Allowed labels must be exactly {sorted(ALLOWED_RESULT_LABELS)}."))
    if set(policy.get("public_claim_result_labels") or []) != PUBLIC_RESULT_LABELS:
        issues.append(_issue("error", "policy.public_claim_result_labels", f"Public-claim labels must be exactly {sorted(PUBLIC_RESULT_LABELS)}."))
    if policy.get("public_claim_requires_non_calibration_split") is not True:
        issues.append(_issue("error", "policy.public_claim_requires_non_calibration_split", "Public claims must not be allowed from calibration splits."))

    covered_root = str(policy.get("covered_root") or DEFAULT_COVERED_ROOT.as_posix()).replace("\\", "/")
    tracked_files: set[str] = set()
    if require_existing_artifacts:
        try:
            tracked_files = _tracked_evidence_files(root_path, covered_root)
        except (OSError, subprocess.CalledProcessError) as exc:
            issues.append(_issue("error", "policy.covered_root", f"Could not enumerate tracked evidence files: {exc}"))

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        issues.append(_issue("error", "artifacts", "Manifest must include a non-empty artifacts list."))
        artifacts = []

    covered_files: set[str] = set()
    seen_paths: set[str] = set()
    for index, artifact in enumerate(artifacts):
        base = f"artifacts[{index}]"
        if not isinstance(artifact, dict):
            issues.append(_issue("error", base, "Artifact entry must be an object."))
            continue

        artifact_path = artifact.get("artifact_path")
        if not isinstance(artifact_path, str) or not artifact_path.strip():
            issues.append(_issue("error", f"{base}.artifact_path", "Artifact path must be a non-empty string."))
            continue
        artifact_path = artifact_path.replace("\\", "/")
        if artifact_path in seen_paths:
            issues.append(_issue("error", f"{base}.artifact_path", f"Duplicate artifact path entry: {artifact_path}"))
        seen_paths.add(artifact_path)
        if not artifact_path.startswith(f"{covered_root}/") and artifact_path != covered_root:
            issues.append(_issue("error", f"{base}.artifact_path", f"Artifact must stay under {covered_root}."))

        result_label = artifact.get("result_label")
        if result_label not in ALLOWED_RESULT_LABELS:
            issues.append(_issue("error", f"{base}.result_label", f"result_label must be one of {sorted(ALLOWED_RESULT_LABELS)}."))

        source_split = artifact.get("source_split")
        if not isinstance(source_split, str) or not source_split.strip():
            issues.append(_issue("error", f"{base}.source_split", "source_split must be a non-empty string."))

        public_claim_allowed = artifact.get("public_claim_allowed")
        if not isinstance(public_claim_allowed, bool):
            issues.append(_issue("error", f"{base}.public_claim_allowed", "public_claim_allowed must be a boolean."))
            public_claim_allowed = False
        if public_claim_allowed and result_label not in PUBLIC_RESULT_LABELS:
            issues.append(_issue("error", f"{base}.public_claim_allowed", "Public claims require heldout or external_reporting result labels."))
        if public_claim_allowed and "calibration" in str(source_split).lower():
            issues.append(_issue("error", f"{base}.source_split", "Public claims cannot use calibration source splits."))
        if result_label in {"diagnostic", "probe", "calibration"} and public_claim_allowed:
            issues.append(_issue("error", f"{base}.public_claim_allowed", "Calibration, diagnostic, and probe artifacts cannot allow public claims."))

        command = artifact.get("reproduction_command")
        if not isinstance(command, str) or not command.strip():
            issues.append(_issue("error", f"{base}.reproduction_command", "reproduction_command must be a non-empty string."))

        if require_existing_artifacts:
            matches = _matches(artifact_path, tracked_files)
            if not matches:
                issues.append(_issue("error", f"{base}.artifact_path", f"Artifact path does not match any tracked evidence file: {artifact_path}"))
            covered_files.update(matches)

    if require_existing_artifacts:
        missing = sorted(tracked_files - covered_files)
        for path in missing:
            issues.append(_issue("error", "artifacts", f"Tracked evidence artifact is not covered by the manifest: {path}"))

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "artifact_entries": len(artifacts),
        "covered_files": len(covered_files),
        "tracked_files": len(tracked_files),
    }


def load_manifest(path: str | pathlib.Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    return _load_json(pathlib.Path(path))


__all__ = [
    "DEFAULT_MANIFEST",
    "EVIDENCE_ARTIFACT_MANIFEST_VERSION",
    "load_manifest",
    "validate_evidence_artifact_manifest",
]
