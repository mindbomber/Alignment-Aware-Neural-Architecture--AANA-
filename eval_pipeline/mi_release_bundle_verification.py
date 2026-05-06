"""Verification for AANA MI release evidence bundles."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline.mi_release_bundle import DEFAULT_MI_RELEASE_BUNDLE_DIR


MI_RELEASE_BUNDLE_VERIFICATION_VERSION = "0.1"
DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH = DEFAULT_MI_RELEASE_BUNDLE_DIR / "release_bundle_verification.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _issue(code: str, path: str, message: str, *, artifact: str | None = None) -> dict[str, str]:
    issue = {"code": code, "path": path, "message": message}
    if artifact is not None:
        issue["artifact"] = artifact
    return issue


def _artifact_checks(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    checks = []
    issues = []
    if not artifacts:
        issues.append(_issue("missing_artifacts", "$.artifacts", "Release manifest must contain bundled artifacts."))
        return checks, issues

    for name, item in sorted(artifacts.items()):
        if not isinstance(item, dict):
            issues.append(_issue("invalid_artifact_entry", f"$.artifacts.{name}", "Artifact entry must be an object.", artifact=name))
            continue
        path = pathlib.Path(str(item.get("bundle_path") or ""))
        expected_hash = item.get("sha256")
        exists = path.exists()
        actual_hash = _sha256_file(path) if exists else None
        expected_bytes = item.get("bytes")
        actual_bytes = path.stat().st_size if exists else None
        status = "pass"
        artifact_issues = []
        if not exists:
            status = "block"
            artifact_issues.append(_issue("missing_artifact", f"$.artifacts.{name}.bundle_path", "Bundled artifact does not exist.", artifact=name))
        elif actual_hash != expected_hash:
            status = "block"
            artifact_issues.append(
                _issue(
                    "sha256_mismatch",
                    f"$.artifacts.{name}.sha256",
                    "Bundled artifact SHA-256 does not match release manifest.",
                    artifact=name,
                )
            )
        if exists and isinstance(expected_bytes, int) and actual_bytes != expected_bytes:
            status = "block"
            artifact_issues.append(
                _issue(
                    "byte_count_mismatch",
                    f"$.artifacts.{name}.bytes",
                    "Bundled artifact byte count does not match release manifest.",
                    artifact=name,
                )
            )
        checks.append(
            {
                "artifact": name,
                "status": status,
                "bundle_path": str(path),
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
                "expected_bytes": expected_bytes,
                "actual_bytes": actual_bytes,
            }
        )
        issues.extend(artifact_issues)
    return checks, issues


def verify_mi_release_bundle(
    manifest_path: str | pathlib.Path = DEFAULT_MI_RELEASE_BUNDLE_DIR / "release_manifest.json",
    *,
    output_path: str | pathlib.Path | None = DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH,
) -> dict[str, Any]:
    """Verify a release bundle manifest and optionally write verification JSON."""

    path = pathlib.Path(manifest_path)
    manifest = _load_json(path)
    artifact_checks, issues = _artifact_checks(manifest)
    global_aix = manifest.get("global_aix") if isinstance(manifest.get("global_aix"), dict) else {}
    score = global_aix.get("score")
    threshold = global_aix.get("accept_threshold", 0.0)

    if manifest.get("rc_status") != "pass":
        issues.append(_issue("rc_not_pass", "$.rc_status", "Release candidate status must be pass."))
    if manifest.get("readiness_status") != "ready":
        issues.append(_issue("readiness_not_ready", "$.readiness_status", "Readiness status must be ready."))
    if not isinstance(score, (int, float)) or not isinstance(threshold, (int, float)) or float(score) < float(threshold):
        issues.append(_issue("global_aix_below_threshold", "$.global_aix.score", "Global AIx must meet or exceed accept threshold."))
    if manifest.get("unresolved_blocker_count") != 0:
        issues.append(_issue("unresolved_blockers", "$.unresolved_blocker_count", "Unresolved blocker count must be 0."))

    verification = {
        "mi_release_bundle_verification_version": MI_RELEASE_BUNDLE_VERIFICATION_VERSION,
        "created_at": _utc_now(),
        "manifest_path": str(path),
        "status": "pass" if not issues else "block",
        "valid": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "artifact_count": len(artifact_checks),
        "artifact_checks": artifact_checks,
        "release_status_checks": {
            "rc_status": manifest.get("rc_status"),
            "readiness_status": manifest.get("readiness_status"),
            "global_aix_score": score,
            "global_aix_accept_threshold": threshold,
            "unresolved_blocker_count": manifest.get("unresolved_blocker_count"),
        },
    }
    if output_path is not None:
        output = pathlib.Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return verification


__all__ = [
    "DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH",
    "MI_RELEASE_BUNDLE_VERIFICATION_VERSION",
    "verify_mi_release_bundle",
]
