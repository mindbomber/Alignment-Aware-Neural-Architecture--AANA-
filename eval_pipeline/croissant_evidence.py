"""Croissant metadata importer for AANA evidence registries."""

from __future__ import annotations

import datetime
import json
import pathlib
import re
from typing import Any


CROISSANT_EVIDENCE_IMPORT_VERSION = "0.1"
DEFAULT_CROISSANT_METADATA_PATH = pathlib.Path(__file__).resolve().parents[1] / "examples" / "croissant_metadata_sample.json"
DEFAULT_CROISSANT_EVIDENCE_OUTPUT_PATH = pathlib.Path(__file__).resolve().parents[1] / "eval_outputs" / "croissant" / "evidence-registry.json"
DEFAULT_CROISSANT_IMPORT_REPORT_PATH = pathlib.Path(__file__).resolve().parents[1] / "eval_outputs" / "croissant" / "croissant-evidence-report.json"
SENSITIVE_HINTS = (
    "age",
    "biometric",
    "diagnosis",
    "dob",
    "email",
    "ethnicity",
    "gender",
    "health",
    "income",
    "location",
    "medical",
    "name",
    "patient",
    "phone",
    "race",
    "religion",
    "ssn",
    "zip",
)
NON_SENSITIVE_FIELD_NAMES = {
    "case_id",
    "case_summary",
    "dataset_id",
    "example_id",
    "file_id",
    "id",
    "record_id",
    "row_id",
    "summary",
}


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: str | pathlib.Path) -> dict[str, Any]:
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _write_json(path: str | pathlib.Path, payload: dict[str, Any]) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _coerce_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    return [value]


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ("name", "url", "@id", "identifier", "text"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key].strip()
    return None


def _texts(value: Any) -> list[str]:
    return [text for text in (_text(item) for item in _coerce_list(value)) if text]


