"""Schema versioning and artifact compatibility policy for MI contracts."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from eval_pipeline.handoff_gate import HANDOFF_CONTRACT_VERSION
from eval_pipeline.mi_audit import MI_AUDIT_RECORD_VERSION
from eval_pipeline.mi_observability import MI_OBSERVABILITY_DASHBOARD_VERSION
from eval_pipeline.mi_pilot import MI_PILOT_VERSION
from eval_pipeline.production_readiness import PRODUCTION_MI_READINESS_VERSION


SCHEMA_VERSIONING_POLICY_VERSION = "0.1"
ACTIVE_INTEROPERABILITY_SCHEMA_VERSION = HANDOFF_CONTRACT_VERSION
ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_VERSIONING_POLICY_PATH = ROOT / "docs" / "schema-versioning-policy.md"
DEFAULT_SCHEMA_VERSIONING_POLICY_JSON_PATH = ROOT / "schemas" / "mi_schema_versioning_policy.json"

COMPATIBILITY_MATRIX = {
    "0.1": {
        "schema": {
            "contract_version": HANDOFF_CONTRACT_VERSION,
            "schema_id_suffix": "interoperability_contract.schema.json",
        },
        "pilot_handoffs": {"field": "contract_version", "compatible_versions": [HANDOFF_CONTRACT_VERSION]},
        "audit_jsonl": {"field": "mi_audit_record_version", "compatible_versions": [MI_AUDIT_RECORD_VERSION]},
        "dashboard": {
            "field": "mi_observability_dashboard_version",
            "compatible_versions": [MI_OBSERVABILITY_DASHBOARD_VERSION],
        },
        "production_readiness": {
            "field": "production_mi_readiness_version",
            "compatible_versions": [PRODUCTION_MI_READINESS_VERSION],
        },
        "mi_pilot": {"field": "mi_pilot_version", "compatible_versions": [MI_PILOT_VERSION]},
    }
}

BREAKING_CHANGE_RULES = [
    "Adding a required top-level field requires a new contract version and migration notes.",
    "Removing, renaming, or changing the meaning of a required field is breaking.",
    "Narrowing an enum, changing decision semantics, or tightening redaction requirements is breaking.",
    "Changing AIx, evidence, audit, dashboard, or readiness version compatibility is breaking for CI artifacts.",
    "Additive optional fields are non-breaking when old readers can ignore them safely.",
]

MIGRATION_NOTES = {
    "0.1": [
        "Initial MI handoff contract for recipient-relative constraint checking.",
        "Pilot handoffs, redacted MI audit records, dashboard payloads, and production readiness payloads are compatible at version 0.1.",
        "Future breaking versions must include a migration path for pilot fixtures, audit JSONL readers, dashboard exporters, and readiness gates.",
    ]
}


def schema_versioning_policy() -> dict[str, Any]:
    """Return the active MI schema versioning policy."""

    return {
        "schema_versioning_policy_version": SCHEMA_VERSIONING_POLICY_VERSION,
        "active_interoperability_schema_version": ACTIVE_INTEROPERABILITY_SCHEMA_VERSION,
        "compatibility_matrix": json.loads(json.dumps(COMPATIBILITY_MATRIX)),
        "breaking_change_rules": list(BREAKING_CHANGE_RULES),
        "migration_notes": json.loads(json.dumps(MIGRATION_NOTES)),
    }


def _issues_for_version(value: Any, versions: list[str], *, path: str, artifact: str) -> list[dict[str, str]]:
    if value in versions:
        return []
    return [
        {
            "artifact": artifact,
            "path": path,
            "message": f"Version {value!r} is not compatible with {ACTIVE_INTEROPERABILITY_SCHEMA_VERSION}.",
        }
    ]


def _schema_contract_version(schema: dict[str, Any]) -> Any:
    version_block = schema.get("properties", {}).get("contract_version", {}) if isinstance(schema, dict) else {}
    return version_block.get("const") if isinstance(version_block, dict) else None


def check_schema_artifact_compatibility(
    *,
    schema: dict[str, Any] | None = None,
    pilot_handoffs: dict[str, Any] | None = None,
    audit_records: list[dict[str, Any]] | None = None,
    dashboard: dict[str, Any] | None = None,
    production_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check schema, pilot, audit, dashboard, and readiness version compatibility."""

    matrix = COMPATIBILITY_MATRIX[ACTIVE_INTEROPERABILITY_SCHEMA_VERSION]
    issues: list[dict[str, str]] = []

    if schema is not None:
        issues.extend(
            _issues_for_version(
                _schema_contract_version(schema),
                [matrix["schema"]["contract_version"]],
                path="$.properties.contract_version.const",
                artifact="schema",
            )
        )

    handoffs = pilot_handoffs.get("handoffs") if isinstance(pilot_handoffs, dict) else None
    if isinstance(handoffs, list):
        versions = matrix["pilot_handoffs"]["compatible_versions"]
        for index, handoff in enumerate(handoffs):
            value = handoff.get("contract_version") if isinstance(handoff, dict) else None
            issues.extend(
                _issues_for_version(value, versions, path=f"$.handoffs[{index}].contract_version", artifact="pilot_handoffs")
            )

    if isinstance(audit_records, list):
        versions = matrix["audit_jsonl"]["compatible_versions"]
        for index, record in enumerate(audit_records):
            value = record.get("mi_audit_record_version") if isinstance(record, dict) else None
            issues.extend(
                _issues_for_version(value, versions, path=f"$[{index}].mi_audit_record_version", artifact="audit_jsonl")
            )

    if isinstance(dashboard, dict):
        issues.extend(
            _issues_for_version(
                dashboard.get("mi_observability_dashboard_version"),
                matrix["dashboard"]["compatible_versions"],
                path="$.mi_observability_dashboard_version",
                artifact="dashboard",
            )
        )

    if isinstance(production_readiness, dict):
        issues.extend(
            _issues_for_version(
                production_readiness.get("production_mi_readiness_version"),
                matrix["production_readiness"]["compatible_versions"],
                path="$.production_mi_readiness_version",
                artifact="production_readiness",
            )
        )

    return {
        "schema_versioning_policy_version": SCHEMA_VERSIONING_POLICY_VERSION,
        "active_interoperability_schema_version": ACTIVE_INTEROPERABILITY_SCHEMA_VERSION,
        "compatible": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "observed_versions": {
            "schema": _schema_contract_version(schema or {}),
            "pilot_handoff_versions": sorted(
                {
                    str(handoff.get("contract_version"))
                    for handoff in (pilot_handoffs or {}).get("handoffs", [])
                    if isinstance(handoff, dict) and handoff.get("contract_version") is not None
                }
            )
            if isinstance(pilot_handoffs, dict)
            else [],
            "audit_record_versions": sorted(
                {
                    str(record.get("mi_audit_record_version"))
                    for record in audit_records or []
                    if isinstance(record, dict) and record.get("mi_audit_record_version") is not None
                }
            ),
            "dashboard": dashboard.get("mi_observability_dashboard_version") if isinstance(dashboard, dict) else None,
            "production_readiness": production_readiness.get("production_mi_readiness_version")
            if isinstance(production_readiness, dict)
            else None,
        },
    }


