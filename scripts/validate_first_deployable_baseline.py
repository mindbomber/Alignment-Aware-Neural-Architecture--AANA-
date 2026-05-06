#!/usr/bin/env python3
"""Validate the first deployable AANA support runtime baseline boundary."""

from __future__ import annotations

import argparse
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / "examples" / "first_deployable_support_baseline.json"
REQUIRED_SUPPORT_ADAPTERS = {
    "support_reply",
    "crm_support_reply",
    "email_send_guardrail",
    "ticket_update_checker",
    "invoice_billing_reply",
}
REQUIRED_CRITERIA = {
    "support_contract_paths",
    "registry_driven_runtime_routing",
    "support_evidence_connectors",
    "audit_safe_records",
    "human_review_paths",
    "golden_outputs",
    "gallery_validation",
    "release_gate",
    "security_privacy_review",
    "support_domain_owner_signoff",
    "internal_pilot_metrics",
}
REQUIRED_PILOT_METRICS = {
    "max_over_acceptance_count",
    "max_over_refusal_count",
    "max_p95_latency_ms",
    "min_correction_success_rate",
}
REQUIRED_ATTACHMENTS = {
    "connector_manifests",
    "deployment_manifest",
    "support_owner_signoff",
    "measured_pilot_results",
}
REACHED_STATUSES = {"reached", "approved", "validated"}


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _repo_path_exists(reference):
    reference = str(reference)
    if pathlib.Path(reference).is_absolute():
        return pathlib.Path(reference).exists()
    raw_path = reference.split(":", 1)[0].split("#", 1)[0]
    if not raw_path or raw_path.startswith("scripts/aana_cli.py "):
        return True
    if raw_path.startswith("scripts/dev.py "):
        return (ROOT / "scripts" / "dev.py").exists()
    path = pathlib.Path(raw_path)
    if path.is_absolute():
        return path.exists()
    return (ROOT / path).exists()


def _criterion_reached(criterion):
    return criterion.get("status") in REACHED_STATUSES


def _load_attached_json(attachments, key, errors):
    reference = attachments.get(key)
    if not isinstance(reference, str) or not reference.strip():
        errors.append(f"attached_artifacts.{key} is required.")
        return None
    if not _repo_path_exists(reference):
        errors.append(f"attached_artifacts.{key} path does not exist: {reference}")
        return None
    try:
        path = pathlib.Path(reference)
        return load_json(path if path.is_absolute() else ROOT / path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"attached_artifacts.{key} must be readable JSON: {exc}")
        return None


def _validate_connector_attachment(payload, errors):
    manifests = payload.get("connector_manifests", []) if isinstance(payload, dict) else []
    by_id = {item.get("connector_id"): item for item in manifests if isinstance(item, dict)}
    missing = sorted(
        {
            "crm_customer_account",
            "order_history",
            "refund_policy",
            "internal_notes_classifier",
            "support_ticket_history",
            "email_recipient_verification",
            "attachment_metadata",
            "account_verification_status",
            "billing_payment_redaction",
            "support_policy_registry",
        }
        - set(by_id)
    )
    if missing:
        errors.append(f"connector_manifests missing support connector(s): {', '.join(missing)}")
    for connector_id, manifest in by_id.items():
        if connector_id not in missing and connector_id:
            if manifest.get("source_mode") != "live":
                errors.append(f"connector_manifests.{connector_id}: source_mode must be live.")
            if manifest.get("approval_status") not in {"live_approved", "approved"}:
                errors.append(f"connector_manifests.{connector_id}: approval_status must be live_approved or approved.")
            if not str(manifest.get("endpoint_url", "")).startswith("https://"):
                errors.append(f"connector_manifests.{connector_id}: endpoint_url must be HTTPS.")


def _validate_signoff_attachment(payload, errors):
    if not isinstance(payload, dict):
        errors.append("support_owner_signoff must be a JSON object.")
        return
    if payload.get("overall_status") != "approved":
        errors.append("support_owner_signoff.overall_status must be approved.")
    for approver in payload.get("required_approvers", []):
        if approver.get("approval_status") != "approved":
            errors.append(f"support_owner_signoff approver {approver.get('role', '<missing>')} must be approved.")
    for area in payload.get("required_signoff_areas", []):
        if area.get("approval_status") != "approved":
            errors.append(f"support_owner_signoff area {area.get('id', '<missing>')} must be approved.")