def _field_name(field: dict[str, Any]) -> str | None:
    for key in ("name", "source", "id", "@id"):
        value = field.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _find_fields(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    fields = []
    for record_set in _coerce_list(metadata.get("recordSet")):
        if not isinstance(record_set, dict):
            continue
        for field in _coerce_list(record_set.get("field")):
            if isinstance(field, dict):
                fields.append(field)
    return fields


def _sensitive_fields(metadata: dict[str, Any]) -> list[str]:
    explicit = []
    for key in ("dataSensitivity", "sensitiveFields", "rai:dataSensitivity", "rai:sensitiveFields"):
        explicit.extend(_texts(metadata.get(key)))
    fields = []
    for field in _find_fields(metadata):
        name = _field_name(field)
        if not name:
            continue
        if name.lower() in NON_SENSITIVE_FIELD_NAMES:
            continue
        field_text = json.dumps(field, sort_keys=True).lower()
        if any(hint in field_text or re.search(rf"(^|[_\-\s]){re.escape(hint)}($|[_\-\s])", name.lower()) for hint in SENSITIVE_HINTS):
            fields.append(name)
    return sorted(set(explicit + fields))


def _distribution_ids(metadata: dict[str, Any]) -> list[str]:
    ids = []
    for item in _coerce_list(metadata.get("distribution")):
        if not isinstance(item, dict):
            text = _text(item)
            if text:
                ids.append(text)
            continue
        ids.append(_text(item) or item.get("@type") or "distribution")
    return sorted(set(str(item) for item in ids if item))


def _dataset_name(metadata: dict[str, Any]) -> str:
    return _text(metadata.get("name")) or _text(metadata.get("@id")) or "croissant_dataset"


def _source_id(metadata: dict[str, Any]) -> str:
    base = _dataset_name(metadata).lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-") or "dataset"
    version = _text(metadata.get("version"))
    if version:
        version_slug = re.sub(r"[^a-z0-9]+", "-", version.lower()).strip("-")
        if version_slug:
            base = f"{base}-{version_slug}"
    return f"croissant-{base}"


def _gap_report(metadata: dict[str, Any], sensitive_fields: list[str]) -> dict[str, Any]:
    gaps = []
    if not _text(metadata.get("name")):
        gaps.append({"level": "error", "field": "name", "message": "Croissant metadata should declare dataset name."})
    if not _texts(metadata.get("creator")):
        gaps.append({"level": "error", "field": "creator", "message": "Dataset creator is required for provenance."})
    if not (_texts(metadata.get("license")) or _texts(metadata.get("sdLicense"))):
        gaps.append({"level": "error", "field": "license", "message": "Dataset license or sdLicense is required for regulated audit."})
    if not _texts(metadata.get("citeAs")):
        gaps.append({"level": "warning", "field": "citeAs", "message": "Citation is recommended for audit traceability."})
    if not _coerce_list(metadata.get("distribution")):
        gaps.append({"level": "error", "field": "distribution", "message": "Dataset distribution files are required for reproducibility."})
    if not (_text(metadata.get("description")) or _text(metadata.get("intendedUse")) or _text(metadata.get("rai:intendedUse"))):
        gaps.append({"level": "warning", "field": "intendedUse", "message": "Intended use or description should be declared."})
    if sensitive_fields and not (_text(metadata.get("privacyPolicy")) or _text(metadata.get("rai:privacyPolicy"))):
        gaps.append({"level": "warning", "field": "privacyPolicy", "message": "Sensitive fields were detected; privacy policy metadata is recommended."})
    errors = sum(1 for gap in gaps if gap["level"] == "error")
    warnings = sum(1 for gap in gaps if gap["level"] == "warning")
    return {"valid": errors == 0, "errors": errors, "warnings": warnings, "gaps": gaps}


def croissant_metadata_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    sensitive_fields = _sensitive_fields(metadata)
    return {
        "name": _dataset_name(metadata),
        "source_id": _source_id(metadata),
        "url": _text(metadata.get("url")),
        "version": _text(metadata.get("version")),
        "creators": _texts(metadata.get("creator")),
        "publishers": _texts(metadata.get("publisher")),
        "licenses": _texts(metadata.get("license")) or _texts(metadata.get("sdLicense")),
        "cite_as": _texts(metadata.get("citeAs")),
        "intended_use": _text(metadata.get("intendedUse")) or _text(metadata.get("rai:intendedUse")) or _text(metadata.get("description")),
        "sensitive_fields": sensitive_fields,
        "distribution": _distribution_ids(metadata),
        "record_set_count": len(_coerce_list(metadata.get("recordSet"))),
        "field_count": len(_find_fields(metadata)),
        "conforms_to": _texts(metadata.get("conformsTo")) or _texts(metadata.get("dct:conformsTo")),
        "gap_report": _gap_report(metadata, sensitive_fields),
    }


def croissant_to_evidence_source(metadata: dict[str, Any]) -> dict[str, Any]:
    summary = croissant_metadata_summary(metadata)
    source = {
        "source_id": summary["source_id"],
        "owner": ", ".join(summary["creators"] or summary["publishers"] or ["Dataset Governance"]),
        "enabled": summary["gap_report"]["errors"] == 0,
        "allowed_trust_tiers": ["verified", "approved_fixture", "repository_fixture"],
        "allowed_redaction_statuses": ["redacted", "public", "synthetic"],
        "max_age_hours": None,
        "metadata": {
            "source_type": "croissant_dataset",
            "dataset_name": summary["name"],
            "dataset_url": summary["url"],
            "dataset_version": summary["version"],
            "licenses": summary["licenses"],
            "cite_as": summary["cite_as"],
            "intended_use": summary["intended_use"],
            "sensitive_fields": summary["sensitive_fields"],
            "distribution": summary["distribution"],
            "record_set_count": summary["record_set_count"],
            "field_count": summary["field_count"],
            "conforms_to": summary["conforms_to"],
        },
    }
    return source


def croissant_to_evidence_registry(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "registry_version": "0.1",
        "sources": [croissant_to_evidence_source(metadata)],
    }


def import_croissant_evidence(
    *,
    metadata_path: str | pathlib.Path = DEFAULT_CROISSANT_METADATA_PATH,
    output_registry: str | pathlib.Path = DEFAULT_CROISSANT_EVIDENCE_OUTPUT_PATH,
    report_path: str | pathlib.Path = DEFAULT_CROISSANT_IMPORT_REPORT_PATH,
) -> dict[str, Any]:
    metadata = _load_json(metadata_path)
    summary = croissant_metadata_summary(metadata)
    registry = croissant_to_evidence_registry(metadata)
    report = {
        "croissant_evidence_import_version": CROISSANT_EVIDENCE_IMPORT_VERSION,
        "created_at": _utc_now(),
        "metadata_path": str(metadata_path),
        "output_registry": str(output_registry),
        "report_path": str(report_path),
        "valid": summary["gap_report"]["valid"],
        "summary": summary,
        "registry": registry,
        "gap_report": summary["gap_report"],
        "claim_boundary": "Croissant metadata supports dataset provenance evidence; it does not certify dataset quality, legal compliance, or production readiness by itself.",
    }
    _write_json(output_registry, registry)
    _write_json(report_path, report)
    return report


__all__ = [
    "CROISSANT_EVIDENCE_IMPORT_VERSION",
    "DEFAULT_CROISSANT_EVIDENCE_OUTPUT_PATH",
    "DEFAULT_CROISSANT_IMPORT_REPORT_PATH",
    "DEFAULT_CROISSANT_METADATA_PATH",
    "croissant_metadata_summary",
    "croissant_to_evidence_registry",
    "croissant_to_evidence_source",
    "import_croissant_evidence",
]
