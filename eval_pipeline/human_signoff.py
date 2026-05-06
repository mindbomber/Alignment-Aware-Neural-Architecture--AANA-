"""Human/domain-owner signoff records for AANA MI release bundles."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline.mi_release_bundle import DEFAULT_MI_RELEASE_BUNDLE_DIR


HUMAN_SIGNOFF_VERSION = "0.1"
HUMAN_SIGNOFF_RECORD_TYPE = "aana_mi_human_signoff"
SIGNOFF_DECISIONS = ("pending", "approved", "rejected", "needs_changes")
DEFAULT_HUMAN_SIGNOFF_PATH = DEFAULT_MI_RELEASE_BUNDLE_DIR / "human_signoff.json"
DEFAULT_RELEASE_MANIFEST_PATH = DEFAULT_MI_RELEASE_BUNDLE_DIR / "release_manifest.json"
DEFAULT_RELEASE_VERIFICATION_PATH = DEFAULT_MI_RELEASE_BUNDLE_DIR / "release_bundle_verification.json"


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


def _reviewer(reviewer: dict[str, Any] | None = None) -> dict[str, Any]:
    reviewer = reviewer if isinstance(reviewer, dict) else {}
    return {
        "id": reviewer.get("id", "pending-domain-owner"),
        "name": reviewer.get("name", "Pending domain owner"),
        "role": reviewer.get("role", "domain_owner"),
    }


def human_signoff_record(
    *,
    reviewer: dict[str, Any] | None = None,
    decision: str = "pending",
    scope: dict[str, Any] | None = None,
    release_manifest_path: str | pathlib.Path = DEFAULT_RELEASE_MANIFEST_PATH,
    verification_path: str | pathlib.Path = DEFAULT_RELEASE_VERIFICATION_PATH,
    created_at: str | None = None,
    notes: str = "Human/domain-owner approval has not been granted yet.",
) -> dict[str, Any]:
    """Create a structured human signoff record bound to a release bundle hash."""

    if decision not in SIGNOFF_DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(SIGNOFF_DECISIONS)}")
    manifest_path = pathlib.Path(release_manifest_path)
    manifest = _load_json(manifest_path)
    verification_file = pathlib.Path(verification_path)
    verification = _load_json(verification_file) if verification_file.exists() else {}
    record = {
        "human_signoff_version": HUMAN_SIGNOFF_VERSION,
        "record_type": HUMAN_SIGNOFF_RECORD_TYPE,
        "created_at": created_at or _utc_now(),
        "reviewer": _reviewer(reviewer),
        "decision": decision,
        "scope": scope
        if isinstance(scope, dict)
        else {
            "release_candidate": "aana_mi",
            "approval_boundary": "local_mi_release_bundle",
            "external_production_deployment": False,
        },
        "evidence_bundle": {
            "release_manifest_path": str(manifest_path),
            "release_manifest_sha256": _sha256_file(manifest_path),
            "verification_path": str(verification_file) if verification_file.exists() else None,
            "verification_status": verification.get("status"),
            "rc_status": manifest.get("rc_status"),
            "readiness_status": manifest.get("readiness_status"),
            "global_aix": manifest.get("global_aix") if isinstance(manifest.get("global_aix"), dict) else {},
            "unresolved_blocker_count": manifest.get("unresolved_blocker_count"),
        },
        "notes": notes,
    }
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    record["signoff_fingerprint"] = hashlib.sha256(encoded).hexdigest()
    return record


def validate_human_signoff_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate human signoff shape and release-bundle binding."""

    issues = []
    if not isinstance(record, dict):
        return {"valid": False, "issues": [{"path": "$", "message": "Human signoff record must be an object."}]}
    if record.get("human_signoff_version") != HUMAN_SIGNOFF_VERSION:
        issues.append({"path": "$.human_signoff_version", "message": f"Must be {HUMAN_SIGNOFF_VERSION}."})
    if record.get("record_type") != HUMAN_SIGNOFF_RECORD_TYPE:
        issues.append({"path": "$.record_type", "message": f"Must be {HUMAN_SIGNOFF_RECORD_TYPE}."})
    if record.get("decision") not in SIGNOFF_DECISIONS:
        issues.append({"path": "$.decision", "message": "Decision is not supported."})
    for field in ("reviewer", "scope", "evidence_bundle"):
        if not isinstance(record.get(field), dict):
            issues.append({"path": f"$.{field}", "message": f"{field} must be an object."})
    reviewer = record.get("reviewer") if isinstance(record.get("reviewer"), dict) else {}
    for field in ("id", "name", "role"):
        if not isinstance(reviewer.get(field), str) or not reviewer.get(field).strip():
            issues.append({"path": f"$.reviewer.{field}", "message": "Reviewer field must be a non-empty string."})
    evidence = record.get("evidence_bundle") if isinstance(record.get("evidence_bundle"), dict) else {}
    manifest_path = evidence.get("release_manifest_path")
    expected_hash = evidence.get("release_manifest_sha256")
    if not isinstance(manifest_path, str) or not manifest_path:
        issues.append({"path": "$.evidence_bundle.release_manifest_path", "message": "Release manifest path is required."})
    else:
        path = pathlib.Path(manifest_path)
        if not path.exists():
            issues.append({"path": "$.evidence_bundle.release_manifest_path", "message": "Release manifest file does not exist."})
        elif _sha256_file(path) != expected_hash:
            issues.append({"path": "$.evidence_bundle.release_manifest_sha256", "message": "Evidence bundle hash does not match release manifest."})
    if record.get("decision") == "approved":
        if evidence.get("verification_status") != "pass":
            issues.append({"path": "$.evidence_bundle.verification_status", "message": "Approved signoff requires passing bundle verification."})
        if evidence.get("rc_status") != "pass" or evidence.get("readiness_status") != "ready":
            issues.append({"path": "$.evidence_bundle", "message": "Approved signoff requires pass/ready release status."})
        if evidence.get("unresolved_blocker_count") != 0:
            issues.append({"path": "$.evidence_bundle.unresolved_blocker_count", "message": "Approved signoff requires zero unresolved blockers."})
    return {"valid": not issues, "issues": issues}


def write_human_signoff_record(
    path: str | pathlib.Path = DEFAULT_HUMAN_SIGNOFF_PATH,
    *,
    reviewer: dict[str, Any] | None = None,
    decision: str = "pending",
    scope: dict[str, Any] | None = None,
    release_manifest_path: str | pathlib.Path = DEFAULT_RELEASE_MANIFEST_PATH,
    verification_path: str | pathlib.Path = DEFAULT_RELEASE_VERIFICATION_PATH,
    notes: str = "Human/domain-owner approval has not been granted yet.",
) -> dict[str, Any]:
    """Write the human signoff record artifact."""

    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    record = human_signoff_record(
        reviewer=reviewer,
        decision=decision,
        scope=scope,
        release_manifest_path=release_manifest_path,
        verification_path=verification_path,
        notes=notes,
    )
    validation = validate_human_signoff_record(record)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"record": record, "validation": validation, "path": str(output), "bytes": output.stat().st_size}


__all__ = [
    "DEFAULT_HUMAN_SIGNOFF_PATH",
    "DEFAULT_RELEASE_MANIFEST_PATH",
    "DEFAULT_RELEASE_VERIFICATION_PATH",
    "HUMAN_SIGNOFF_RECORD_TYPE",
    "HUMAN_SIGNOFF_VERSION",
    "SIGNOFF_DECISIONS",
    "human_signoff_record",
    "validate_human_signoff_record",
    "write_human_signoff_record",
]
