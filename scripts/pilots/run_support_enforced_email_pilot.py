#!/usr/bin/env python3
"""Run the enforced support email-send guardrail pilot."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api
from scripts import run_support_shadow_pilot


DEFAULT_SUPPORT_FIXTURES = ROOT / "examples" / "support_workflow_contract_examples.json"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_SLA_POLICY = ROOT / "examples" / "support_sla_failure_policy.json"
DEFAULT_AUDIT_LOG = ROOT / "eval_outputs" / "audit" / "support-enforced-email-internal-pilot.jsonl"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "pilots" / "support-enforced-email-internal-pilot-results.json"
DEFAULT_METRICS = ROOT / "eval_outputs" / "pilots" / "support-enforced-email-internal-pilot-metrics.json"
DEFAULT_REVIEWER_REPORT = ROOT / "eval_outputs" / "pilots" / "support-enforced-email-internal-pilot-reviewer-report.md"
ENFORCED_EMAIL_ADAPTERS = ("email_send_guardrail",)
SUPPORT_ACTIONS = ("accept", "revise", "retrieve", "ask", "defer", "refuse")


class SupportEnforcedEmailPilotError(RuntimeError):
    pass


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _increment(mapping, key):
    if key:
        mapping[key] = mapping.get(key, 0) + 1


def _p95(values):
    return run_support_shadow_pilot._p95(values)


def _matches_expected(result, expected):
    return run_support_shadow_pilot._matches_expected(result, expected)


def _case_expected(case, surface):
    expected = case.get("expected", {})
    return expected.get(surface, {}) if isinstance(expected, dict) else {}


def enforced_cases(support_fixtures=DEFAULT_SUPPORT_FIXTURES):
    cases = []
    skipped = []
    for case in run_support_shadow_pilot.support_cases(support_fixtures):
        for surface, key in (("workflow", "workflow_request"), ("agent_event", "agent_event")):
            payload = case[key]
            adapter_id = payload.get("adapter") or payload.get("adapter_id")
            item = {"case": case, "surface": surface, "key": key, "adapter_id": adapter_id}
            if adapter_id in ENFORCED_EMAIL_ADAPTERS:
                cases.append(item)
            else:
                item["reason"] = "adapter_outside_enforced_email_allowlist"
                skipped.append(item)
    return cases, skipped


def _evidence_items(payload, surface):
    if surface == "workflow":
        evidence = payload.get("evidence", [])
        items = []
        for item in evidence if isinstance(evidence, list) else []:
            if isinstance(item, dict):
                items.append(
                    {
                        "source_id": str(item.get("source_id") or ""),
                        "text": str(item.get("text") or ""),
                        "trust_tier": str(item.get("trust_tier") or ""),
                    }
                )
            elif isinstance(item, str):
                items.append({"source_id": "", "text": item, "trust_tier": ""})
        return items

    evidence = payload.get("available_evidence", [])
    return [{"source_id": "", "text": str(item), "trust_tier": ""} for item in evidence if isinstance(item, str)]


def _has_source(items, source_id):
    needle = f"source_id={source_id}"
    for item in items:
        if item.get("source_id") == source_id:
            return True
        if needle in item.get("text", ""):
            return True
    return False


def _has_terms(items, *terms):
    haystack = "\n".join(item.get("text", "") for item in items).lower()
    return all(term.lower() in haystack for term in terms)


def _email_preflight(payload, surface):
    items = _evidence_items(payload, surface)
    recipient_verified = _has_source(items, "recipient-metadata") and _has_terms(items, "verified")
    attachment_metadata_dlp = _has_source(items, "attachment-metadata") and (
        _has_terms(items, "dlp") or _has_terms(items, "not safe") or _has_terms(items, "no approved attachments")
    )
    approval_path = _has_source(items, "user-approval")
    approval_text = "\n".join(item.get("text", "") for item in items).lower()
    send_approved = approval_path and "approved sending" in approval_text and "drafting only, not sending" not in approval_text
    return {
        "recipient_verification_present": recipient_verified,
        "attachment_metadata_dlp_present": attachment_metadata_dlp,
        "irreversible_send_approval_path_present": approval_path,
        "send_approval_status": "approved_to_send" if send_approved else "draft_or_missing_send_approval",
        "required_source_ids": ["recipient-metadata", "attachment-metadata", "user-approval"],
    }


def _bridge_outage_proof(policy_path):
    policy = load_json(policy_path)
    fallback = None
    for item in policy.get("undecidable_fallbacks", []):
        if item.get("id") == "bridge_unavailable_irreversible":
            fallback = item
            break
    mode_policy = policy.get("mode_policy", {}).get("enforced", {})
    proven = bool(
        fallback
        and fallback.get("failure_mode") == "fail_closed"
        and fallback.get("default_action") == "refuse"
        and fallback.get("human_review") is True
        and mode_policy.get("bridge_unavailable_irreversible") == "fail_closed"
    )
    return {
        "scenario": "email_send_guardrail_bridge_unavailable",
        "proven": proven,
        "failure_mode": fallback.get("failure_mode") if fallback else None,
        "recommended_action": fallback.get("default_action") if fallback else None,
        "production_effect": "send_blocked" if proven else "unknown",
        "human_review_required": bool(fallback.get("human_review")) if fallback else False,
        "audit_code": fallback.get("audit_code") if fallback else None,
        "mode_policy": mode_policy.get("bridge_unavailable_irreversible"),
    }


def _enforced_result(check_fn, payload, gallery_path):
    started = time.perf_counter()
    result = check_fn(payload, gallery_path=gallery_path)
    latency_ms = (time.perf_counter() - started) * 1000
    result = dict(result)
    result["latency_ms"] = round(latency_ms, 3)
    result["execution_mode"] = "enforce"
    action = result.get("recommended_action")
    candidate_gate = result.get("candidate_gate")
    send_allowed = action == "accept" and candidate_gate == "pass"
    result["production_decision"] = {
        "enforcement": "irreversible_email_send_blocking",
        "gate_decision": result.get("gate_decision"),
        "recommended_action": action,
        "candidate_gate": candidate_gate,
        "production_effect": "send_allowed" if send_allowed else "send_blocked",
        "send_allowed": send_allowed,
        "human_review_required": action in {"ask", "defer", "refuse"} or candidate_gate == "block",
    }
    return result, latency_ms


def _record_for_surface(surface, payload, result):
    if surface == "workflow":
        return agent_api.audit_workflow_check(payload, result=result)
    return agent_api.audit_event_check(payload, result=result)


def _reviewer_report(result):
    metrics = result["metrics"]
    lines = [
        "# AANA Support Enforced Email Pilot Reviewer Report",
        "",
        f"- Enforced email checks: {metrics['enforced_email_checks']}",
        f"- Sends allowed: {metrics['send_allowed_count']}",
        f"- Sends blocked: {metrics['send_blocked_count']}",
        f"- Preflight failures: {metrics['preflight_failure_count']}",
        f"- Bridge outage blocks sends: {metrics['bridge_outage_blocks_sends']}",
        f"- Excluded non-email checks: {metrics['excluded_non_email_checks']}",
        f"- P95 latency ms: {metrics['p95_latency_ms']}",
        "",
        "This phase enforces only email_send_guardrail after fixture-approved recipient, attachment/DLP, approval, and fail-closed bridge-outage checks.",
        "",
    ]
    return "\n".join(lines)


def run_enforced_email_pilot(args):
    cases, skipped = enforced_cases(args.support_fixtures)
    bridge_outage = _bridge_outage_proof(args.sla_policy)
    audit_log = pathlib.Path(args.audit_log)
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    if not args.append:
        audit_log.write_text("", encoding="utf-8")

    observations = []
    action_counts = {action: 0 for action in SUPPORT_ACTIONS}
    adapter_counts = {}
    expectation_failures = []
    preflight_failures = []
    latencies = []
    send_allowed = 0
    send_blocked = 0
    human_review_required = 0

    for item in cases:
        case = item["case"]
        surface = item["surface"]
        key = item["key"]
        payload = case[key]
        adapter_id = item["adapter_id"]
        if adapter_id not in ENFORCED_EMAIL_ADAPTERS:
            raise SupportEnforcedEmailPilotError(f"Unexpected adapter in enforced email pilot: {adapter_id}")

        preflight = _email_preflight(payload, surface)
        missing = [
            name
            for name in (
                "recipient_verification_present",
                "attachment_metadata_dlp_present",
                "irreversible_send_approval_path_present",
            )
            if not preflight.get(name)
        ]
        if missing:
            preflight_failures.append({"case": case.get("name"), "surface": surface, "missing": missing})

        check_fn = agent_api.check_workflow_request if surface == "workflow" else agent_api.check_event
        result, latency_ms = _enforced_result(check_fn, payload, args.gallery)
        expected = _case_expected(case, surface)
        passed, expectation_checks = _matches_expected(result, expected)
        if not passed:
            expectation_failures.append({"case": case.get("name"), "surface": surface, "checks": expectation_checks})

        action = result.get("recommended_action")
        production = result.get("production_decision", {})
        _increment(action_counts, action)
        _increment(adapter_counts, adapter_id)
        latencies.append(latency_ms)
        if production.get("send_allowed"):
            send_allowed += 1
        else:
            send_blocked += 1
        if production.get("human_review_required"):
            human_review_required += 1

        record = _record_for_surface(surface, payload, result)
        record["enforcement"] = {
            "mode": "irreversible_email_send_blocking",
            "adapter_allowlist": list(ENFORCED_EMAIL_ADAPTERS),
            "production_effect": production.get("production_effect"),
            "send_allowed": production.get("send_allowed"),
            "preflight": preflight,
            "bridge_outage_proof": bridge_outage,
        }
        agent_api.append_audit_record(audit_log, record)
        observations.append(
            {
                "case": case.get("name"),
                "surface": surface,
                "adapter_id": adapter_id,
                "execution_mode": "enforce",
                "recommended_action": action,
                "candidate_gate": result.get("candidate_gate"),
                "production_effect": production.get("production_effect"),
                "send_allowed": production.get("send_allowed"),
                "human_review_required": production.get("human_review_required"),
                "preflight": preflight,
                "latency_ms": round(latency_ms, 3),
                "expectations_passed": passed,
            }
        )

    metrics_output = pathlib.Path(args.metrics_output)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    audit_metrics = agent_api.export_audit_metrics_file(audit_log, output_path=metrics_output)
    total_checks = len(observations)
    metrics = {
        "enforced_email_checks": total_checks,
        "send_allowed_count": send_allowed,
        "send_blocked_count": send_blocked,
        "human_review_required_count": human_review_required,
        "excluded_non_email_checks": len(skipped),
        "preflight_failure_count": len(preflight_failures),
        "bridge_outage_blocks_sends": bridge_outage.get("production_effect") == "send_blocked",
        "p95_latency_ms": _p95(latencies),
    }
    result = {
        "pilot_results_version": "0.1",
        "pilot_id": "aana-support-enforced-email-internal-pilot",
        "environment": "internal-pilot",
        "execution_mode": "enforce",
        "enforcement": "irreversible_email_send_blocking",
        "measurement_status": "accepted"
        if not expectation_failures and not preflight_failures and bridge_outage.get("proven") and total_checks > 0
        else "needs_review",
        "enforced_adapters": list(ENFORCED_EMAIL_ADAPTERS),
        "source_fixture": str(pathlib.Path(args.support_fixtures)),
        "sla_policy_ref": str(pathlib.Path(args.sla_policy)),
        "audit_log_ref": str(audit_log),
        "metrics_report_ref": str(metrics_output),
        "reviewer_report_ref": str(pathlib.Path(args.reviewer_report)),
        "summary": {
            "enforced_cases": total_checks,
            "skipped_cases": len(skipped),
            "expectation_failures": len(expectation_failures),
            "preflight_failures": len(preflight_failures),
            "covered_enforced_adapters": sorted(adapter_counts),
        },
        "preflight_requirements": {
            "verified_recipient_required": True,
            "attachment_metadata_dlp_required": True,
            "irreversible_send_approval_path_required": True,
            "bridge_outage_must_fail_closed": True,
        },
        "bridge_outage_proof": bridge_outage,
        "enforcement_metrics": {
            "recommended_actions": action_counts,
            "adapter_counts": adapter_counts,
        },
        "metrics": metrics,
        "audit_metrics_summary": audit_metrics.get("summary", {}),
        "expectation_failures": expectation_failures,
        "preflight_failures": preflight_failures,
        "skipped_cases": skipped,
        "observations": observations,
        "notes": [
            "Email-send enforcement is scoped to fixture-approved internal pilot checks for email_send_guardrail.",
            "Bridge outage behavior is confirmed from the support SLA failure policy: irreversible support actions fail closed.",
            "This artifact does not certify external production readiness without live evidence connectors, deployment evidence, owner signoff, and measured pilot review.",
        ],
    }
    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    reviewer_report = pathlib.Path(args.reviewer_report)
    reviewer_report.parent.mkdir(parents=True, exist_ok=True)
    reviewer_report.write_text(_reviewer_report(result), encoding="utf-8")
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--support-fixtures", default=DEFAULT_SUPPORT_FIXTURES, help="Canonical support workflow fixture JSON.")
    parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    parser.add_argument("--sla-policy", default=DEFAULT_SLA_POLICY, help="Support SLA/failure policy JSON.")
    parser.add_argument("--audit-log", default=DEFAULT_AUDIT_LOG, help="Redacted enforced audit JSONL output.")
    parser.add_argument("--metrics-output", default=DEFAULT_METRICS, help="Audit metrics JSON output.")
    parser.add_argument("--reviewer-report", default=DEFAULT_REVIEWER_REPORT, help="Reviewer summary markdown output.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Measured enforced email pilot result JSON.")
    parser.add_argument("--append", action="store_true", help="Append to the audit log instead of starting fresh.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        result = run_enforced_email_pilot(args)
    except (SupportEnforcedEmailPilotError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AANA support enforced email pilot: FAIL - {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "PASS" if result["measurement_status"] == "accepted" else "NEEDS REVIEW"
        print(f"AANA support enforced email pilot: {status}")
        print(f"- Enforced email checks: {result['metrics']['enforced_email_checks']}")
        print(f"- Sends allowed: {result['metrics']['send_allowed_count']}")
        print(f"- Sends blocked: {result['metrics']['send_blocked_count']}")
        print(f"- Preflight failures: {result['metrics']['preflight_failure_count']}")
        print(f"- Bridge outage blocks sends: {result['metrics']['bridge_outage_blocks_sends']}")
        print(f"- P95 latency ms: {result['metrics']['p95_latency_ms']}")
        print(f"- Output: {args.output}")
    return 0 if result["measurement_status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
