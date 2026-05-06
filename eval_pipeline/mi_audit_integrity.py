"""SHA-256 integrity manifests for MI audit JSONL outputs."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any


MI_AUDIT_INTEGRITY_MANIFEST_VERSION = "0.1"
DEFAULT_MI_AUDIT_PATH = pathlib.Path(__file__).resolve().parents[1] / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_audit.jsonl"
DEFAULT_MI_AUDIT_MANIFEST_PATH = DEFAULT_MI_AUDIT_PATH.with_suffix(DEFAULT_MI_AUDIT_PATH.suffix + ".sha256.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_lines(path: pathlib.Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"MI audit JSONL does not exist: {path}")
    return path.read_text(encoding="utf-8").splitlines()


def mi_audit_integrity_manifest(
    audit_path: str | pathlib.Path = DEFAULT_MI_AUDIT_PATH,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Generate a SHA-256 manifest for a redacted MI audit JSONL file."""

    path = pathlib.Path(audit_path)
    lines = _read_lines(path)
    line_hashes = []
    previous_chain_hash = ""
    for index, line in enumerate(lines, start=1):
        line_hash = _sha256_text(line)
        chain_hash = _sha256_text(f"{previous_chain_hash}:{line_hash}")
        line_hashes.append(
            {
                "line_number": index,
                "line_sha256": line_hash,
                "chain_sha256": chain_hash,
            }
        )
        previous_chain_hash = chain_hash

    payload = path.read_bytes()
    manifest = {
        "mi_audit_integrity_manifest_version": MI_AUDIT_INTEGRITY_MANIFEST_VERSION,
        "created_at": created_at or _utc_now(),
        "audit_path": str(path),
        "algorithm": "sha256",
        "line_count": len(lines),
        "file_size_bytes": len(payload),
        "file_sha256": _sha256_bytes(payload),
        "final_chain_sha256": previous_chain_hash,
        "line_hashes": line_hashes,
    }
    manifest["manifest_fingerprint"] = _json_hash({key: value for key, value in manifest.items() if key != "manifest_fingerprint"})
    return manifest


