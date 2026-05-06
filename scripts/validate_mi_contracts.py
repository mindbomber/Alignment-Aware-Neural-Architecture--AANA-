"""Validate Mechanistic Interoperability contract artifacts for CI."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

from eval_pipeline.mi_audit import load_mi_audit_jsonl, validate_mi_audit_records
from eval_pipeline.mi_audit_integrity import verify_mi_audit_integrity
from eval_pipeline.mi_observability import MI_OBSERVABILITY_DASHBOARD_VERSION
from eval_pipeline.production_readiness import PRODUCTION_MI_READINESS_VERSION
from eval_pipeline.schema_versioning_policy import (
    DEFAULT_SCHEMA_VERSIONING_POLICY_JSON_PATH,
    SCHEMA_VERSIONING_POLICY_VERSION,
    check_schema_artifact_compatibility,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "interoperability_contract.schema.json"
DEFAULT_PILOT_HANDOFFS = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "pilot_handoffs.json"
DEFAULT_AUDIT_JSONL = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_audit.jsonl"
DEFAULT_AUDIT_MANIFEST = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_audit.jsonl.sha256.json"
DEFAULT_DASHBOARD = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_dashboard.json"
DEFAULT_READINESS = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "production_mi_readiness.json"
DEFAULT_VERSIONING_POLICY = DEFAULT_SCHEMA_VERSIONING_POLICY_JSON_PATH


@dataclass(frozen=True)
class ValidationIssue:
    artifact: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"artifact": self.artifact, "path": self.path, "message": self.message}


def _json_path(parts: Any) -> str:
    values = list(parts)
    if not values:
        return "$"
    path = "$"
    for part in values:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


def _load_json(path: pathlib.Path) -> tuple[Any | None, list[ValidationIssue]]:
    if not path.exists():
        return None, [ValidationIssue(str(path), "$", "File does not exist.")]
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle), []
    except json.JSONDecodeError as exc:
        return None, [ValidationIssue(str(path), "$", f"Invalid JSON: {exc}")]


def _require_object(value: Any, *, artifact: pathlib.Path) -> list[ValidationIssue]:
    if isinstance(value, dict):
        return []
    return [ValidationIssue(str(artifact), "$", "Artifact must be a JSON object.")]


def validate_schema(schema_path: str | pathlib.Path = DEFAULT_SCHEMA) -> tuple[dict[str, Any] | None, list[ValidationIssue]]:
    path = pathlib.Path(schema_path)
    schema, issues = _load_json(path)
    if issues:
        return None, issues
    if not isinstance(schema, dict):
        return None, [ValidationIssue(str(path), "$", "Schema must be a JSON object.")]
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return schema, [ValidationIssue(str(path), "$", f"Invalid JSON Schema: {exc}")]
    return schema, []


def validate_pilot_handoffs(
    schema: dict[str, Any],
    handoffs_path: str | pathlib.Path = DEFAULT_PILOT_HANDOFFS,
) -> list[ValidationIssue]:
    path = pathlib.Path(handoffs_path)
    payload, issues = _load_json(path)
    if issues:
        return issues
    issues = _require_object(payload, artifact=path)
    if issues:
        return issues

    handoffs = payload.get("handoffs")
    if not isinstance(handoffs, list) or not handoffs:
        return [ValidationIssue(str(path), "$.handoffs", "Pilot handoffs artifact must contain a non-empty handoffs array.")]

    validator = Draft202012Validator(schema)
    for index, handoff in enumerate(handoffs):
        if not isinstance(handoff, dict):
            issues.append(ValidationIssue(str(path), f"$.handoffs[{index}]", "Handoff must be an object."))
            continue
        for error in sorted(validator.iter_errors(handoff), key=lambda item: list(item.path)):
            issues.append(ValidationIssue(str(path), f"$.handoffs[{index}]{_json_path(error.path)[1:]}", error.message))
    return issues


def validate_audit_jsonl(audit_path: str | pathlib.Path = DEFAULT_AUDIT_JSONL) -> list[ValidationIssue]:
    path = pathlib.Path(audit_path)
    if not path.exists():
        return [ValidationIssue(str(path), "$", "File does not exist.")]
    try:
        records = load_mi_audit_jsonl(path)
    except ValueError as exc:
        return [ValidationIssue(str(path), "$", str(exc))]
    report = validate_mi_audit_records(records)
    issues = [
        ValidationIssue(str(path), issue.get("path", "$"), issue.get("message", "Invalid MI audit record."))
        for issue in report.get("issues", [])
    ]
    if report.get("record_count", 0) <= 0:
        issues.append(ValidationIssue(str(path), "$", "MI audit JSONL must contain at least one record."))
    return issues


def validate_audit_integrity_manifest(
    audit_path: str | pathlib.Path = DEFAULT_AUDIT_JSONL,
    manifest_path: str | pathlib.Path = DEFAULT_AUDIT_MANIFEST,
) -> list[ValidationIssue]:
    path = pathlib.Path(manifest_path)
    if not path.exists():
        return [ValidationIssue(str(path), "$", "File does not exist.")]
    try:
        report = verify_mi_audit_integrity(audit_path, path)
    except (OSError, ValueError) as exc:
        return [ValidationIssue(str(path), "$", str(exc))]
    return [
        ValidationIssue(str(path), issue.get("path", "$"), issue.get("message", "MI audit integrity failed."))
        for issue in report.get("issues", [])
    ]


def validate_dashboard(dashboard_path: str | pathlib.Path = DEFAULT_DASHBOARD) -> list[ValidationIssue]:
    path = pathlib.Path(dashboard_path)
    dashboard, issues = _load_json(path)
    if issues:
        return issues
    issues = _require_object(dashboard, artifact=path)
    if issues:
        return issues

    if dashboard.get("mi_observability_dashboard_version") != MI_OBSERVABILITY_DASHBOARD_VERSION:
        issues.append(
            ValidationIssue(
                str(path),
                "$.mi_observability_dashboard_version",
                f"Must be {MI_OBSERVABILITY_DASHBOARD_VERSION}.",
            )
        )
    for field in ("source", "metrics", "panels", "workflow_rows"):
        if field not in dashboard:
            issues.append(ValidationIssue(str(path), f"$.{field}", "Required dashboard field is missing."))
    if not isinstance(dashboard.get("metrics"), dict):
        issues.append(ValidationIssue(str(path), "$.metrics", "Dashboard metrics must be an object."))
    if not isinstance(dashboard.get("panels"), dict):
        issues.append(ValidationIssue(str(path), "$.panels", "Dashboard panels must be an object."))
    if not isinstance(dashboard.get("workflow_rows"), list):
        issues.append(ValidationIssue(str(path), "$.workflow_rows", "Dashboard workflow_rows must be an array."))

    metrics = dashboard.get("metrics") if isinstance(dashboard.get("metrics"), dict) else {}
    for metric in (
        "workflow_count",
        "handoff_count",
        "handoff_pass_rate",
        "handoff_fail_rate",
        "propagated_error_rate",
        "correction_success_rate",
        "false_accept_rate",
        "false_refusal_rate",
        "global_aix_drift_max_drop",
    ):
        if not isinstance(metrics.get(metric), (int, float)):
            issues.append(ValidationIssue(str(path), f"$.metrics.{metric}", "Required metric must be numeric."))
    return issues


def validate_production_readiness(readiness_path: str | pathlib.Path = DEFAULT_READINESS) -> list[ValidationIssue]:
    path = pathlib.Path(readiness_path)
    readiness, issues = _load_json(path)
    if issues:
        return issues
    issues = _require_object(readiness, artifact=path)
    if issues:
        return issues

    if readiness.get("production_mi_readiness_version") != PRODUCTION_MI_READINESS_VERSION:
        issues.append(
            ValidationIssue(
                str(path),
                "$.production_mi_readiness_version",
                f"Must be {PRODUCTION_MI_READINESS_VERSION}.",
            )
        )
    if readiness.get("gate") != "production_mi_readiness":
        issues.append(ValidationIssue(str(path), "$.gate", "Must be production_mi_readiness."))
    if readiness.get("release_status") not in {"ready", "blocked"}:
        issues.append(ValidationIssue(str(path), "$.release_status", "Must be ready or blocked."))
    if readiness.get("recommended_action") not in {"accept", "revise", "retrieve", "ask", "defer", "refuse"}:
        issues.append(ValidationIssue(str(path), "$.recommended_action", "Must be a supported AANA route."))
    if not isinstance(readiness.get("can_execute_directly"), bool):
        issues.append(ValidationIssue(str(path), "$.can_execute_directly", "Must be a boolean."))
    if not isinstance(readiness.get("checklist"), list) or not readiness.get("checklist"):
        issues.append(ValidationIssue(str(path), "$.checklist", "Checklist must be a non-empty array."))
    if not isinstance(readiness.get("blockers"), list):
        issues.append(ValidationIssue(str(path), "$.blockers", "Blockers must be an array."))
    if not isinstance(readiness.get("global_aix"), dict):
        issues.append(ValidationIssue(str(path), "$.global_aix", "Global AIx summary must be an object."))
    if not isinstance(readiness.get("propagated_risk"), dict):
        issues.append(ValidationIssue(str(path), "$.propagated_risk", "Propagated risk summary must be an object."))

    checklist = readiness.get("checklist") if isinstance(readiness.get("checklist"), list) else []
    for index, item in enumerate(checklist):
        if not isinstance(item, dict):
            issues.append(ValidationIssue(str(path), f"$.checklist[{index}]", "Checklist item must be an object."))
            continue
        if item.get("status") not in {"pass", "block"}:
            issues.append(ValidationIssue(str(path), f"$.checklist[{index}].status", "Must be pass or block."))
        for field in ("id", "label", "details"):
            if not isinstance(item.get(field), str) or not item.get(field).strip():
                issues.append(ValidationIssue(str(path), f"$.checklist[{index}].{field}", "Must be a non-empty string."))

    blockers = readiness.get("blockers") if isinstance(readiness.get("blockers"), list) else []
    release_status = readiness.get("release_status")
    can_execute = readiness.get("can_execute_directly")
    if release_status == "ready" and blockers:
        issues.append(ValidationIssue(str(path), "$.blockers", "Ready readiness result cannot contain blockers."))
    if release_status == "ready" and can_execute is not True:
        issues.append(ValidationIssue(str(path), "$.can_execute_directly", "Ready readiness result must allow direct execution."))
    if release_status == "blocked" and can_execute is True:
        issues.append(ValidationIssue(str(path), "$.can_execute_directly", "Blocked readiness result cannot allow direct execution."))
    return issues


def validate_schema_versioning_policy(
    policy_path: str | pathlib.Path = DEFAULT_VERSIONING_POLICY,
) -> list[ValidationIssue]:
    path = pathlib.Path(policy_path)
    policy, issues = _load_json(path)
    if issues:
        return issues
    issues = _require_object(policy, artifact=path)
    if issues:
        return issues

    if policy.get("schema_versioning_policy_version") != SCHEMA_VERSIONING_POLICY_VERSION:
        issues.append(
            ValidationIssue(
                str(path),
                "$.schema_versioning_policy_version",
                f"Must be {SCHEMA_VERSIONING_POLICY_VERSION}.",
            )
        )
    if not isinstance(policy.get("active_interoperability_schema_version"), str):
        issues.append(ValidationIssue(str(path), "$.active_interoperability_schema_version", "Must be a string."))
    if not isinstance(policy.get("compatibility_matrix"), dict) or not policy.get("compatibility_matrix"):
        issues.append(ValidationIssue(str(path), "$.compatibility_matrix", "Must be a non-empty object."))
    if not isinstance(policy.get("breaking_change_rules"), list) or not policy.get("breaking_change_rules"):
        issues.append(ValidationIssue(str(path), "$.breaking_change_rules", "Must be a non-empty array."))
    if not isinstance(policy.get("migration_notes"), dict) or not policy.get("migration_notes"):
        issues.append(ValidationIssue(str(path), "$.migration_notes", "Must be a non-empty object."))
    return issues


def validate_schema_artifact_compatibility(
    schema: dict[str, Any],
    *,
    handoffs_path: str | pathlib.Path = DEFAULT_PILOT_HANDOFFS,
    audit_path: str | pathlib.Path = DEFAULT_AUDIT_JSONL,
    audit_manifest_path: str | pathlib.Path = DEFAULT_AUDIT_MANIFEST,
    dashboard_path: str | pathlib.Path = DEFAULT_DASHBOARD,
    readiness_path: str | pathlib.Path = DEFAULT_READINESS,
) -> list[ValidationIssue]:
    pilot_handoffs, handoff_issues = _load_json(pathlib.Path(handoffs_path))
    dashboard, dashboard_issues = _load_json(pathlib.Path(dashboard_path))
    readiness, readiness_issues = _load_json(pathlib.Path(readiness_path))
    issues = [*handoff_issues, *dashboard_issues, *readiness_issues]

    try:
        audit_records = load_mi_audit_jsonl(pathlib.Path(audit_path))
    except ValueError as exc:
        issues.append(ValidationIssue(str(audit_path), "$", str(exc)))
        audit_records = []

    if issues:
        return issues

    report = check_schema_artifact_compatibility(
        schema=schema,
        pilot_handoffs=pilot_handoffs if isinstance(pilot_handoffs, dict) else None,
        audit_records=audit_records,
        dashboard=dashboard if isinstance(dashboard, dict) else None,
        production_readiness=readiness if isinstance(readiness, dict) else None,
    )
    return [
        ValidationIssue(issue["artifact"], issue["path"], issue["message"])
        for issue in report.get("issues", [])
        if isinstance(issue, dict)
    ]


def validate_mi_contracts(
    *,
    schema_path: str | pathlib.Path = DEFAULT_SCHEMA,
    handoffs_path: str | pathlib.Path = DEFAULT_PILOT_HANDOFFS,
    audit_path: str | pathlib.Path = DEFAULT_AUDIT_JSONL,
    audit_manifest_path: str | pathlib.Path = DEFAULT_AUDIT_MANIFEST,
    dashboard_path: str | pathlib.Path = DEFAULT_DASHBOARD,
    readiness_path: str | pathlib.Path = DEFAULT_READINESS,
    versioning_policy_path: str | pathlib.Path = DEFAULT_VERSIONING_POLICY,
) -> dict[str, Any]:
    schema, issues = validate_schema(schema_path)
    if schema is not None:
        issues.extend(validate_pilot_handoffs(schema, handoffs_path))
        issues.extend(
            validate_schema_artifact_compatibility(
                schema,
                handoffs_path=handoffs_path,
                audit_path=audit_path,
                dashboard_path=dashboard_path,
                readiness_path=readiness_path,
            )
        )
    issues.extend(validate_audit_jsonl(audit_path))
    issues.extend(validate_audit_integrity_manifest(audit_path, audit_manifest_path))
    issues.extend(validate_dashboard(dashboard_path))
    issues.extend(validate_production_readiness(readiness_path))
    issues.extend(validate_schema_versioning_policy(versioning_policy_path))

    return {
        "valid": not issues,
        "issue_count": len(issues),
        "issues": [issue.to_dict() for issue in issues],
        "artifacts": {
            "schema": str(pathlib.Path(schema_path)),
            "pilot_handoffs": str(pathlib.Path(handoffs_path)),
            "audit_jsonl": str(pathlib.Path(audit_path)),
            "audit_manifest": str(pathlib.Path(audit_manifest_path)),
            "dashboard": str(pathlib.Path(dashboard_path)),
            "production_readiness": str(pathlib.Path(readiness_path)),
            "versioning_policy": str(pathlib.Path(versioning_policy_path)),
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate AANA MI contract artifacts for CI.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Path to interoperability_contract.schema.json.")
    parser.add_argument("--pilot-handoffs", default=str(DEFAULT_PILOT_HANDOFFS), help="Path to pilot_handoffs.json.")
    parser.add_argument("--audit-jsonl", default=str(DEFAULT_AUDIT_JSONL), help="Path to mi_audit.jsonl.")
    parser.add_argument("--audit-manifest", default=str(DEFAULT_AUDIT_MANIFEST), help="Path to mi_audit.jsonl.sha256.json.")
    parser.add_argument("--dashboard", default=str(DEFAULT_DASHBOARD), help="Path to mi_dashboard.json.")
    parser.add_argument("--production-readiness", default=str(DEFAULT_READINESS), help="Path to production_mi_readiness.json.")
    parser.add_argument("--versioning-policy", default=str(DEFAULT_VERSIONING_POLICY), help="Path to MI schema versioning policy JSON.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = validate_mi_contracts(
        schema_path=args.schema,
        handoffs_path=args.pilot_handoffs,
        audit_path=args.audit_jsonl,
        audit_manifest_path=args.audit_manifest,
        dashboard_path=args.dashboard,
        readiness_path=args.production_readiness,
        versioning_policy_path=args.versioning_policy,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["valid"]:
        print("ok -- MI contract validation passed")
    else:
        print(f"MI contract validation failed with {report['issue_count']} issue(s):", file=sys.stderr)
        for issue in report["issues"]:
            print(f"- {issue['artifact']}::{issue['path']}: {issue['message']}", file=sys.stderr)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
