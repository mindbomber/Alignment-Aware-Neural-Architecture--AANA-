#!/usr/bin/env python3
"""Validate the AANA internal pilot rollout plan."""

from __future__ import annotations

import argparse
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DEPLOYMENT = ROOT / "examples" / "production_deployment_internal_pilot.json"
REQUIRED_PHASES = [
    "shadow_mode",
    "advisory_mode",
    "enforced_support_drafts",
    "enforced_email_send_guardrail",
    "expanded_support_workflows",
]
SUPPORT_DRAFT_ADAPTERS = {"support_reply", "crm_support_reply", "ticket_update_checker"}


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def validate_internal_pilot_plan(path=DEFAULT_DEPLOYMENT):
    manifest = load_json(path)
    errors = []
    rollout = manifest.get("pilot_rollout")
    if not isinstance(rollout, dict):
        return {"valid": False, "errors": ["pilot_rollout is required."], "phase_count": 0}

    if rollout.get("default_phase") != "shadow_mode":
        errors.append("pilot_rollout.default_phase must be shadow_mode.")
    if rollout.get("autonomous_enforcement_allowed") is not False:
        errors.append("pilot_rollout.autonomous_enforcement_allowed must be false.")

    phases = sorted(rollout.get("phase_sequence", []), key=lambda item: item.get("order", 0))
    phase_names = [phase.get("phase") for phase in phases]
    if phase_names != REQUIRED_PHASES:
        errors.append(f"phase_sequence must be ordered as {', '.join(REQUIRED_PHASES)}.")

    orders = [phase.get("order") for phase in phases]
    if orders != list(range(1, len(REQUIRED_PHASES) + 1)):
        errors.append("phase orders must be contiguous starting at 1.")

    phases_by_name = {phase.get("phase"): phase for phase in phases}
    shadow = phases_by_name.get("shadow_mode", {})
    if shadow.get("mode") != "shadow" or shadow.get("enforcement") != "observe_only":
        errors.append("shadow_mode must use mode=shadow and enforcement=observe_only.")
    if not {"redacted audit log with shadow records", "would-route metrics by adapter"}.issubset(
        set(shadow.get("required_exit_evidence", []))
    ):
        errors.append("shadow_mode must require redacted shadow audit records and would-route metrics.")

    advisory = phases_by_name.get("advisory_mode", {})
    if advisory.get("enforcement") != "human_decides":
        errors.append("advisory_mode must leave proceed/hold decisions to humans.")

    support_drafts = phases_by_name.get("enforced_support_drafts", {})
    if support_drafts.get("mode") != "enforced":
        errors.append("enforced_support_drafts must be the first enforced phase.")
    if not set(support_drafts.get("adapters", [])).issubset(SUPPORT_DRAFT_ADAPTERS):
        errors.append("enforced_support_drafts may only cover narrow support draft adapters.")

    email = phases_by_name.get("enforced_email_send_guardrail", {})
    if email.get("adapters") != ["email_send_guardrail"]:
        errors.append("enforced_email_send_guardrail must cover only email_send_guardrail.")
    if "human approval path for irreversible send" not in email.get("required_exit_evidence", []):
        errors.append("email enforcement must require a human approval path for irreversible send.")

    expanded = phases_by_name.get("expanded_support_workflows", {})
    if expanded.get("order", 0) <= email.get("order", 0):
        errors.append("expanded support workflows must come after email-send enforcement.")
    if "expanded support calibration report" not in expanded.get("required_exit_evidence", []):
        errors.append("expanded support workflows must require calibration evidence.")

    for phase in phases:
        name = phase.get("phase", "<missing>")
        if not phase.get("promotion_gate"):
            errors.append(f"{name}: promotion_gate is required.")
        if not phase.get("required_exit_evidence"):
            errors.append(f"{name}: required_exit_evidence is required.")
        if not phase.get("adapters"):
            errors.append(f"{name}: adapters are required.")

    return {
        "valid": not errors,
        "errors": errors,
        "phase_count": len(phases),
        "default_phase": rollout.get("default_phase"),
        "phases": phase_names,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deployment-manifest", default=DEFAULT_DEPLOYMENT, help="Internal pilot deployment manifest.")
    args = parser.parse_args(argv)
    report = validate_internal_pilot_plan(args.deployment_manifest)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
