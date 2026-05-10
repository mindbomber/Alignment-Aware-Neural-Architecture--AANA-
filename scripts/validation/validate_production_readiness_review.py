#!/usr/bin/env python3
"""Validate the environment-specific AANA support production readiness review."""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_REVIEW = ROOT / "examples" / "production_readiness_review_internal_pilot.json"
REQUIRED_COMMANDS = {
    "local_release_gates",
    "environment_baseline_require_reached",
}
REQUIRED_EVIDENCE = {
    "live_connector_evidence",
    "support_domain_owner_signoff",
    "pilot_metrics",
    "audit_retention",
    "observability",
    "security_privacy",
    "incident_response",
    "deployment_manifest",
}
APPROVED_STATUSES = {
    "accepted",
    "approved",
    "approved_for_internal_pilot",
    "passed",
    "reviewed",
}


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _load_baseline_validator():
    path = ROOT / "scripts" / "validation" / "validate_first_deployable_baseline.py"
    spec = importlib.util.spec_from_file_location("validate_first_deployable_baseline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _repo_path(reference):
    path = pathlib.Path(str(reference).split("#", 1)[0])
    return path if path.is_absolute() else ROOT / path


def _artifact_exists(reference):
    return bool(reference) and _repo_path(reference).exists()


def validate_production_readiness_review(path=DEFAULT_REVIEW):
    payload = load_json(path)
    errors = []

    if payload.get("environment") != "internal-pilot":
        errors.append("environment must be internal-pilot for the bundled review artifact.")
    if payload.get("review_status") != "approved_for_internal_pilot_deployable":
        errors.append("review_status must be approved_for_internal_pilot_deployable.")
    if payload.get("environment_deployable") is not True:
        errors.append("environment_deployable must be true after all review gates pass.")
    if payload.get("production_ready") is not False:
        errors.append("production_ready must remain false for the internal-pilot review artifact.")
    if "does not certify external production" not in payload.get("production_claim", ""):
        errors.append("production_claim must keep external production certification out of scope.")

    commands = payload.get("required_commands", [])
    commands_by_id = {item.get("id"): item for item in commands if isinstance(item, dict)}
    missing_commands = sorted(REQUIRED_COMMANDS - set(commands_by_id))
    if missing_commands:
        errors.append(f"required_commands missing: {', '.join(missing_commands)}")
    for command_id, command in commands_by_id.items():
        if command_id in REQUIRED_COMMANDS and command.get("status") != "passed":
            errors.append(f"required_commands.{command_id}.status must be passed.")
        if not str(command.get("command", "")).strip():
            errors.append(f"required_commands.{command_id}.command is required.")
    baseline_command = commands_by_id.get("environment_baseline_require_reached", {})
    baseline_command_text = baseline_command.get("command", "")
    if "--require-reached" not in baseline_command_text:
        errors.append("environment_baseline_require_reached command must include --require-reached.")

    baseline_artifact = payload.get("baseline_artifact")
    if not _artifact_exists(baseline_artifact):
        errors.append(f"baseline_artifact path does not exist: {baseline_artifact}")
    else:
        baseline = _load_baseline_validator()
        baseline_report = baseline.validate_first_deployable_baseline(_repo_path(baseline_artifact), require_reached=True)
        if not baseline_report["valid"]:
            errors.append(f"baseline_artifact must pass --require-reached: {baseline_report['errors']}")

    reviewed = payload.get("reviewed_evidence", [])
    reviewed_by_id = {item.get("id"): item for item in reviewed if isinstance(item, dict)}
    missing_evidence = sorted(REQUIRED_EVIDENCE - set(reviewed_by_id))
    if missing_evidence:
        errors.append(f"reviewed_evidence missing: {', '.join(missing_evidence)}")
    for evidence_id, evidence in reviewed_by_id.items():
        if evidence_id not in REQUIRED_EVIDENCE:
            continue
        if evidence.get("status") not in APPROVED_STATUSES:
            errors.append(f"reviewed_evidence.{evidence_id}.status is not approved.")
        if not _artifact_exists(evidence.get("artifact")):
            errors.append(f"reviewed_evidence.{evidence_id}.artifact path does not exist: {evidence.get('artifact')}")
        if not str(evidence.get("summary", "")).strip():
            errors.append(f"reviewed_evidence.{evidence_id}.summary is required.")

    decision = payload.get("decision", {})
    if decision.get("environment_status") != "deployable_internal_pilot":
        errors.append("decision.environment_status must be deployable_internal_pilot.")
    not_allowed = decision.get("not_allowed_scope", [])
    if "external production customer traffic" not in not_allowed:
        errors.append("decision.not_allowed_scope must exclude external production customer traffic.")
    if not str(decision.get("promotion_requirement", "")).strip():
        errors.append("decision.promotion_requirement is required.")

    release_gate = payload.get("release_gate", {})
    if release_gate.get("script") != "scripts/validation/validate_production_readiness_review.py":
        errors.append("release_gate.script must point to scripts/validation/validate_production_readiness_review.py.")
    if release_gate.get("category") != "production-profile":
        errors.append("release_gate.category must be production-profile.")
    if release_gate.get("blocks_release") is not True:
        errors.append("release_gate.blocks_release must be true.")

    return {
        "valid": not errors,
        "errors": errors,
        "environment": payload.get("environment"),
        "environment_deployable": payload.get("environment_deployable"),
        "production_ready": payload.get("production_ready"),
        "review_status": payload.get("review_status"),
        "reviewed_evidence_count": len(reviewed),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", default=DEFAULT_REVIEW, help="Production readiness review JSON artifact.")
    args = parser.parse_args(argv)
    report = validate_production_readiness_review(args.review)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
