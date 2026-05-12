"""MLCFlow-compatible AANA automation step for MLCommons AIx reports."""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import subprocess
from typing import Any

from eval_pipeline import mlcommons_aix


ROOT = pathlib.Path(__file__).resolve().parents[1]
MLCFLOW_AANA_STEP_VERSION = "0.1"
MLCFLOW_AANA_STEP_MANIFEST_TYPE = "aana_mlcflow_automation_step_manifest"
DEFAULT_MLCFLOW_AANA_OUTPUT_DIR = ROOT / "eval_outputs" / "mlcflow_aana_step"
DEFAULT_MLCFLOW_AANA_MANIFEST_PATH = DEFAULT_MLCFLOW_AANA_OUTPUT_DIR / "aana-mlcflow-step-manifest.json"
CLAIM_BOUNDARY = (
    "AANA MLCFlow automation step output is workflow evidence only; it is not MLCommons benchmark certification, "
    "production certification, or go-live approval for regulated industries."
)


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: str | pathlib.Path) -> str:
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: str | pathlib.Path, payload: dict[str, Any]) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_entry(path: str | pathlib.Path, role: str) -> dict[str, Any]:
    path = pathlib.Path(path)
    return {
        "role": role,
        "path": str(path),
        "exists": path.exists(),
        "sha256": _sha256_file(path) if path.exists() and path.is_file() else None,
        "bytes": path.stat().st_size if path.exists() and path.is_file() else None,
    }


def run_optional_benchmark_command(command: str | None, *, cwd: str | pathlib.Path = ROOT, timeout_seconds: int = 3600) -> dict[str, Any] | None:
    """Run an optional benchmark command before collecting the MLCommons artifact."""

    if not command:
        return None
    completed = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "success": completed.returncode == 0,
    }


