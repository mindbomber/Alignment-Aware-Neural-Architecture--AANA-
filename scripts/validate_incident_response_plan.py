#!/usr/bin/env python3
"""Validate the AANA support incident response plan."""

from __future__ import annotations

import argparse
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "examples" / "incident_response_plan_internal_pilot.json"
REQUIRED_TOP_LEVEL = {
    "plan_version",
    "plan_id",
    "scope",
    "owners",
    "severity_levels",
    "rollback_triggers",
    "notification_paths",
    "audit_review_procedure",
    "customer_impact_review",
    "release_gate",
}
REQUIRED_OWNER_FIELDS = {
    "incident_commander",
    "support_owner",
    "security_owner",
    "privacy_owner",
    "audit_owner",
    "customer_impact_owner",
}
REQUIRED_SEVERITIES = {"sev0", "sev1", "sev2", "sev3"}
REQUIRED_ROLLBACK_TRIGGERS = {
    "critical_false_accept",
    "audit_leakage",
    "auth_or_connector_permission_incident",
    "bridge_unavailable_irreversible_actions",
    "sustained_quality_regression",
}


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _has_text(value):
    return isinstance(value, str) and bool(value.strip())


def _is_placeholder(value):
    return isinstance(value, str) and "replace" in value.lower()


def _add(errors, message):
    errors.append(message)


