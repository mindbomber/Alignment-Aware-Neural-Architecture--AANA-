"""Reproducible evidence bundle for a passing AANA MI release candidate."""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
from datetime import datetime, timezone
from typing import Any

from eval_pipeline.mi_release_candidate import DEFAULT_MI_RELEASE_CANDIDATE_REPORT


MI_RELEASE_BUNDLE_VERSION = "0.1"
ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MI_RELEASE_BUNDLE_DIR = ROOT / "eval_outputs" / "mi_release_candidate" / "release_bundle"
DEFAULT_ARTIFACTS = {
    "release_candidate_report": DEFAULT_MI_RELEASE_CANDIDATE_REPORT,
    "readiness_report": ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "production_mi_release_report.json",
    "production_readiness": ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "production_mi_readiness.json",
    "audit_jsonl": ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_audit.jsonl",
    "audit_manifest": ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_audit.jsonl.sha256.json",
    "dashboard": ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_dashboard.json",
    "benchmark_report": ROOT / "eval_outputs" / "mi_benchmark" / "mi_benchmark_report.json",
    "pilot_handoffs": ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "pilot_handoffs.json",
    "remediation_report": ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "release_blocker_remediation.json",
}


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
    return payload if isinstance(payload, dict) else {}


def _copy_artifact(source: pathlib.Path, bundle_dir: pathlib.Path) -> pathlib.Path:
    target = bundle_dir / "artifacts" / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def _version_summary(rc: dict[str, Any], readiness: dict[str, Any], release_readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "mi_release_bundle_version": MI_RELEASE_BUNDLE_VERSION,
        "mi_release_candidate_version": rc.get("mi_release_candidate_version"),
        "production_mi_readiness_version": readiness.get("production_mi_readiness_version"),
        "release_readiness_report_version": release_readiness.get("release_readiness_report_version"),
    }


def release_note_markdown(manifest: dict[str, Any]) -> str:
    """Return a short human-readable release note for the MI release bundle."""

    return f"""# AANA MI Release Candidate Evidence Bundle

Status: {manifest["rc_status"]}

This bundle snapshots the passing AANA Mechanistic Interoperability release candidate evidence. The release candidate passed contract validation, benchmark checks, guarded pilot checks, redacted audit validation, audit integrity validation, production readiness, dashboard validation, release-readiness validation, and final end-to-end MI contract validation.

Key results:

- RC status: {manifest["rc_status"]}
- Readiness status: {manifest["readiness_status"]}
- Global AIx: {manifest["global_aix"]["score"]}
- Unresolved blockers: {manifest["unresolved_blocker_count"]}
- Artifact count: {len(manifest["artifacts"])}

Out of scope:

- External production deployment approval.
- Immutable remote audit storage.
- Live connector authorization and rate limits.
- Domain-owner signoff outside this local repository.
- Incident response or long-term monitoring operations.
"""


def create_mi_release_bundle(
    bundle_dir: str | pathlib.Path = DEFAULT_MI_RELEASE_BUNDLE_DIR,
    *,
    artifact_paths: dict[str, str | pathlib.Path] | None = None,
) -> dict[str, Any]:
    """Snapshot passing MI release evidence into a reproducible bundle."""

    output_dir = pathlib.Path(bundle_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {key: pathlib.Path(value) for key, value in DEFAULT_ARTIFACTS.items()}
    for key, value in (artifact_paths or {}).items():
        paths[key] = pathlib.Path(value)

    missing = [f"{key}: {path}" for key, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing release bundle artifact(s): " + "; ".join(missing))

    rc = _load_json(paths["release_candidate_report"])
    readiness = _load_json(paths["production_readiness"])
    release_readiness = _load_json(paths["readiness_report"])
    artifacts = {}
    for key, source in sorted(paths.items()):
        copied = _copy_artifact(source, output_dir)
        artifacts[key] = {
            "source_path": str(source),
            "bundle_path": str(copied),
            "sha256": _sha256_file(copied),
            "bytes": copied.stat().st_size,
        }

    manifest = {
        "mi_release_bundle_version": MI_RELEASE_BUNDLE_VERSION,
        "created_at": _utc_now(),
        "bundle_dir": str(output_dir),
        "rc_status": rc.get("status"),
        "readiness_status": readiness.get("release_status"),
        "global_aix": readiness.get("global_aix") if isinstance(readiness.get("global_aix"), dict) else {},
        "unresolved_blocker_count": len(rc.get("unresolved_items", [])) if isinstance(rc.get("unresolved_items"), list) else None,
        "versions": _version_summary(rc, readiness, release_readiness),
        "artifacts": artifacts,
    }
    manifest_path = output_dir / "release_manifest.json"
    release_note_path = output_dir / "release_note.md"
    release_note = release_note_markdown(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    release_note_path.write_text(release_note, encoding="utf-8")
    return {
        "manifest": manifest,
        "release_note": release_note,
        "paths": {
            "bundle_dir": str(output_dir),
            "release_manifest": str(manifest_path),
            "release_note": str(release_note_path),
        },
    }


__all__ = [
    "DEFAULT_ARTIFACTS",
    "DEFAULT_MI_RELEASE_BUNDLE_DIR",
    "MI_RELEASE_BUNDLE_VERSION",
    "create_mi_release_bundle",
    "release_note_markdown",
]
