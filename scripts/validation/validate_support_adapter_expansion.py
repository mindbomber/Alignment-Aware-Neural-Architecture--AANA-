#!/usr/bin/env python3
"""Validate the gated AANA support adapter expansion plan."""

from __future__ import annotations

import argparse
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_PLAN = ROOT / "examples" / "support_adapter_expansion_plan.json"
GALLERY = ROOT / "examples" / "adapter_gallery.json"
REQUIRED_CANDIDATES = {
    "refunds",
    "account_closure",
    "chargeback",
    "cancellation",
    "escalation",
    "retention_deletion_request",
}
REQUIRED_SURFACES = {"Workflow Contract", "Agent Event Contract", "HTTP bridge", "Python SDK", "CLI"}
REQUIRED_CANDIDATE_FIELDS = {
    "id",
    "title",
    "status",
    "family",
    "risk_tier",
    "product_boundary",
    "supported_surfaces",
    "evidence_requirements",
    "verifier_behavior",
    "correction_policy",
    "human_review_path",
    "production_status",
    "promotion_requirements",
    "caveats",
}


def _load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _repo_path(reference):
    path = pathlib.Path(str(reference))
    return path if path.is_absolute() else ROOT / path


def _has_text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_expansion_plan(path=DEFAULT_PLAN):
    payload = _load_json(path)
    gallery = _load_json(GALLERY)
    errors = []

    gate = payload.get("first_enforced_baseline_gate", {})
    if gate.get("required") is not True:
        errors.append("first_enforced_baseline_gate.required must be true.")
    if gate.get("status") != "passed":
        errors.append("first_enforced_baseline_gate.status must be passed before productizing expansion candidates.")
    if not _has_text(gate.get("promotion_rule")) or "Do not add" not in gate.get("promotion_rule", ""):
        errors.append("first_enforced_baseline_gate.promotion_rule must prevent premature supported-adapter promotion.")

    baseline_ref = gate.get("baseline_ref")
    if not baseline_ref or not _repo_path(baseline_ref).exists():
        errors.append("first_enforced_baseline_gate.baseline_ref must point to an existing baseline artifact.")
        baseline = {}
    else:
        baseline = _load_json(_repo_path(baseline_ref))
        if baseline.get("current_status") != "reached":
            errors.append("baseline_ref.current_status must be reached.")

    for result_ref in gate.get("measured_results", []) or []:
        result_path = _repo_path(result_ref)
        if not result_path.exists():
            errors.append(f"measured result does not exist: {result_ref}")
            continue
        result = _load_json(result_path)
        if result.get("measurement_status") != gate.get("required_measurement_status"):
            errors.append(f"{result_ref}: measurement_status must be {gate.get('required_measurement_status')}.")

    candidates = payload.get("candidates", [])
    by_id = {item.get("id"): item for item in candidates if isinstance(item, dict)}
    missing = sorted(REQUIRED_CANDIDATES - set(by_id))
    if missing:
        errors.append(f"missing expansion candidates: {', '.join(missing)}")

    support_line = gallery.get("product_lines", {}).get("support", {})
    supported_ids = set(support_line.get("adapter_ids", []))
    later_adapters = set(support_line.get("later_adapters", []))
    if later_adapters != REQUIRED_CANDIDATES:
        errors.append("adapter_gallery.product_lines.support.later_adapters must match the expansion candidate set.")
    premature = sorted(REQUIRED_CANDIDATES & supported_ids)
    if premature:
        errors.append(f"expansion candidates must not be supported adapter_ids yet: {', '.join(premature)}")

    for candidate_id, candidate in by_id.items():
        missing_fields = sorted(REQUIRED_CANDIDATE_FIELDS - set(candidate))
        if missing_fields:
            errors.append(f"{candidate_id}: missing fields {', '.join(missing_fields)}")
            continue
        if candidate.get("status") != "expansion_candidate":
            errors.append(f"{candidate_id}: status must be expansion_candidate.")
        if candidate.get("production_status") != "not_supported_expansion_candidate":
            errors.append(f"{candidate_id}: production_status must be not_supported_expansion_candidate.")
        if candidate.get("risk_tier") not in {"high", "strict"}:
            errors.append(f"{candidate_id}: risk_tier must be high or strict for later support adapters.")
        if not REQUIRED_SURFACES.issubset(set(candidate.get("supported_surfaces", []))):
            errors.append(f"{candidate_id}: supported_surfaces must include every public surface.")
        for field in ("evidence_requirements", "verifier_behavior", "promotion_requirements", "caveats"):
            if not isinstance(candidate.get(field), list) or not candidate.get(field):
                errors.append(f"{candidate_id}: {field} must be a non-empty list.")
        if not isinstance(candidate.get("correction_policy"), dict) or not candidate.get("correction_policy"):
            errors.append(f"{candidate_id}: correction_policy must be a non-empty object.")
        if not _has_text(candidate.get("human_review_path")):
            errors.append(f"{candidate_id}: human_review_path must be concrete.")

    release_gate = payload.get("release_gate", {})
    if release_gate.get("script") != "scripts/validation/validate_support_adapter_expansion.py":
        errors.append("release_gate.script must point to scripts/validation/validate_support_adapter_expansion.py.")
    if release_gate.get("category") != "catalog":
        errors.append("release_gate.category must be catalog.")
    if release_gate.get("blocks_release") is not True:
        errors.append("release_gate.blocks_release must be true.")

    return {
        "valid": not errors,
        "errors": errors,
        "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
        "required_candidates": sorted(REQUIRED_CANDIDATES),
        "baseline_status": baseline.get("current_status"),
        "gate_status": gate.get("status"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=DEFAULT_PLAN, help="Support adapter expansion plan JSON.")
    args = parser.parse_args(argv)

    report = validate_expansion_plan(args.plan)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
