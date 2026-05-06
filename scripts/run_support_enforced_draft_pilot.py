#!/usr/bin/env python3
"""Run the narrow enforced support-draft pilot."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api
from scripts import run_support_shadow_pilot


DEFAULT_SUPPORT_FIXTURES = ROOT / "examples" / "support_workflow_contract_examples.json"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_AUDIT_LOG = ROOT / "eval_outputs" / "audit" / "support-enforced-draft-internal-pilot.jsonl"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "pilots" / "support-enforced-draft-internal-pilot-results.json"
DEFAULT_METRICS = ROOT / "eval_outputs" / "pilots" / "support-enforced-draft-internal-pilot-metrics.json"
DEFAULT_REVIEWER_REPORT = ROOT / "eval_outputs" / "pilots" / "support-enforced-draft-internal-pilot-reviewer-report.md"
ENFORCED_DRAFT_ADAPTERS = ("support_reply", "crm_support_reply", "ticket_update_checker")
EXCLUDED_FROM_ENFORCEMENT = ("email_send_guardrail",)
SUPPORT_ACTIONS = ("accept", "revise", "retrieve", "ask", "defer", "refuse")


class SupportEnforcedDraftPilotError(RuntimeError):
    pass


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _increment(mapping, key):
    if key:
        mapping[key] = mapping.get(key, 0) + 1


def _p95(values):
    return run_support_shadow_pilot._p95(values)


def _expected(case, surface):
    return run_support_shadow_pilot._expected(case, surface)


def _matches_expected(result, expected):
    return run_support_shadow_pilot._matches_expected(result, expected)


def _gallery_entry(gallery, adapter_id):
    for entry in gallery.get("adapters", []):
        if entry.get("id") == adapter_id:
            return entry
    raise SupportEnforcedDraftPilotError(f"Adapter gallery is missing {adapter_id}.")


def _gallery_workflow_case(entry):
    adapter_id = entry["id"]
    return {
        "name": f"gallery_smoke_{adapter_id}",
        "title": f"Gallery smoke check for {adapter_id}",
        "surface": "workflow",
        "workflow_request": {
            "contract_version": "0.1",
            "workflow_id": f"internal-pilot-enforced-{adapter_id}",
            "adapter": adapter_id,
            "request": entry.get("prompt") or entry.get("workflow") or entry.get("title"),
            "candidate": entry.get("bad_candidate"),
            "evidence": [],
            "constraints": entry.get("best_for", []),
            "allowed_actions": list(SUPPORT_ACTIONS),
            "metadata": {
                "scenario": f"gallery_smoke_{adapter_id}",
                "policy_preset": "message_send",
                "internal_pilot_gallery_smoke": True,
                "enforced_support_draft_phase": True,
            },
        },
        "expected": {"workflow": entry.get("expected", {})},
    }


def enforced_cases(support_fixtures=DEFAULT_SUPPORT_FIXTURES, gallery_path=DEFAULT_GALLERY):
    cases = []
    skipped = []
    for case in run_support_shadow_pilot.support_cases(support_fixtures):
        for surface, key in (("workflow", "workflow_request"), ("agent_event", "agent_event")):
            payload = case[key]
            adapter_id = payload.get("adapter") or payload.get("adapter_id")
            if adapter_id in ENFORCED_DRAFT_ADAPTERS:
                cases.append({"case": case, "surface": surface, "key": key, "source": "support_fixture"})
            else:
                skipped.append(
                    {
                        "case": case.get("name"),
                        "surface": surface,
                        "adapter_id": adapter_id,
                        "reason": "adapter_outside_enforced_draft_allowlist",
                    }
                )

    covered = {
        (item["case"][item["key"]].get("adapter") or item["case"][item["key"]].get("adapter_id"))
        for item in cases
    }
    gallery = load_json(gallery_path)
    for adapter_id in ENFORCED_DRAFT_ADAPTERS:
        if adapter_id not in covered:
            cases.append(
                {
                    "case": _gallery_workflow_case(_gallery_entry(gallery, adapter_id)),
                    "surface": "workflow",
                    "key": "workflow_request",
                    "source": "gallery_smoke",
                }
            )
    return cases, skipped


def _enforced_result(check_fn, payload, gallery_path):
    started = time.perf_counter()
    result = check_fn(payload, gallery_path=gallery_path)
    latency_ms = (time.perf_counter() - started) * 1000
    result = dict(result)
    result["latency_ms"] = round(latency_ms, 3)
    result["execution_mode"] = "enforce"
    action = result.get("recommended_action")
    candidate_gate = result.get("candidate_gate")
    production_effect = "candidate_allowed" if action == "accept" and candidate_gate == "pass" else "original_candidate_blocked"
    result["production_decision"] = {
        "enforcement": "narrow_support_draft_blocking",
        "gate_decision": result.get("gate_decision"),
        "recommended_action": action,
        "candidate_gate": candidate_gate,
        "production_effect": production_effect,
        "safe_output_may_proceed": action in {"accept", "revise"},
        "human_review_required": action in {"ask", "defer", "refuse"},
    }
    return result, latency_ms


def _record_for_surface(surface, payload, result):
    if surface == "workflow":
        return agent_api.audit_workflow_check(payload, result=result)
    return agent_api.audit_event_check(payload, result=result)


def _case_expected(case, surface):
    expected = case.get("expected", {})
    return expected.get(surface, {}) if isinstance(expected, dict) else {}


def _expected_matches_for_gallery(result, expected):
    checks = {
        "gate_decision": result.get("gate_decision") == expected.get("gate_decision"),
        "recommended_action": result.get("recommended_action") == expected.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate") == expected.get("candidate_gate"),
        "aix_decision": result.get("aix", {}).get("decision") == expected.get("aix_decision"),
        "candidate_aix_decision": result.get("candidate_aix", {}).get("decision") == expected.get("candidate_aix_decision"),
    }
    return all(checks.values()), checks


def _reviewer_report(result):
    metrics = result["metrics"]
    lines = [
        "# AANA Support Enforced Draft Pilot Reviewer Report",
        "",
        f"- Enforced checks: {metrics['enforced_checks']}",
        f"- Original candidates blocked: {metrics['original_candidate_blocked_count']}",
        f"- Candidates allowed: {metrics['candidate_allowed_count']}",
        f"- Human review required: {metrics['human_review_required_count']}",
        f"- Excluded email-send checks: {metrics['excluded_email_send_checks']}",
        f"- Prohibited email enforcement count: {metrics['prohibited_email_enforcement_count']}",
        f"- P95 latency ms: {metrics['p95_latency_ms']}",
        "",
        "Email-send guardrail remains outside enforcement until recipient, attachment, approval, and bridge-failure paths are proven.",
        "",
    ]
    return "\n".join(lines)


def run_enforced_draft_pilot(args):
    cases, skipped = enforced_cases(args.support_fixtures, args.gallery)
    audit_log = pathlib.Path(args.audit_log)
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    if not args.append:
        audit_log.write_text("", encoding="utf-8")

    observations = []
    action_counts = {action: 0 for action in SUPPORT_ACTIONS}
    adapter_counts = {}
    expectation_failures = []
    latencies = []
    original_candidate_blocked = 0
    candidate_allowed = 0
    human_review_required = 0
    safe_output_available = 0
    prohibited_email_enforcement = 0

    for item in cases:
        case = item["case"]
        surface = item["surface"]
        key = item["key"]
        payload = case[key]
        adapter_id = payload.get("adapter") or payload.get("adapter_id")
        if adapter_id in EXCLUDED_FROM_ENFORCEMENT:
            prohibited_email_enforcement += 1
            continue
        if adapter_id not in ENFORCED_DRAFT_ADAPTERS:
            raise SupportEnforcedDraftPilotError(f"Unexpected adapter in enforced draft pilot: {adapter_id}")

        check_fn = agent_api.check_workflow_request if surface == "workflow" else agent_api.check_event
        result, latency_ms = _enforced_result(check_fn, payload, args.gallery)
        expected = _case_expected(case, surface)
        if item["source"] == "gallery_smoke":
            passed, expectation_checks = _expected_matches_for_gallery(result, expected)
        else:
            passed, expectation_checks = _matches_expected(result, expected)
        if not passed:
            expectation_failures.append({"case": case.get("name"), "surface": surface, "checks": expectation_checks})

        action = result.get("recommended_action")
        production = result.get("production_decision", {})
        _increment(action_counts, action)
        _increment(adapter_counts, adapter_id)
        latencies.append(latency_ms)
        if production.get("production_effect") == "original_candidate_blocked":
            original_candidate_blocked += 1
        if production.get("production_effect") == "candidate_allowed":
            candidate_allowed += 1
        if production.get("human_review_required"):
            human_review_required += 1
        if result.get("safe_response"):
            safe_output_available += 1

        record = _record_for_surface(surface, payload, result)
        record["enforcement"] = {
            "mode": "narrow_support_draft_blocking",
            "adapter_allowlist": list(ENFORCED_DRAFT_ADAPTERS),
            "excluded_adapters": list(EXCLUDED_FROM_ENFORCEMENT),
            "production_effect": production.get("production_effect"),
            "safe_output_may_proceed": production.get("safe_output_may_proceed"),
        }
        agent_api.append_audit_record(audit_log, record)
        observations.append(
            {
                "case": case.get("name"),
                "surface": surface,
                "source": item["source"],
                "adapter_id": adapter_id,
                "execution_mode": "enforce",
                "recommended_action": action,
                "candidate_gate": result.get("candidate_gate"),
                "production_effect": production.get("production_effect"),
                "safe_output_may_proceed": production.get("safe_output_may_proceed"),
                "human_review_required": production.get("human_review_required"),
                "latency_ms": round(latency_ms, 3),
                "expectations_passed": passed,
            }
        )

    metrics_output = pathlib.Path(args.metrics_output)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    audit_metrics = agent_api.export_audit_metrics_file(audit_log, output_path=metrics_output)
    total_checks = len(observations)
    excluded_email = sum(1 for item in skipped if item.get("adapter_id") in EXCLUDED_FROM_ENFORCEMENT)
    metrics = {
        "enforced_checks": total_checks,
        "original_candidate_blocked_count": original_candidate_blocked,
        "candidate_allowed_count": candidate_allowed,
        "safe_output_available_count": safe_output_available,
        "human_review_required_count": human_review_required,
        "excluded_checks": len(skipped),
        "excluded_email_send_checks": excluded_email,
        "prohibited_email_enforcement_count": prohibited_email_enforcement,
        "p95_latency_ms": _p95(latencies),
    }
    result = {
        "pilot_results_version": "0.1",
        "pilot_id": "aana-support-enforced-draft-internal-pilot",
        "environment": "internal-pilot",
        "execution_mode": "enforce",
        "enforcement": "narrow_support_draft_blocking",
        "measurement_status": "accepted"
        if not expectation_failures and not prohibited_email_enforcement and total_checks > 0
        else "needs_review",
        "enforced_adapters": list(ENFORCED_DRAFT_ADAPTERS),
        "excluded_from_enforcement": list(EXCLUDED_FROM_ENFORCEMENT),
        "source_fixture": str(pathlib.Path(args.support_fixtures)),
        "audit_log_ref": str(audit_log),
        "metrics_report_ref": str(metrics_output),
        "reviewer_report_ref": str(pathlib.Path(args.reviewer_report)),
        "summary": {
            "enforced_cases": total_checks,
            "skipped_cases": len(skipped),
            "expectation_failures": len(expectation_failures),
            "covered_enforced_adapters": sorted(adapter_counts),
        },
        "enforcement_metrics": {
            "recommended_actions": action_counts,
            "adapter_counts": adapter_counts,
        },
        "metrics": metrics,
        "audit_metrics_summary": audit_metrics.get("summary", {}),
        "expectation_failures": expectation_failures,
        "skipped_cases": skipped,
        "observations": observations,
        "notes": [
            "Narrow enforced phase blocks only original draft candidates for support_reply, crm_support_reply, and ticket_update_checker.",
            "Email-send guardrail remains excluded from enforcement until recipient, attachment, approval, and bridge-failure paths are proven.",
            "This artifact is scoped to approved internal support fixtures and gallery smoke checks; it is not production certification.",
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
    parser.add_argument("--audit-log", default=DEFAULT_AUDIT_LOG, help="Redacted enforced audit JSONL output.")
    parser.add_argument("--metrics-output", default=DEFAULT_METRICS, help="Audit metrics JSON output.")
    parser.add_argument("--reviewer-report", default=DEFAULT_REVIEWER_REPORT, help="Reviewer summary markdown output.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Measured enforced draft pilot result JSON.")
    parser.add_argument("--append", action="store_true", help="Append to the audit log instead of starting fresh.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        result = run_enforced_draft_pilot(args)
    except (SupportEnforcedDraftPilotError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AANA support enforced draft pilot: FAIL - {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "PASS" if result["measurement_status"] == "accepted" else "NEEDS REVIEW"
        print(f"AANA support enforced draft pilot: {status}")
        print(f"- Enforced checks: {result['metrics']['enforced_checks']}")
        print(f"- Original candidates blocked: {result['metrics']['original_candidate_blocked_count']}")
        print(f"- Candidates allowed: {result['metrics']['candidate_allowed_count']}")
        print(f"- Excluded email-send checks: {result['metrics']['excluded_email_send_checks']}")
        print(f"- Prohibited email enforcement: {result['metrics']['prohibited_email_enforcement_count']}")
        print(f"- P95 latency ms: {result['metrics']['p95_latency_ms']}")
        print(f"- Output: {args.output}")
    return 0 if result["measurement_status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