def write_mi_audit_integrity_manifest(
    audit_path: str | pathlib.Path = DEFAULT_MI_AUDIT_PATH,
    manifest_path: str | pathlib.Path | None = None,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Write a SHA-256 integrity manifest for an MI audit JSONL file."""

    manifest = mi_audit_integrity_manifest(audit_path, created_at=created_at)
    output_path = pathlib.Path(manifest_path) if manifest_path is not None else pathlib.Path(str(audit_path) + ".sha256.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(output_path), "bytes": output_path.stat().st_size, "manifest": manifest}


def load_mi_audit_integrity_manifest(path: str | pathlib.Path) -> dict[str, Any]:
    """Load an MI audit integrity manifest."""

    with pathlib.Path(path).open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError("MI audit integrity manifest must be a JSON object.")
    return manifest


def validate_mi_audit_integrity_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate manifest structure and manifest fingerprint."""

    issues = []
    if not isinstance(manifest, dict):
        return {"valid": False, "issues": [{"path": "$", "message": "Manifest must be a JSON object."}]}
    if manifest.get("mi_audit_integrity_manifest_version") != MI_AUDIT_INTEGRITY_MANIFEST_VERSION:
        issues.append(
            {
                "path": "$.mi_audit_integrity_manifest_version",
                "message": f"Must be {MI_AUDIT_INTEGRITY_MANIFEST_VERSION}.",
            }
        )
    for field in ("audit_path", "algorithm", "file_sha256", "final_chain_sha256", "manifest_fingerprint"):
        if not isinstance(manifest.get(field), str) or not manifest.get(field):
            issues.append({"path": f"$.{field}", "message": f"{field} must be a non-empty string."})
    if manifest.get("algorithm") != "sha256":
        issues.append({"path": "$.algorithm", "message": "Algorithm must be sha256."})
    if not isinstance(manifest.get("line_count"), int) or manifest.get("line_count") < 0:
        issues.append({"path": "$.line_count", "message": "line_count must be a non-negative integer."})
    if not isinstance(manifest.get("file_size_bytes"), int) or manifest.get("file_size_bytes") < 0:
        issues.append({"path": "$.file_size_bytes", "message": "file_size_bytes must be a non-negative integer."})
    line_hashes = manifest.get("line_hashes")
    if not isinstance(line_hashes, list):
        issues.append({"path": "$.line_hashes", "message": "line_hashes must be an array."})
    elif isinstance(manifest.get("line_count"), int) and len(line_hashes) != manifest.get("line_count"):
        issues.append({"path": "$.line_hashes", "message": "line_hashes length must equal line_count."})
    expected_fingerprint = _json_hash({key: value for key, value in manifest.items() if key != "manifest_fingerprint"})
    if manifest.get("manifest_fingerprint") != expected_fingerprint:
        issues.append({"path": "$.manifest_fingerprint", "message": "Manifest fingerprint does not match manifest contents."})
    return {"valid": not issues, "issues": issues}


def verify_mi_audit_integrity(
    audit_path: str | pathlib.Path,
    manifest: dict[str, Any] | str | pathlib.Path,
) -> dict[str, Any]:
    """Verify an MI audit JSONL file exactly matches a manifest."""

    expected = load_mi_audit_integrity_manifest(manifest) if isinstance(manifest, (str, pathlib.Path)) else manifest
    current = mi_audit_integrity_manifest(audit_path, created_at=expected.get("created_at"))
    issues = validate_mi_audit_integrity_manifest(expected)["issues"]
    for field in ("line_count", "file_size_bytes", "file_sha256", "final_chain_sha256"):
        if current.get(field) != expected.get(field):
            issues.append({"path": f"$.{field}", "message": f"Audit file {field} does not match manifest."})

    expected_lines = expected.get("line_hashes") if isinstance(expected.get("line_hashes"), list) else []
    current_lines = current.get("line_hashes")
    for index, expected_line in enumerate(expected_lines):
        current_line = current_lines[index] if index < len(current_lines) else None
        if current_line != expected_line:
            issues.append(
                {
                    "path": f"$.line_hashes[{index}]",
                    "message": "Audit line hash or chain hash does not match manifest.",
                }
            )
            break
    return {
        "valid": not issues,
        "tampered": bool(issues),
        "issues": issues,
        "current": current,
        "expected": expected,
    }


def validate_append_only_audit(
    previous_manifest: dict[str, Any] | str | pathlib.Path,
    audit_path: str | pathlib.Path,
) -> dict[str, Any]:
    """Validate the current audit file is an append-only extension of a prior manifest."""

    previous = (
        load_mi_audit_integrity_manifest(previous_manifest)
        if isinstance(previous_manifest, (str, pathlib.Path))
        else previous_manifest
    )
    current = mi_audit_integrity_manifest(audit_path, created_at=previous.get("created_at"))
    issues = validate_mi_audit_integrity_manifest(previous)["issues"]
    previous_lines = previous.get("line_hashes") if isinstance(previous.get("line_hashes"), list) else []
    current_lines = current.get("line_hashes") if isinstance(current.get("line_hashes"), list) else []

    if len(current_lines) < len(previous_lines):
        issues.append({"path": "$.line_count", "message": "Current audit is shorter than previous manifest."})
    for index, previous_line in enumerate(previous_lines):
        current_line = current_lines[index] if index < len(current_lines) else None
        if current_line != previous_line:
            issues.append(
                {
                    "path": f"$.line_hashes[{index}]",
                    "message": "Current audit changed a line covered by the previous manifest.",
                }
            )
            break

    return {
        "valid": not issues,
        "append_only": not issues,
        "issues": issues,
        "previous_line_count": len(previous_lines),
        "current_line_count": len(current_lines),
        "appended_line_count": max(0, len(current_lines) - len(previous_lines)),
        "previous_final_chain_sha256": previous.get("final_chain_sha256"),
        "current_final_chain_sha256": current.get("final_chain_sha256"),
    }


__all__ = [
    "DEFAULT_MI_AUDIT_MANIFEST_PATH",
    "DEFAULT_MI_AUDIT_PATH",
    "MI_AUDIT_INTEGRITY_MANIFEST_VERSION",
    "load_mi_audit_integrity_manifest",
    "mi_audit_integrity_manifest",
    "validate_append_only_audit",
    "validate_mi_audit_integrity_manifest",
    "verify_mi_audit_integrity",
    "write_mi_audit_integrity_manifest",
]
