"""Durable append-only storage option for redacted AANA runtime audit records."""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

from eval_pipeline import audit


DURABLE_AUDIT_STORAGE_VERSION = "0.1"
DURABLE_AUDIT_STORAGE_TYPE = "aana_durable_audit_storage"
DEFAULT_DURABLE_AUDIT_DIR = pathlib.Path(__file__).resolve().parents[1] / "eval_outputs" / "durable_audit_storage"
DEFAULT_DURABLE_AUDIT_JSONL = DEFAULT_DURABLE_AUDIT_DIR / "aana_audit.jsonl"
DEFAULT_DURABLE_AUDIT_MANIFEST = DEFAULT_DURABLE_AUDIT_JSONL.with_suffix(
    DEFAULT_DURABLE_AUDIT_JSONL.suffix + ".sha256.json"
)
DEFAULT_DURABLE_AUDIT_CONFIG_PATH = pathlib.Path(__file__).resolve().parents[1] / "examples" / "durable_audit_storage.json"


def _file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(payload: dict[str, Any]) -> str:
    copy = dict(payload)
    copy.pop("manifest_sha256", None)
    encoded = json.dumps(copy, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: str | pathlib.Path, payload: dict[str, Any]) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _raw_field_findings(value: Any, path: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            key_text = str(key).lower()
            is_fingerprint_metadata = ".input_fingerprints." in child_path
            allowed_raw_metadata = key_text in {"raw_payload_logged", "raw_artifact_storage", "raw_payload_storage"}
            if not is_fingerprint_metadata and (
                (key_text.startswith("raw_") and not allowed_raw_metadata)
                or key_text in {"prompt", "candidate", "evidence", "safe_response", "output"}
            ):
                findings.append({"level": "error", "path": child_path, "message": "Durable audit storage cannot store raw payload fields."})
            findings.extend(_raw_field_findings(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_raw_field_findings(child, f"{path}[{index}]"))
    return findings


def _load_manifest(path: pathlib.Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Durable audit manifest must be a JSON object.")
    return payload


def durable_audit_storage_config() -> dict[str, Any]:
    """Return the default local durable storage config."""

    return {
        "durable_audit_storage_version": DURABLE_AUDIT_STORAGE_VERSION,
        "storage_type": DURABLE_AUDIT_STORAGE_TYPE,
        "storage_mode": "local_append_only",
        "audit_path": str(DEFAULT_DURABLE_AUDIT_JSONL),
        "manifest_path": str(DEFAULT_DURABLE_AUDIT_MANIFEST),
        "redacted_records_only": True,
        "raw_payload_storage": "disabled",
        "append_only": True,
        "tamper_evident_manifest": True,
        "retention": {
            "minimum_days": 365,
            "legal_hold_supported": True,
            "production_remote_backend_required_for_go_live": True,
        },
        "production_boundary": (
            "Local durable storage is suitable for production-candidate testing. "
            "External production still needs customer-approved immutable storage, access controls, backups, and retention enforcement."
        ),
    }


def validate_durable_audit_storage_config(config: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(config, dict):
        return {"valid": False, "errors": 1, "warnings": 0, "issues": [{"level": "error", "path": "$", "message": "Config must be an object."}]}
    if config.get("durable_audit_storage_version") != DURABLE_AUDIT_STORAGE_VERSION:
        issues.append({"level": "error", "path": "durable_audit_storage_version", "message": f"Must be {DURABLE_AUDIT_STORAGE_VERSION}."})
    if config.get("storage_type") != DURABLE_AUDIT_STORAGE_TYPE:
        issues.append({"level": "error", "path": "storage_type", "message": f"Must be {DURABLE_AUDIT_STORAGE_TYPE}."})
    if config.get("storage_mode") != "local_append_only":
        issues.append({"level": "error", "path": "storage_mode", "message": "V1 durable storage mode must be local_append_only."})
    if config.get("redacted_records_only") is not True:
        issues.append({"level": "error", "path": "redacted_records_only", "message": "Durable storage must accept redacted records only."})
    if config.get("raw_payload_storage") != "disabled":
        issues.append({"level": "error", "path": "raw_payload_storage", "message": "Raw payload storage must be disabled."})
    if config.get("append_only") is not True:
        issues.append({"level": "error", "path": "append_only", "message": "Durable storage must be append-only."})
    for key in ("audit_path", "manifest_path"):
        if not isinstance(config.get(key), str) or not config.get(key).strip():
            issues.append({"level": "error", "path": key, "message": "Path must be a non-empty string."})
    retention = config.get("retention") if isinstance(config.get("retention"), dict) else {}
    if not isinstance(retention.get("minimum_days"), int) or retention.get("minimum_days") < 365:
        issues.append({"level": "error", "path": "retention.minimum_days", "message": "Retention must be at least 365 days."})
    if retention.get("production_remote_backend_required_for_go_live") is not True:
        issues.append({"level": "warning", "path": "retention.production_remote_backend_required_for_go_live", "message": "Remote immutable backend should remain required for go-live."})
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "issues": issues}


def write_durable_audit_storage_config(path: str | pathlib.Path = DEFAULT_DURABLE_AUDIT_CONFIG_PATH) -> dict[str, Any]:
    config = durable_audit_storage_config()
    validation = validate_durable_audit_storage_config(config)
    _write_json(path, config)
    return {"path": str(path), "config": config, "validation": validation}


def _verify_manifest_self_hash(manifest: dict[str, Any], issues: list[dict[str, str]]) -> None:
    if manifest.get("manifest_sha256") != _canonical_sha256(manifest):
        issues.append({"level": "error", "path": "$.manifest_sha256", "message": "Manifest self-hash does not match."})


def _verify_current(audit_path: pathlib.Path, manifest_path: pathlib.Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    if manifest is None:
        return {"valid": True, "manifest": None, "issues": []}
    report = verify_durable_audit_storage(audit_path=audit_path, manifest_path=manifest_path)
    if not report["valid"]:
        raise ValueError("Durable audit storage cannot append to a tampered audit log.")
    return {"valid": True, "manifest": manifest, "issues": []}


def _manifest(audit_path: pathlib.Path, previous_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    records = audit.load_jsonl(audit_path)
    payload = {
        "durable_audit_storage_version": DURABLE_AUDIT_STORAGE_VERSION,
        "storage_type": DURABLE_AUDIT_STORAGE_TYPE,
        "storage_mode": "local_append_only",
        "audit_log_path": str(audit_path.resolve()),
        "audit_log_sha256": _file_sha256(audit_path),
        "audit_log_size_bytes": audit_path.stat().st_size,
        "record_count": len(records),
        "redacted_records_only": True,
        "raw_payload_storage": "disabled",
        "summary": audit.summarize_records(records),
    }
    if previous_manifest:
        payload["previous_audit_log_size_bytes"] = previous_manifest.get("audit_log_size_bytes")
        payload["previous_audit_log_sha256"] = previous_manifest.get("audit_log_sha256")
        payload["previous_record_count"] = previous_manifest.get("record_count")
        payload["previous_manifest_sha256"] = previous_manifest.get("manifest_sha256")
    payload["manifest_sha256"] = _canonical_sha256(payload)
    return payload


def append_durable_audit_records(
    records: dict[str, Any] | list[dict[str, Any]],
    *,
    audit_path: str | pathlib.Path = DEFAULT_DURABLE_AUDIT_JSONL,
    manifest_path: str | pathlib.Path = DEFAULT_DURABLE_AUDIT_MANIFEST,
) -> dict[str, Any]:
    """Append redacted AANA audit records to local durable storage."""

    rows = records if isinstance(records, list) else [records]
    rows = [row for row in rows if isinstance(row, dict)]
    validation = audit.validate_audit_records(rows)
    raw_findings = []
    for index, row in enumerate(rows):
        raw_findings.extend(_raw_field_findings(row, f"$[{index}]"))
    if not validation["valid"] or raw_findings:
        raise ValueError("Durable audit storage only accepts valid redacted AANA audit records.")
    audit_file = pathlib.Path(audit_path)
    manifest_file = pathlib.Path(manifest_path)
    previous = _verify_current(audit_file, manifest_file)["manifest"]
    for row in rows:
        audit.append_jsonl(audit_file, row)
    current = _manifest(audit_file, previous)
    _write_json(manifest_file, current)
    return {
        "durable_audit_storage_version": DURABLE_AUDIT_STORAGE_VERSION,
        "storage_mode": "local_append_only",
        "audit_path": str(audit_file),
        "manifest_path": str(manifest_file),
        "record_count": len(rows),
        "line_count": current["record_count"],
        "append_only": True,
        "manifest_sha256": current["manifest_sha256"],
        "audit_log_sha256": current["audit_log_sha256"],
        "redacted_records_only": True,
        "raw_payload_storage": "disabled",
    }


def import_audit_log_to_durable_storage(
    source_audit_log: str | pathlib.Path,
    *,
    audit_path: str | pathlib.Path = DEFAULT_DURABLE_AUDIT_JSONL,
    manifest_path: str | pathlib.Path = DEFAULT_DURABLE_AUDIT_MANIFEST,
) -> dict[str, Any]:
    """Import an existing redacted AANA audit JSONL file into durable storage."""

    records = audit.load_jsonl(source_audit_log)
    return append_durable_audit_records(records, audit_path=audit_path, manifest_path=manifest_path)


def verify_durable_audit_storage(
    *,
    audit_path: str | pathlib.Path = DEFAULT_DURABLE_AUDIT_JSONL,
    manifest_path: str | pathlib.Path = DEFAULT_DURABLE_AUDIT_MANIFEST,
) -> dict[str, Any]:
    """Verify the durable audit log, manifest, and append-only prefix."""

    audit_file = pathlib.Path(audit_path)
    manifest_file = pathlib.Path(manifest_path)
    issues: list[dict[str, str]] = []
    if not audit_file.exists() or not manifest_file.exists():
        return {
            "durable_audit_storage_version": DURABLE_AUDIT_STORAGE_VERSION,
            "valid": False,
            "storage_mode": "local_append_only",
            "audit_path": str(audit_file),
            "manifest_path": str(manifest_file),
            "issues": [{"level": "error", "path": "$", "message": "Audit JSONL and manifest must both exist."}],
        }
    manifest = _load_manifest(manifest_file) or {}
    _verify_manifest_self_hash(manifest, issues)
    if manifest.get("audit_log_sha256") != _file_sha256(audit_file):
        issues.append({"level": "error", "path": "$.audit_log_sha256", "message": "Audit log SHA-256 does not match manifest."})
    if manifest.get("audit_log_size_bytes") != audit_file.stat().st_size:
        issues.append({"level": "error", "path": "$.audit_log_size_bytes", "message": "Audit log byte size does not match manifest."})
    try:
        records = audit.load_jsonl(audit_file)
        validation = audit.validate_audit_records(records)
        if not validation["valid"]:
            issues.extend(validation["issues"])
        if manifest.get("record_count") != len(records):
            issues.append({"level": "error", "path": "$.record_count", "message": "Audit record count does not match manifest."})
    except ValueError as exc:
        records = []
        issues.append({"level": "error", "path": "$.audit_log_path", "message": str(exc)})

    previous_size = manifest.get("previous_audit_log_size_bytes")
    previous_hash = manifest.get("previous_audit_log_sha256")
    if isinstance(previous_size, int) and isinstance(previous_hash, str):
        with audit_file.open("rb") as handle:
            prefix = handle.read(previous_size)
        if hashlib.sha256(prefix).hexdigest() != previous_hash:
            issues.append({"level": "error", "path": "$.previous_audit_log_sha256", "message": "Current audit log no longer preserves the previous append-only prefix."})

    errors = sum(1 for issue in issues if issue.get("level") == "error")
    return {
        "durable_audit_storage_version": DURABLE_AUDIT_STORAGE_VERSION,
        "valid": errors == 0,
        "errors": errors,
        "storage_mode": "local_append_only",
        "audit_path": str(audit_file),
        "manifest_path": str(manifest_file),
        "issues": issues,
        "record_count": len(records),
        "manifest_sha256": manifest.get("manifest_sha256"),
        "audit_log_sha256": manifest.get("audit_log_sha256"),
        "append_only_prefix_verified": not any(issue.get("path") == "$.previous_audit_log_sha256" for issue in issues),
        "redacted_records_only": manifest.get("redacted_records_only") is True,
        "raw_payload_storage": manifest.get("raw_payload_storage"),
    }


class LocalDurableAuditStorage:
    """Local append-only durable storage for regular AANA audit records."""

    def __init__(
        self,
        audit_path: str | pathlib.Path = DEFAULT_DURABLE_AUDIT_JSONL,
        manifest_path: str | pathlib.Path = DEFAULT_DURABLE_AUDIT_MANIFEST,
    ) -> None:
        self.audit_path = pathlib.Path(audit_path)
        self.manifest_path = pathlib.Path(manifest_path)

    def append(self, records: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        return append_durable_audit_records(records, audit_path=self.audit_path, manifest_path=self.manifest_path)

    def import_jsonl(self, source_audit_log: str | pathlib.Path) -> dict[str, Any]:
        return import_audit_log_to_durable_storage(source_audit_log, audit_path=self.audit_path, manifest_path=self.manifest_path)

    def verify(self) -> dict[str, Any]:
        return verify_durable_audit_storage(audit_path=self.audit_path, manifest_path=self.manifest_path)

    def config(self) -> dict[str, Any]:
        config = durable_audit_storage_config()
        config["audit_path"] = str(self.audit_path)
        config["manifest_path"] = str(self.manifest_path)
        return config


__all__ = [
    "DEFAULT_DURABLE_AUDIT_CONFIG_PATH",
    "DEFAULT_DURABLE_AUDIT_DIR",
    "DEFAULT_DURABLE_AUDIT_JSONL",
    "DEFAULT_DURABLE_AUDIT_MANIFEST",
    "DURABLE_AUDIT_STORAGE_TYPE",
    "DURABLE_AUDIT_STORAGE_VERSION",
    "LocalDurableAuditStorage",
    "append_durable_audit_records",
    "durable_audit_storage_config",
    "import_audit_log_to_durable_storage",
    "validate_durable_audit_storage_config",
    "verify_durable_audit_storage",
    "write_durable_audit_storage_config",
]