def schema_versioning_policy_markdown() -> str:
    """Return the MI schema versioning policy as Markdown."""

    rules = "\n".join(f"- {rule}" for rule in BREAKING_CHANGE_RULES)
    notes = "\n".join(f"- {note}" for note in MIGRATION_NOTES[ACTIVE_INTEROPERABILITY_SCHEMA_VERSION])
    return f"""# MI Schema Versioning Policy

Status: milestone 5 schema versioning policy.

Active interoperability contract schema version: `{ACTIVE_INTEROPERABILITY_SCHEMA_VERSION}`.

Policy version: `{SCHEMA_VERSIONING_POLICY_VERSION}`.

## Versioning Rules

`interoperability_contract.schema.json` uses explicit contract versions, currently `contract_version: "0.1"`.

Patch-compatible schema changes may add optional fields, descriptions, examples, or non-required metadata when older readers can ignore the new data without changing gate behavior.

Breaking schema changes require a new contract version, migration notes, updated fixtures, updated validators, and regenerated pilot/dashboard/readiness artifacts before CI can pass.

## Breaking Changes

{rules}

## Compatibility Matrix

| Contract version | Pilot handoffs | Audit JSONL | Dashboard | Production readiness |
| --- | --- | --- | --- | --- |
| `0.1` | `0.1` | `0.1` | `0.1` | `0.1` |

## Migration Notes

{notes}

## CI Enforcement

`scripts/validate_mi_contracts.py` checks that the JSON schema, pilot handoffs, audit JSONL, dashboard payload, and production-readiness payload remain compatible with the active interoperability contract version.
"""


def write_schema_versioning_policy(
    path: str | pathlib.Path = DEFAULT_SCHEMA_VERSIONING_POLICY_PATH,
) -> dict[str, Any]:
    """Write the Markdown schema versioning policy artifact."""

    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(schema_versioning_policy_markdown(), encoding="utf-8")
    return {"path": str(output_path), "bytes": output_path.stat().st_size}


def write_schema_versioning_policy_json(
    path: str | pathlib.Path = DEFAULT_SCHEMA_VERSIONING_POLICY_JSON_PATH,
) -> dict[str, Any]:
    """Write the machine-readable schema versioning policy artifact."""

    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema_versioning_policy(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(output_path), "bytes": output_path.stat().st_size}


__all__ = [
    "ACTIVE_INTEROPERABILITY_SCHEMA_VERSION",
    "BREAKING_CHANGE_RULES",
    "COMPATIBILITY_MATRIX",
    "DEFAULT_SCHEMA_VERSIONING_POLICY_JSON_PATH",
    "DEFAULT_SCHEMA_VERSIONING_POLICY_PATH",
    "MIGRATION_NOTES",
    "SCHEMA_VERSIONING_POLICY_VERSION",
    "check_schema_artifact_compatibility",
    "schema_versioning_policy",
    "schema_versioning_policy_markdown",
    "write_schema_versioning_policy",
    "write_schema_versioning_policy_json",
]
