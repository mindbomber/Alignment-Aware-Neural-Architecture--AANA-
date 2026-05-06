"""Immutable audit storage adapter stub for MI audit records."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from eval_pipeline.mi_audit import append_mi_audit_jsonl, validate_mi_audit_records
from eval_pipeline.mi_audit_integrity import (
    load_mi_audit_integrity_manifest,
    validate_append_only_audit,
    verify_mi_audit_integrity,
    write_mi_audit_integrity_manifest,
)


IMMUTABLE_AUDIT_STORAGE_VERSION = "0.1"
DEFAULT_IMMUTABLE_AUDIT_DIR = pathlib.Path(__file__).resolve().parents[1] / "eval_outputs" / "immutable_audit_storage"
DEFAULT_IMMUTABLE_AUDIT_JSONL = DEFAULT_IMMUTABLE_AUDIT_DIR / "mi_audit.jsonl"
DEFAULT_IMMUTABLE_AUDIT_MANIFEST = DEFAULT_IMMUTABLE_AUDIT_JSONL.with_suffix(
    DEFAULT_IMMUTABLE_AUDIT_JSONL.suffix + ".sha256.json"
)


def immutable_audit_storage_contract() -> dict[str, Any]:
    """Return the future immutable audit storage interface contract."""

    return {
        "immutable_audit_storage_version": IMMUTABLE_AUDIT_STORAGE_VERSION,
        "interface": "ImmutableAuditStorage",
        "storage_modes": ["local_append_only_stub", "remote_append_only_future"],
        "current_mode": "local_append_only_stub",
        "remote_storage_enabled": False,
        "production_boundary": {
            "status": "not_configured",
            "required_before_live_production": True,
            "required_capabilities": [
                "append_only_writes",
                "tamper_evident_hash_chain",
                "server_side_timestamps",
                "retention_policy",
                "access_control",
                "replication_or_backup",
                "incident_export",
            ],
        },
        "methods": {
            "append(records)": "Append redacted MI audit records and return a storage receipt.",
            "verify()": "Verify the current audit JSONL against the latest manifest.",
            "contract()": "Return the storage mode, boundary, and capability contract.",
        },
    }


def _fingerprints(records: list[dict[str, Any]]) -> list[str]:
    return [str(record.get("record_fingerprint")) for record in records if record.get("record_fingerprint")]


def _load_previous_manifest(path: pathlib.Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return load_mi_audit_integrity_manifest(path)


def _verify_current_if_manifest_exists(audit_path: pathlib.Path, manifest_path: pathlib.Path) -> None:
    if not audit_path.exists() or not manifest_path.exists():
        return
    report = verify_mi_audit_integrity(audit_path, manifest_path)
    if not report.get("valid"):
        raise ValueError("Immutable audit storage cannot append to tampered audit log.")


def append_immutable_audit_records(
    records: dict[str, Any] | list[dict[str, Any]],
    *,
    audit_path: str | pathlib.Path = DEFAULT_IMMUTABLE_AUDIT_JSONL,
    manifest_path: str | pathlib.Path = DEFAULT_IMMUTABLE_AUDIT_MANIFEST,
) -> dict[str, Any]:
    """Append redacted audit records to the local append-only storage stub."""

    rows = records if isinstance(records, list) else [records]
    rows = [row for row in rows if isinstance(row, dict)]
    validation = validate_mi_audit_records(rows)
    if not validation.get("valid"):
        raise ValueError("Immutable audit storage only accepts valid redacted MI audit records.")

    audit = pathlib.Path(audit_path)
    manifest = pathlib.Path(manifest_path)
    previous_manifest = _load_previous_manifest(manifest)
    _verify_current_if_manifest_exists(audit, manifest)
    append_mi_audit_jsonl(audit, rows)
    current = write_mi_audit_integrity_manifest(audit, manifest)["manifest"]
    append_only = {"valid": True, "append_only": True, "issues": []}
    if previous_manifest is not None:
        append_only = validate_append_only_audit(previous_manifest, audit)
        if not append_only.get("append_only"):
            raise ValueError("Immutable audit storage append-only validation failed.")

    return {
        "immutable_audit_storage_version": IMMUTABLE_AUDIT_STORAGE_VERSION,
        "storage_mode": "local_append_only_stub",
        "remote_storage_enabled": False,
        "audit_path": str(audit),
        "manifest_path": str(manifest),
        "record_count": len(rows),
        "record_fingerprints": _fingerprints(rows),
        "append_only": bool(append_only.get("append_only")),
        "line_count": current.get("line_count"),
        "final_chain_sha256": current.get("final_chain_sha256"),
        "production_boundary": immutable_audit_storage_contract()["production_boundary"],
    }


def verify_immutable_audit_storage(
    *,
    audit_path: str | pathlib.Path = DEFAULT_IMMUTABLE_AUDIT_JSONL,
    manifest_path: str | pathlib.Path = DEFAULT_IMMUTABLE_AUDIT_MANIFEST,
) -> dict[str, Any]:
    """Verify the local immutable audit storage stub against its manifest."""

    audit = pathlib.Path(audit_path)
    manifest = pathlib.Path(manifest_path)
    if not audit.exists() or not manifest.exists():
        return {
            "immutable_audit_storage_version": IMMUTABLE_AUDIT_STORAGE_VERSION,
            "valid": False,
            "storage_mode": "local_append_only_stub",
            "audit_path": str(audit),
            "manifest_path": str(manifest),
            "issues": [{"path": "$", "message": "Audit JSONL and manifest must both exist."}],
        }
    report = verify_mi_audit_integrity(audit, manifest)
    return {
        "immutable_audit_storage_version": IMMUTABLE_AUDIT_STORAGE_VERSION,
        "valid": bool(report.get("valid")),
        "storage_mode": "local_append_only_stub",
        "audit_path": str(audit),
        "manifest_path": str(manifest),
        "issues": report.get("issues", []),
        "line_count": report.get("current", {}).get("line_count") if isinstance(report.get("current"), dict) else None,
        "final_chain_sha256": report.get("current", {}).get("final_chain_sha256")
        if isinstance(report.get("current"), dict)
        else None,
        "production_boundary": immutable_audit_storage_contract()["production_boundary"],
    }


class LocalImmutableAuditStorage:
    """Local append-only immutable audit storage stub.

    This class intentionally does not implement remote storage. It provides the
    stable interface that a future remote/immutable backend must satisfy.
    """

    def __init__(
        self,
        audit_path: str | pathlib.Path = DEFAULT_IMMUTABLE_AUDIT_JSONL,
        manifest_path: str | pathlib.Path = DEFAULT_IMMUTABLE_AUDIT_MANIFEST,
    ) -> None:
        self.audit_path = pathlib.Path(audit_path)
        self.manifest_path = pathlib.Path(manifest_path)

    def contract(self) -> dict[str, Any]:
        return immutable_audit_storage_contract()

    def append(self, records: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        return append_immutable_audit_records(
            records,
            audit_path=self.audit_path,
            manifest_path=self.manifest_path,
        )

    def verify(self) -> dict[str, Any]:
        return verify_immutable_audit_storage(audit_path=self.audit_path, manifest_path=self.manifest_path)


def write_immutable_audit_storage_contract(path: str | pathlib.Path) -> dict[str, Any]:
    """Write the immutable audit storage contract JSON artifact."""

    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    contract = immutable_audit_storage_contract()
    output.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(output), "bytes": output.stat().st_size, "contract": contract}


__all__ = [
    "DEFAULT_IMMUTABLE_AUDIT_DIR",
    "DEFAULT_IMMUTABLE_AUDIT_JSONL",
    "DEFAULT_IMMUTABLE_AUDIT_MANIFEST",
    "IMMUTABLE_AUDIT_STORAGE_VERSION",
    "LocalImmutableAuditStorage",
    "append_immutable_audit_records",
    "immutable_audit_storage_contract",
    "verify_immutable_audit_storage",
    "write_immutable_audit_storage_contract",
]