def _validate_pilot_results_attachment(payload, thresholds, errors):
    if not isinstance(payload, dict):
        errors.append("measured_pilot_results must be a JSON object.")
        return
    if payload.get("measurement_status") != "accepted":
        errors.append("measured_pilot_results.measurement_status must be accepted.")
    metrics = payload.get("metrics", {})
    for key in ("over_acceptance_count", "over_refusal_count", "p95_latency_ms", "correction_success_rate"):
        if not isinstance(metrics.get(key), (int, float)):
            errors.append(f"measured_pilot_results.metrics.{key} is required.")
            return
    if metrics.get("over_acceptance_count") > thresholds.get("max_over_acceptance_count", -1):
        errors.append("measured_pilot_results.over_acceptance_count exceeds threshold.")
    if metrics.get("over_refusal_count") > thresholds.get("max_over_refusal_count", -1):
        errors.append("measured_pilot_results.over_refusal_count exceeds threshold.")
    if metrics.get("p95_latency_ms") > thresholds.get("max_p95_latency_ms", -1):
        errors.append("measured_pilot_results.p95_latency_ms exceeds threshold.")
    if metrics.get("correction_success_rate") < thresholds.get("min_correction_success_rate", 2.0):
        errors.append("measured_pilot_results.correction_success_rate is below threshold.")
    for key in ("audit_log_ref", "metrics_report_ref", "reviewer_report_ref"):
        if not str(payload.get(key, "")).strip():
            errors.append(f"measured_pilot_results.{key} is required.")


