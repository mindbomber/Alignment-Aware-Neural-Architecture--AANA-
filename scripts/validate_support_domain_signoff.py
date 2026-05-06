#!/usr/bin/env python3
"""Validate support domain-owner signoff coverage."""

from __future__ import annotations

import argparse
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SIGNOFF = ROOT / "examples" / "support_domain_owner_signoff_template.json"
REQUIRED_AREAS = {
    "refund_policy_interpretation",
    "verification_requirements",
    "escalation_paths",
    "safe_response_language",
    "human_review_triggers",
    "audit_retention",
    "customer_facing_language_boundaries",
    "allowed_automation_scope",
}
REQUIRED_APPROVER_ROLES = {
    "support_leadership",
    "support_policy_owner",
    "privacy_or_audit_owner",
}
REQUIRED_FIELD_NAMES = {
    "id",
    "title",
    "owner_role",
    "approval_status",
    "required_before",
    "review_scope",
    "evidence_required",
    "repo_references",
    "residual_risk",
}
ALLOWED_PENDING_STATUSES = {"pending", "approved", "rejected"}


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _repo_path_exists(reference):
    path_part = str(reference).split(":", 1)[0].split("#", 1)[0]
    if not path_part:
        return True
    return (ROOT / path_part).exists()


def validate_support_domain_signoff(path=DEFAULT_SIGNOFF, require_approved=False):
    payload = load_json(path)
    errors = []

    if payload.get("overall_status") not in {"pending_external_approval", "approved", "rejected"}:
        errors.append("overall_status must be pending_external_approval, approved, or rejected.")
    if payload.get("production_claim") != "not production-approved by this repository artifact":
        errors.append("production_claim must remain conservative.")

    scope = payload.get("scope", {})
    adapters = set(scope.get("adapters", []))
    for adapter_id in {"support_reply", "crm_support_reply", "email_send_guardrail", "ticket_update_checker"}:
        if adapter_id not in adapters:
            errors.append(f"scope.adapters missing {adapter_id}.")

    approver_roles = {item.get("role") for item in payload.get("required_approvers", [])}
    missing_roles = sorted(REQUIRED_APPROVER_ROLES - approver_roles)
    if missing_roles:
        errors.append(f"required_approvers missing roles: {', '.join(missing_roles)}")

    areas = payload.get("required_signoff_areas", [])
    area_ids = {area.get("id") for area in areas}
    missing_areas = sorted(REQUIRED_AREAS - area_ids)
    if missing_areas:
        errors.append(f"required_signoff_areas missing: {', '.join(missing_areas)}")

    for area in areas:
        area_id = area.get("id", "<missing>")
        missing_fields = sorted(REQUIRED_FIELD_NAMES - set(area))
        if missing_fields:
            errors.append(f"{area_id}: missing fields {', '.join(missing_fields)}")
        if area.get("owner_role") not in REQUIRED_APPROVER_ROLES:
            errors.append(f"{area_id}: owner_role must be one of {', '.join(sorted(REQUIRED_APPROVER_ROLES))}.")
        if area.get("approval_status") not in ALLOWED_PENDING_STATUSES:
            errors.append(f"{area_id}: approval_status must be pending, approved, or rejected.")
        if require_approved and area.get("approval_status") != "approved":
            errors.append(f"{area_id}: approval_status must be approved for enforced support phases.")
        if not area.get("required_before"):
            errors.append(f"{area_id}: required_before must be non-empty.")
        if not area.get("evidence_required"):
            errors.append(f"{area_id}: evidence_required must be non-empty.")
        if not str(area.get("review_scope", "")).strip():
            errors.append(f"{area_id}: review_scope is required.")
        if not str(area.get("residual_risk", "")).strip():
            errors.append(f"{area_id}: residual_risk is required.")
        for reference in area.get("repo_references", []):
            if not _repo_path_exists(reference):
                errors.append(f"{area_id}: repo reference does not exist: {reference}")

    rules = payload.get("approval_rules", {})
    if rules.get("require_all_areas_approved_before_enforced_support") is not True:
        errors.append("approval_rules.require_all_areas_approved_before_enforced_support must be true.")
    if rules.get("require_live_evidence_before_production") is not True:
        errors.append("approval_rules.require_live_evidence_before_production must be true.")
    if rules.get("allow_pending_for_demo_or_shadow") is not True:
        errors.append("approval_rules.allow_pending_for_demo_or_shadow must be true.")

    return {
        "valid": not errors,
        "errors": errors,
        "area_count": len(areas),
        "required_areas": sorted(REQUIRED_AREAS),
        "overall_status": payload.get("overall_status"),
        "require_approved": require_approved,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signoff", default=DEFAULT_SIGNOFF, help="Support domain owner signoff JSON artifact.")
    parser.add_argument(
        "--require-approved",
        action="store_true",
        help="Require all signoff areas to be approved. Use this before enforced support phases.",
    )
    args = parser.parse_args(argv)
    report = validate_support_domain_signoff(args.signoff, require_approved=args.require_approved)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