def validate_plan(path=DEFAULT_PLAN):
    plan_path = pathlib.Path(path)
    payload = _load_json(plan_path)
    errors = []

    missing = sorted(REQUIRED_TOP_LEVEL - set(payload))
    if missing:
        _add(errors, f"missing top-level fields: {', '.join(missing)}")

    scope = payload.get("scope", {})
    if not isinstance(scope, dict):
        _add(errors, "scope must be an object.")
    else:
        if scope.get("production_position") != "pilot-ready/production-candidate; not production-certified by local tests alone":
            _add(errors, "scope.production_position must remain conservative.")
        if not isinstance(scope.get("adapters"), list) or not scope.get("adapters"):
            _add(errors, "scope.adapters must be a non-empty list.")

    owners = payload.get("owners", {})
    if not isinstance(owners, dict):
        _add(errors, "owners must be an object.")
    else:
        for field in sorted(REQUIRED_OWNER_FIELDS):
            value = owners.get(field)
            if not _has_text(value) or _is_placeholder(value):
                _add(errors, f"owners.{field} must be concrete.")

    severity_levels = payload.get("severity_levels", [])
    severity_ids = {item.get("id") for item in severity_levels if isinstance(item, dict)}
    missing_severities = sorted(REQUIRED_SEVERITIES - severity_ids)
    if missing_severities:
        _add(errors, f"missing severity levels: {', '.join(missing_severities)}")
    for item in severity_levels:
        if not isinstance(item, dict):
            _add(errors, "severity level must be an object.")
            continue
        severity_id = item.get("id", "<missing>")
        for field in ("name", "definition"):
            if not _has_text(item.get(field)):
                _add(errors, f"{severity_id}: {field} must be non-empty.")
        if not isinstance(item.get("response_sla_minutes"), int) or item.get("response_sla_minutes") <= 0:
            _add(errors, f"{severity_id}: response_sla_minutes must be a positive integer.")
        for field in ("rollback_required", "customer_impact_review_required", "audit_review_required"):
            if field not in item or not isinstance(item.get(field), bool):
                _add(errors, f"{severity_id}: {field} must be boolean.")

    rollback_triggers = payload.get("rollback_triggers", [])
    trigger_ids = {item.get("id") for item in rollback_triggers if isinstance(item, dict)}
    missing_triggers = sorted(REQUIRED_ROLLBACK_TRIGGERS - trigger_ids)
    if missing_triggers:
        _add(errors, f"missing rollback triggers: {', '.join(missing_triggers)}")
    for item in rollback_triggers:
        if not isinstance(item, dict):
            _add(errors, "rollback trigger must be an object.")
            continue
        trigger_id = item.get("id", "<missing>")
        if item.get("severity") not in REQUIRED_SEVERITIES:
            _add(errors, f"{trigger_id}: severity must reference a declared severity.")
        for field in ("condition", "action"):
            if not _has_text(item.get(field)):
                _add(errors, f"{trigger_id}: {field} must be non-empty.")

    notification_paths = payload.get("notification_paths", [])
    if not isinstance(notification_paths, list) or not notification_paths:
        _add(errors, "notification_paths must be a non-empty list.")
    else:
        covered = set()
        for item in notification_paths:
            if not isinstance(item, dict):
                _add(errors, "notification path must be an object.")
                continue
            path_id = item.get("id", "<missing>")
            for field in ("owner", "channel"):
                value = item.get(field)
                if not _has_text(value) or _is_placeholder(value):
                    _add(errors, f"{path_id}: {field} must be concrete.")
            severities = item.get("severities")
            if not isinstance(severities, list) or not severities:
                _add(errors, f"{path_id}: severities must be a non-empty list.")
            else:
                covered.update(severities)
            if not isinstance(item.get("notify_within_minutes"), int) or item.get("notify_within_minutes") <= 0:
                _add(errors, f"{path_id}: notify_within_minutes must be a positive integer.")
        for severity in ("sev0", "sev1", "sev2"):
            if severity not in covered:
                _add(errors, f"notification_paths must cover {severity}.")

    audit_review = payload.get("audit_review_procedure", {})
    if not isinstance(audit_review, dict):
        _add(errors, "audit_review_procedure must be an object.")
    else:
        for field in ("owner", "raw_data_policy"):
            if not _has_text(audit_review.get(field)):
                _add(errors, f"audit_review_procedure.{field} must be non-empty.")
        if not isinstance(audit_review.get("start_within_minutes"), int) or audit_review.get("start_within_minutes") <= 0:
            _add(errors, "audit_review_procedure.start_within_minutes must be a positive integer.")
        for field in ("records_to_collect", "commands", "outputs"):
            if not isinstance(audit_review.get(field), list) or not audit_review.get(field):
                _add(errors, f"audit_review_procedure.{field} must be a non-empty list.")
        raw_policy = str(audit_review.get("raw_data_policy", "")).lower()
        for forbidden in ("raw customer", "raw candidate", "payment data", "tokens"):
            if forbidden not in raw_policy:
                _add(errors, f"audit_review_procedure.raw_data_policy must mention {forbidden}.")

    customer_impact = payload.get("customer_impact_review", {})
    if not isinstance(customer_impact, dict):
        _add(errors, "customer_impact_review must be an object.")
    else:
        for field in ("owner", "customer_notification_owner"):
            value = customer_impact.get(field)
            if not _has_text(value) or _is_placeholder(value):
                _add(errors, f"customer_impact_review.{field} must be concrete.")
        if not isinstance(customer_impact.get("start_within_minutes"), int) or customer_impact.get("start_within_minutes") <= 0:
            _add(errors, "customer_impact_review.start_within_minutes must be a positive integer.")
        required_for = set(customer_impact.get("required_for_severities") or [])
        for severity in ("sev0", "sev1", "sev2"):
            if severity not in required_for:
                _add(errors, f"customer_impact_review.required_for_severities must include {severity}.")
        for field in ("review_questions", "remediation_paths"):
            if not isinstance(customer_impact.get(field), list) or not customer_impact.get(field):
                _add(errors, f"customer_impact_review.{field} must be a non-empty list.")

    release_gate = payload.get("release_gate", {})
    if release_gate.get("script") != "scripts/validate_incident_response_plan.py":
        _add(errors, "release_gate.script must point to scripts/validate_incident_response_plan.py.")
    if release_gate.get("category") != "production-profile":
        _add(errors, "release_gate.category must be production-profile.")
    if release_gate.get("blocks_release") is not True:
        _add(errors, "release_gate.blocks_release must be true.")

    return {
        "valid": not errors,
        "errors": errors,
        "severity_count": len(severity_levels) if isinstance(severity_levels, list) else 0,
        "rollback_trigger_count": len(rollback_triggers) if isinstance(rollback_triggers, list) else 0,
        "notification_path_count": len(notification_paths) if isinstance(notification_paths, list) else 0,
        "required_severities": sorted(REQUIRED_SEVERITIES),
        "required_rollback_triggers": sorted(REQUIRED_ROLLBACK_TRIGGERS),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=DEFAULT_PLAN, help="Incident response plan JSON.")
    args = parser.parse_args(argv)

    report = validate_plan(args.plan)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