def validate_first_deployable_baseline(path=DEFAULT_BASELINE, require_reached=False):
    payload = load_json(path)
    errors = []

    if payload.get("current_status") not in {"not_reached_external_evidence_required", "reached"}:
        errors.append("current_status must be not_reached_external_evidence_required or reached.")
    if "does not claim the baseline is reached" not in payload.get("positioning", "") and payload.get("current_status") != "reached":
        errors.append("positioning must stay conservative until baseline is reached.")

    adapters = set(payload.get("support_adapters", []))
    missing_adapters = sorted(REQUIRED_SUPPORT_ADAPTERS - adapters)
    if missing_adapters:
        errors.append(f"support_adapters missing: {', '.join(missing_adapters)}")

    criteria = payload.get("required_criteria", [])
    criteria_by_id = {item.get("id"): item for item in criteria}
    missing_criteria = sorted(REQUIRED_CRITERIA - set(criteria_by_id))
    if missing_criteria:
        errors.append(f"required_criteria missing: {', '.join(missing_criteria)}")

    for criterion in criteria:
        criterion_id = criterion.get("id", "<missing>")
        if not str(criterion.get("requirement", "")).strip():
            errors.append(f"{criterion_id}: requirement is required.")
        if not str(criterion.get("status", "")).strip():
            errors.append(f"{criterion_id}: status is required.")
        if not criterion.get("release_gate"):
            errors.append(f"{criterion_id}: release_gate is required.")
        evidence = criterion.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{criterion_id}: evidence must be a non-empty list.")
        for reference in evidence:
            if not _repo_path_exists(reference):
                errors.append(f"{criterion_id}: evidence path does not exist: {reference}")

    pilot = criteria_by_id.get("internal_pilot_metrics", {})
    thresholds = pilot.get("acceptance_thresholds", {})
    missing_metrics = sorted(REQUIRED_PILOT_METRICS - set(thresholds))
    if missing_metrics:
        errors.append(f"internal_pilot_metrics.acceptance_thresholds missing: {', '.join(missing_metrics)}")
    if thresholds.get("max_over_acceptance_count") != 0:
        errors.append("internal_pilot_metrics must require zero over-acceptance.")
    if thresholds.get("max_over_refusal_count") != 0:
        errors.append("internal_pilot_metrics must require zero over-refusal.")
    if not isinstance(thresholds.get("max_p95_latency_ms"), int) or thresholds.get("max_p95_latency_ms", 0) <= 0:
        errors.append("internal_pilot_metrics.max_p95_latency_ms must be a positive integer.")
    if thresholds.get("min_correction_success_rate") != 1.0:
        errors.append("internal_pilot_metrics must require full correction success for the baseline fixture threshold.")

    signoff = criteria_by_id.get("support_domain_owner_signoff", {})
    if signoff.get("status") != "pending_external_approval" and payload.get("current_status") != "reached":
        errors.append("support_domain_owner_signoff should remain pending_external_approval until a reached baseline artifact is supplied.")
    measured = criteria_by_id.get("internal_pilot_metrics", {})
    if measured.get("status") != "pending_measured_pilot_results" and payload.get("current_status") != "reached":
        errors.append("internal_pilot_metrics should remain pending_measured_pilot_results until measured pilot evidence is supplied.")

    if payload.get("current_status") == "reached" or require_reached:
        attachments = payload.get("attached_artifacts", {})
        if not isinstance(attachments, dict):
            errors.append("attached_artifacts must be an object for a reached baseline.")
            attachments = {}
        missing_attachments = sorted(REQUIRED_ATTACHMENTS - set(attachments))
        if missing_attachments:
            errors.append(f"attached_artifacts missing: {', '.join(missing_attachments)}")
        connector_payload = _load_attached_json(attachments, "connector_manifests", errors)
        signoff_payload = _load_attached_json(attachments, "support_owner_signoff", errors)
        pilot_payload = _load_attached_json(attachments, "measured_pilot_results", errors)
        deployment_payload = _load_attached_json(attachments, "deployment_manifest", errors)
        if connector_payload is not None:
            _validate_connector_attachment(connector_payload, errors)
        if signoff_payload is not None:
            _validate_signoff_attachment(signoff_payload, errors)
        if pilot_payload is not None:
            _validate_pilot_results_attachment(pilot_payload, thresholds, errors)
        if isinstance(deployment_payload, dict) and deployment_payload.get("environment") != payload.get("environment"):
            errors.append("attached deployment_manifest.environment must match baseline environment.")

    reached_policy = payload.get("baseline_reached_policy", {})
    if reached_policy.get("all_required_criteria_must_be_reached") is not True:
        errors.append("baseline_reached_policy.all_required_criteria_must_be_reached must be true.")
    external_required = reached_policy.get("external_evidence_required", [])
    for expected in (
        "live or approved support evidence connector manifest",
        "approved support domain owner signoff artifact",
        "measured internal pilot metrics report with over-acceptance, over-refusal, latency, and correction metrics",
    ):
        if expected not in external_required:
            errors.append(f"baseline_reached_policy.external_evidence_required missing {expected!r}.")

    reached = bool(criteria) and all(_criterion_reached(item) for item in criteria)
    if payload.get("current_status") == "reached" and not reached:
        errors.append("current_status cannot be reached unless every required criterion has a reached status.")
    if require_reached and payload.get("current_status") != "reached":
        errors.append("baseline has not reached deployable status; external signoff and measured pilot results are still required.")

    release_gate = payload.get("release_gate", {})
    if release_gate.get("script") != "scripts/validate_first_deployable_baseline.py":
        errors.append("release_gate.script must point to scripts/validate_first_deployable_baseline.py.")
    if release_gate.get("category") != "production-profile":
        errors.append("release_gate.category must be production-profile.")
    if release_gate.get("blocks_release") is not True:
        errors.append("release_gate.blocks_release must be true.")

    return {
        "valid": not errors,
        "errors": errors,
        "current_status": payload.get("current_status"),
        "criteria_count": len(criteria),
        "required_criteria": sorted(REQUIRED_CRITERIA),
        "baseline_reached": payload.get("current_status") == "reached",
        "require_reached": require_reached,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default=DEFAULT_BASELINE, help="First deployable support baseline JSON artifact.")
    parser.add_argument(
        "--require-reached",
        action="store_true",
        help="Fail unless the baseline artifact is externally complete and marked reached.",
    )
    args = parser.parse_args(argv)
    report = validate_first_deployable_baseline(args.baseline, require_reached=args.require_reached)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
