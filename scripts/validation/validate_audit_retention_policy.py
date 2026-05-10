#!/usr/bin/env python3
"""Validate production audit retention policy and support redaction proof."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api


DEFAULT_POLICY = ROOT / "examples" / "audit_retention_policy_internal_pilot.json"
DEFAULT_SUPPORT_FIXTURES = ROOT / "examples" / "support_workflow_contract_examples.json"
REQUIRED_PROHIBITED_FIELDS = {
    "raw_customer_message",
    "raw_candidate_response",
    "raw_prompt",
    "raw_evidence",
    "full_crm_record",
    "payment_or_billing_data",
    "internal_notes",
    "attachment_body",
    "safe_response_text",
    "secrets",
    "tokens",
}
REQUIRED_ACCESS_DENY = {"public", "unauthenticated"}


def _load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _add(errors, message):
    errors.append(message)


def _repo_path_exists(reference):
    raw = str(reference).split(":", 1)[0].split("#", 1)[0]
    if not raw:
        return True
    return (ROOT / raw).exists()


def _fixture_cases(path):
    payload = _load_json(path)
    cases = payload.get("cases", [])
    if not isinstance(cases, list) or not cases:
        raise ValueError("Support fixture must contain a non-empty cases array.")
    return cases


def _raw_forbidden_terms(case):
    workflow = case.get("workflow_request", {})
    event = case.get("agent_event", {})
    terms = [
        workflow.get("request"),
        workflow.get("candidate"),
        event.get("user_request"),
        event.get("candidate_action"),
        case.get("candidate_output"),
        case.get("candidate_bad_output"),
    ]
    terms.extend(item.get("text") for item in workflow.get("evidence", []) if isinstance(item, dict))
    terms.extend(item for item in event.get("available_evidence", []) if isinstance(item, str))
    return [term for term in terms if isinstance(term, str) and term]


def _support_redaction_proof(fixture_path):
    records = []
    forbidden_terms = []
    cases = _fixture_cases(fixture_path)
    for case in cases:
        workflow_request = case["workflow_request"]
        workflow_result = agent_api.check_workflow_request(workflow_request)
        records.append(agent_api.audit_workflow_check(workflow_request, workflow_result))
        event = case["agent_event"]
        event_result = agent_api.check_event(event)
        records.append(agent_api.audit_event_check(event, event_result))
        forbidden_terms.extend(_raw_forbidden_terms(case))

    validation = agent_api.validate_audit_records(records)
    redaction = agent_api.audit_redaction_report(records, forbidden_terms=forbidden_terms)
    return {
        "record_count": len(records),
        "fixture_case_count": len(cases),
        "schema_valid": validation["valid"],
        "redacted": redaction["redacted"],
        "validation_errors": validation["errors"],
        "redaction_errors": redaction["errors"],
        "issues": validation["issues"] + redaction["issues"],
    }


def validate_policy(policy_path=DEFAULT_POLICY, fixture_path=DEFAULT_SUPPORT_FIXTURES):
    payload = _load_json(policy_path)
    errors = []

    if payload.get("status") not in {"approved_for_internal_pilot", "approved_for_production"}:
        _add(errors, "status must be approved_for_internal_pilot or approved_for_production.")
    if "not certify external production readiness" not in str(payload.get("positioning", "")):
        _add(errors, "positioning must keep external production readiness conservative.")

    scope = payload.get("audit_record_scope", {})
    if scope.get("records") != "decision metadata only":
        _add(errors, "audit_record_scope.records must be decision metadata only.")
    if scope.get("raw_artifact_store") != "none":
        _add(errors, "audit_record_scope.raw_artifact_store must be none.")
    if scope.get("redaction_required") is not True:
        _add(errors, "audit_record_scope.redaction_required must be true.")
    prohibited = set(scope.get("prohibited_fields", []))
    missing_prohibited = sorted(REQUIRED_PROHIBITED_FIELDS - prohibited)
    if missing_prohibited:
        _add(errors, f"audit_record_scope.prohibited_fields missing: {', '.join(missing_prohibited)}.")

    storage = payload.get("storage", {})
    if storage.get("approved") is not True:
        _add(errors, "storage.approved must be true.")
    sink_uri = str(storage.get("sink_uri", ""))
    if not sink_uri or sink_uri.startswith(("jsonl://", "file://")):
        _add(errors, "storage.sink_uri must name approved immutable storage, not local JSONL or file storage.")
    if storage.get("append_only") is not True:
        _add(errors, "storage.append_only must be true.")
    if storage.get("immutable") is not True:
        _add(errors, "storage.immutable must be true.")
    if storage.get("object_lock") not in {"governance", "compliance"}:
        _add(errors, "storage.object_lock must be governance or compliance.")
    if storage.get("versioning") is not True:
        _add(errors, "storage.versioning must be true.")
    if "no overwrite" not in str(storage.get("write_mode", "")).lower() or "delete" not in str(storage.get("write_mode", "")).lower():
        _add(errors, "storage.write_mode must deny overwrite and delete permission for runtime writers.")
    if not _repo_path_exists(storage.get("deployment_manifest_ref", "")):
        _add(errors, f"storage.deployment_manifest_ref does not exist: {storage.get('deployment_manifest_ref')}")

    retention = payload.get("retention", {})
    if not isinstance(retention.get("minimum_days"), int) or retention.get("minimum_days") < 365:
        _add(errors, "retention.minimum_days must be at least 365.")
    if not isinstance(retention.get("default_days"), int) or retention.get("default_days") < retention.get("minimum_days", 0):
        _add(errors, "retention.default_days must be greater than or equal to minimum_days.")
    if "legal hold" not in str(retention.get("delete_after_expiration", "")).lower():
        _add(errors, "retention.delete_after_expiration must account for legal hold.")
    legal_hold = retention.get("legal_hold", {})
    if legal_hold.get("supported") is not True or not legal_hold.get("authority") or not legal_hold.get("effect"):
        _add(errors, "retention.legal_hold must define supported=true, authority, and effect.")

    access = payload.get("access_control", {})
    if not access.get("runtime_writer_role"):
        _add(errors, "access_control.runtime_writer_role is required.")
    if not access.get("reader_roles") or not access.get("admin_roles"):
        _add(errors, "access_control must define reader_roles and admin_roles.")
    denied = set(access.get("denied", []))
    missing_denies = sorted(REQUIRED_ACCESS_DENY - denied)
    if missing_denies:
        _add(errors, f"access_control.denied missing: {', '.join(missing_denies)}.")
    if access.get("mfa_required") is not True:
        _add(errors, "access_control.mfa_required must be true.")
    if access.get("least_privilege") is not True:
        _add(errors, "access_control.least_privilege must be true.")
    if access.get("break_glass_review_required") is not True:
        _add(errors, "access_control.break_glass_review_required must be true.")

    integrity = payload.get("integrity_checks", {})
    if integrity.get("hash_algorithm") != "sha256":
        _add(errors, "integrity_checks.hash_algorithm must be sha256.")
    if integrity.get("manifest_chain_required") is not True:
        _add(errors, "integrity_checks.manifest_chain_required must be true.")
    if integrity.get("previous_manifest_hash_required") is not True:
        _add(errors, "integrity_checks.previous_manifest_hash_required must be true.")
    if "audit-verify" not in str(integrity.get("verification_command", "")):
        _add(errors, "integrity_checks.verification_command must use audit-verify.")
    if not integrity.get("tamper_response"):
        _add(errors, "integrity_checks.tamper_response is required.")

    redaction_proof = payload.get("redaction_proof", {})
    if redaction_proof.get("required_result") != "no_raw_support_data_stored":
        _add(errors, "redaction_proof.required_result must be no_raw_support_data_stored.")
    proof = _support_redaction_proof(fixture_path)
    if not proof["schema_valid"]:
        _add(errors, "support redaction proof failed audit schema validation.")
    if not proof["redacted"]:
        _add(errors, "support redaction proof found raw support data in audit records.")

    release_gate = payload.get("release_gate", {})
    if release_gate.get("script") != "scripts/validation/validate_audit_retention_policy.py":
        _add(errors, "release_gate.script must point to scripts/validation/validate_audit_retention_policy.py.")
    if release_gate.get("category") != "production-profile":
        _add(errors, "release_gate.category must be production-profile.")
    if release_gate.get("blocks_release") is not True:
        _add(errors, "release_gate.blocks_release must be true.")

    return {
        "valid": not errors,
        "errors": errors,
        "policy_id": payload.get("policy_id"),
        "status": payload.get("status"),
        "storage_sink": storage.get("sink_uri"),
        "retention_days": retention.get("default_days"),
        "append_only": storage.get("append_only") is True,
        "immutable": storage.get("immutable") is True,
        "redaction_proof": proof,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default=DEFAULT_POLICY, help="Audit retention policy JSON.")
    parser.add_argument("--support-fixtures", default=DEFAULT_SUPPORT_FIXTURES, help="Support workflow fixture JSON.")
    args = parser.parse_args(argv)

    report = validate_policy(args.policy, args.support_fixtures)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