def build_mlcflow_step_manifest(
    *,
    aix_result: dict[str, Any],
    results_path: str | pathlib.Path,
    source_type: str,
    output_dir: str | pathlib.Path,
    benchmark_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an MLCFlow step manifest from the generated AANA AIx result."""

    artifacts = [
        _artifact_entry(results_path, "mlcommons_input_artifact"),
        _artifact_entry(aix_result["artifacts"]["normalized_results"], "normalized_mlcommons_results"),
        _artifact_entry(aix_result["artifacts"]["report_json"], "aana_mlcommons_aix_report_json"),
        _artifact_entry(aix_result["artifacts"]["report_markdown"], "aana_mlcommons_aix_report_markdown"),
    ]
    hard_blockers = list(aix_result.get("hard_blockers") or [])
    fail_reasons: list[str] = []
    if benchmark_result and not benchmark_result.get("success"):
        fail_reasons.append("benchmark_command_failed")
    if not aix_result.get("valid"):
        fail_reasons.append("aana_mlcommons_aix_report_invalid")
    if hard_blockers:
        fail_reasons.append("hard_blockers_present")
    step_status = "fail" if fail_reasons else "pass"
    if aix_result.get("deployment_recommendation") == "insufficient_evidence" and step_status == "pass":
        step_status = "warn"
        fail_reasons.append("insufficient_evidence")
    return {
        "manifest_type": MLCFLOW_AANA_STEP_MANIFEST_TYPE,
        "manifest_version": MLCFLOW_AANA_STEP_VERSION,
        "created_at": _utc_now(),
        "step": "aana_mlcommons_aix_report",
        "claim_boundary": CLAIM_BOUNDARY,
        "source_type": source_type,
        "output_dir": str(output_dir),
        "benchmark_result": benchmark_result,
        "aana_result": {
            "valid": aix_result.get("valid"),
            "deployment_recommendation": aix_result.get("deployment_recommendation"),
            "overall_aix": aix_result.get("overall_aix"),
            "hard_blockers": hard_blockers,
        },
        "artifacts": artifacts,
        "step_status": step_status,
        "fail_reasons": fail_reasons,
        "fail_policy": {
            "fail_on_benchmark_command_failure": True,
            "fail_on_invalid_aana_report": True,
            "fail_on_hard_blockers": True,
            "insufficient_evidence_status": "warn",
        },
    }


def validate_mlcflow_step_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(manifest, dict):
        return {"valid": False, "errors": 1, "warnings": 0, "issues": [{"level": "error", "path": "$", "message": "Manifest must be a JSON object."}]}
    if manifest.get("manifest_type") != MLCFLOW_AANA_STEP_MANIFEST_TYPE:
        issues.append({"level": "error", "path": "manifest_type", "message": f"Must be {MLCFLOW_AANA_STEP_MANIFEST_TYPE}."})
    if manifest.get("manifest_version") != MLCFLOW_AANA_STEP_VERSION:
        issues.append({"level": "error", "path": "manifest_version", "message": f"Must be {MLCFLOW_AANA_STEP_VERSION}."})
    if "not mlcommons benchmark certification" not in str(manifest.get("claim_boundary", "")).lower():
        issues.append({"level": "error", "path": "claim_boundary", "message": "Claim boundary must state this is not MLCommons benchmark certification."})
    if manifest.get("step_status") not in {"pass", "warn", "fail"}:
        issues.append({"level": "error", "path": "step_status", "message": "Step status must be pass, warn, or fail."})
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) < 4:
        issues.append({"level": "error", "path": "artifacts", "message": "Manifest must include input, normalized, JSON report, and Markdown report artifacts."})
    else:
        for index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict) or not artifact.get("exists") or not artifact.get("sha256"):
                issues.append({"level": "error", "path": f"artifacts[{index}]", "message": "Artifact must exist and include a SHA-256 hash."})
    aana_result = manifest.get("aana_result") if isinstance(manifest.get("aana_result"), dict) else {}
    if aana_result.get("hard_blockers") and manifest.get("step_status") != "fail":
        issues.append({"level": "error", "path": "step_status", "message": "Hard blockers must fail the MLCFlow step."})
    if manifest.get("step_status") == "fail" and not manifest.get("fail_reasons"):
        issues.append({"level": "error", "path": "fail_reasons", "message": "Failing step must include fail reasons."})
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "issues": issues}


def run_mlcflow_aana_step(
    *,
    results_path: str | pathlib.Path = mlcommons_aix.DEFAULT_MLCOMMONS_RESULTS_PATH,
    source_type: str = "ailuminate",
    profile_path: str | pathlib.Path = mlcommons_aix.DEFAULT_MLCOMMONS_PROFILE_PATH,
    output_dir: str | pathlib.Path = DEFAULT_MLCFLOW_AANA_OUTPUT_DIR,
    manifest_path: str | pathlib.Path | None = None,
    benchmark_command: str | None = None,
    benchmark_cwd: str | pathlib.Path = ROOT,
    benchmark_timeout_seconds: int = 3600,
) -> dict[str, Any]:
    """Run the AANA AIx report as an MLCFlow automation step."""

    output_dir = pathlib.Path(output_dir)
    manifest_path = pathlib.Path(manifest_path) if manifest_path else output_dir / "aana-mlcflow-step-manifest.json"
    benchmark_result = run_optional_benchmark_command(
        benchmark_command,
        cwd=benchmark_cwd,
        timeout_seconds=benchmark_timeout_seconds,
    )
    aix_result = mlcommons_aix.run_mlcommons_aix_report(
        results_path=results_path,
        source_type=source_type,
        profile_path=profile_path,
        output_dir=output_dir,
    )
    manifest = build_mlcflow_step_manifest(
        aix_result=aix_result,
        results_path=results_path,
        source_type=source_type,
        output_dir=output_dir,
        benchmark_result=benchmark_result,
    )
    manifest_validation = validate_mlcflow_step_manifest(manifest)
    _write_json(manifest_path, manifest)
    step_passed = manifest["step_status"] in {"pass", "warn"} and manifest_validation["valid"]
    return {
        "mlcflow_aana_step_version": MLCFLOW_AANA_STEP_VERSION,
        "valid": step_passed,
        "step_status": manifest["step_status"],
        "fail_reasons": manifest["fail_reasons"],
        "hard_blockers": manifest["aana_result"]["hard_blockers"],
        "manifest_path": str(manifest_path),
        "manifest_validation": manifest_validation,
        "aix_result": aix_result,
        "manifest": manifest,
    }


__all__ = [
    "CLAIM_BOUNDARY",
    "DEFAULT_MLCFLOW_AANA_MANIFEST_PATH",
    "DEFAULT_MLCFLOW_AANA_OUTPUT_DIR",
    "MLCFLOW_AANA_STEP_MANIFEST_TYPE",
    "MLCFLOW_AANA_STEP_VERSION",
    "build_mlcflow_step_manifest",
    "run_mlcflow_aana_step",
    "run_optional_benchmark_command",
    "validate_mlcflow_step_manifest",
]
