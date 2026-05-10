#!/usr/bin/env python3
"""Validate the conservative AANA production readiness boundary."""

from __future__ import annotations

import argparse
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_BOUNDARY = ROOT / "examples" / "production_readiness_boundary.json"
REQUIRED_REPO_STATUSES = {"demo-ready", "pilot-ready", "production-candidate"}
REQUIRED_GATES = {
    "live_evidence_connectors",
    "domain_owner_signoff",
    "audit_retention",
    "observability",
    "human_review_path",
    "security_review",
    "deployment_manifest",
    "incident_response_plan",
    "measured_pilot_results",
}
CONSERVATIVE_PHRASE = "not production-certified by local tests alone"


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def validate_boundary(path=DEFAULT_BOUNDARY):
    payload = load_json(path)
    errors = []

    statuses = set(payload.get("allowed_repo_statuses", []))
    if statuses != REQUIRED_REPO_STATUSES:
        errors.append("allowed_repo_statuses must be exactly demo-ready, pilot-ready, and production-candidate.")

    positioning = payload.get("repo_local_positioning", "")
    if CONSERVATIVE_PHRASE not in positioning:
        errors.append(f"repo_local_positioning must include {CONSERVATIVE_PHRASE!r}.")

    forbidden_claims = " ".join(payload.get("forbidden_claims", []))
    if "production-certified by local tests alone" not in forbidden_claims:
        errors.append("forbidden_claims must reject production certification by local tests alone.")

    gates = payload.get("production_readiness_requires", [])
    gate_ids = {gate.get("id") for gate in gates}
    missing_gates = sorted(REQUIRED_GATES - gate_ids)
    if missing_gates:
        errors.append(f"production_readiness_requires missing gates: {', '.join(missing_gates)}")
    for gate in gates:
        gate_id = gate.get("id", "<missing>")
        if not gate.get("title"):
            errors.append(f"{gate_id}: title is required.")
        if not gate.get("description"):
            errors.append(f"{gate_id}: description is required.")

    local_boundary = payload.get("local_test_boundary", {})
    cannot_prove = " ".join(local_boundary.get("local_tests_cannot_prove", []))
    for expected in {
        "live connector permissions",
        "domain owner approval",
        "retained audit evidence",
        "deployed observability",
        "human review staffing",
        "security approval",
        "incident response readiness",
        "measured pilot performance",
    }:
        if expected not in cannot_prove:
            errors.append(f"local_tests_cannot_prove must mention {expected!r}.")

    return {
        "valid": not errors,
        "errors": errors,
        "allowed_repo_statuses": sorted(statuses),
        "required_gates": sorted(REQUIRED_GATES),
        "gate_count": len(gates),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary", default=DEFAULT_BOUNDARY, help="Production readiness boundary JSON.")
    args = parser.parse_args(argv)
    report = validate_boundary(args.boundary)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
