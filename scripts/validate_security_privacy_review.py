#!/usr/bin/env python3
"""Validate the support security/privacy review manifest."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_REVIEW = ROOT / "examples" / "security_privacy_review_support.json"
REQUIRED_CONTROLS = {
    "support_data_flow_threat_model",
    "raw_prompt_candidate_log_leakage",
    "token_auth_handling",
    "evidence_connector_permission_review",
    "pii_redaction_review",
    "attachment_metadata_handling",
    "internal_crm_note_exposure_tests",
    "audit_retention_policy",
    "support_domain_owner_signoff",
    "secrets_scanning",
    "rate_limiting_plan",
}
REQUIRED_CONTROL_FIELDS = {
    "id",
    "status",
    "owner",
    "required_before_deployment",
    "evidence",
    "tests_or_gates",
    "residual_risk",
}
EXTERNAL_REQUIRED_CONTROLS = {
    "evidence_connector_permission_review",
    "audit_retention_policy",
    "support_domain_owner_signoff",
    "secrets_scanning",
}


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_path_exists(reference):
    raw_path = reference.split(":", 1)[0].split("#", 1)[0]
    if not raw_path or raw_path.startswith("tests."):
        return True
    path = ROOT / raw_path
    return path.exists()


def validate_review(path=DEFAULT_REVIEW):
    review_path = pathlib.Path(path)
    payload = _load_json(review_path)
    errors = []

    if payload.get("deployment_position", {}).get("production_status") != "not production-certified by local tests alone":
        errors.append("deployment_position.production_status must remain conservative.")
    if payload.get("deployment_position", {}).get("repo_local_status") != "demo-ready/pilot-ready/production-candidate":
        errors.append("deployment_position.repo_local_status must be demo-ready/pilot-ready/production-candidate.")

    blockers = set(payload.get("deployment_position", {}).get("production_blockers", []))
    for expected in {
        "live evidence connector permission review",
        "domain owner signoff",
        "audit retention policy approval",
        "observability approval",
        "human review staffing and SLA",
        "security review approval",
        "deployment manifest approval",
        "incident response plan approval",
        "measured pilot results",
        "rate limit and abuse plan approved by deployment owner",
    }:
        if expected not in blockers:
            errors.append(f"deployment_position.production_blockers missing {expected!r}.")

    if len(payload.get("support_data_flow", [])) < 4:
        errors.append("support_data_flow must cover agent, evidence, runtime gate, and bridge/audit steps.")

    controls = payload.get("controls", [])
    control_ids = {control.get("id") for control in controls}
    missing_controls = sorted(REQUIRED_CONTROLS - control_ids)
    if missing_controls:
        errors.append(f"missing required controls: {', '.join(missing_controls)}")

    duplicate_ids = sorted(control_id for control_id in control_ids if control_id and sum(1 for c in controls if c.get("id") == control_id) > 1)
    if duplicate_ids:
        errors.append(f"duplicate controls: {', '.join(duplicate_ids)}")

    for control in controls:
        control_id = control.get("id", "<missing>")
        missing_fields = sorted(REQUIRED_CONTROL_FIELDS - set(control))
        if missing_fields:
            errors.append(f"{control_id}: missing fields {', '.join(missing_fields)}")
        if control.get("required_before_deployment") is not True:
            errors.append(f"{control_id}: required_before_deployment must be true.")
        for field in ("evidence", "tests_or_gates"):
            values = control.get(field)
            if not isinstance(values, list) or not values:
                errors.append(f"{control_id}: {field} must be a non-empty list.")
        if not str(control.get("residual_risk", "")).strip():
            errors.append(f"{control_id}: residual_risk must be explicit.")
        if control_id in EXTERNAL_REQUIRED_CONTROLS and "external" not in str(control.get("status", "")):
            if control.get("status") != "plan_required":
                errors.append(f"{control_id}: status must mark external deployment work or plan_required.")
        for reference in control.get("evidence", []):
            if not _repo_path_exists(reference):
                errors.append(f"{control_id}: evidence path does not exist: {reference}")

    release_gate = payload.get("release_gate", {})
    if release_gate.get("script") != "scripts/validate_security_privacy_review.py":
        errors.append("release_gate.script must point to scripts/validate_security_privacy_review.py.")
    if release_gate.get("category") != "production-profile":
        errors.append("release_gate.category must be production-profile.")
    if release_gate.get("blocks_release") is not True:
        errors.append("release_gate.blocks_release must be true.")

    return {"valid": not errors, "errors": errors, "control_count": len(controls), "required_controls": sorted(REQUIRED_CONTROLS)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", default=DEFAULT_REVIEW, help="Security/privacy review JSON manifest.")
    args = parser.parse_args(argv)

    report = validate_review(args.review)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
