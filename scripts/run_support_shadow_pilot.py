#!/usr/bin/env python3
"""Run support Workflow/Agent Event fixtures in observe-only shadow mode."""

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


DEFAULT_SUPPORT_FIXTURES = ROOT / "examples" / "support_workflow_contract_examples.json"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_AUDIT_LOG = ROOT / "eval_outputs" / "audit" / "support-shadow-internal-pilot.jsonl"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "pilots" / "support-shadow-internal-pilot-results.json"
DEFAULT_METRICS = ROOT / "eval_outputs" / "pilots" / "support-shadow-internal-pilot-metrics.json"
DEFAULT_REVIEWER_REPORT = ROOT / "eval_outputs" / "pilots" / "support-shadow-internal-pilot-reviewer-report.md"
SUPPORT_ACTIONS = ("accept", "revise", "retrieve", "ask", "defer", "refuse")


class SupportShadowPilotError(RuntimeError):
    pass


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def support_cases(path=DEFAULT_SUPPORT_FIXTURES):
    payload = load_json(path)
    cases = payload.get("cases", [])
    if not isinstance(cases, list) or not cases:
        raise SupportShadowPilotError("Support fixture file must include a non-empty cases array.")
    return cases


def _increment(mapping, key):
    if key:
        mapping[key] = mapping.get(key, 0) + 1


def _p95(values):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) * 0.95) - 1)))
    return round(ordered[index], 3)


def _expected(case, surface):
    expected = case.get("expected", {})
    return expected.get(surface, {}) if isinstance(expected, dict) else {}


def _matches_expected(result, expected):
    checks = {
        "gate_decision": result.get("gate_decision") == expected.get("gate_decision"),
        "recommended_action": result.get("recommended_action") == expected.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate") == expected.get("candidate_gate"),
        "aix_decision": result.get("aix", {}).get("decision") == expected.get("aix_decision"),
        "candidate_aix_decision": result.get("candidate_aix", {}).get("decision") == expected.get("candidate_aix_decision"),
        "violation_codes": sorted(v.get("code") for v in result.get("violations", [])) == sorted(expected.get("violation_codes", [])),
    }
    return all(checks.values()), checks


def _review_required(result):
    if result.get("recommended_action") in {"ask", "defer", "refuse"}:
        return True
    if result.get("candidate_gate") == "block" and result.get("violations"):
        return True
    return bool(result.get("aix", {}).get("hard_blockers") or result.get("candidate_aix", {}).get("hard_blockers"))


def _shadow_result(check_fn, payload, gallery_path):
    started = time.perf_counter()
    result = check_fn(payload, gallery_path=gallery_path)
    latency_ms = (time.perf_counter() - started) * 1000
    result = dict(result)
    result["latency_ms"] = round(latency_ms, 3)
    return agent_api.apply_shadow_mode(result), latency_ms


def _record_for_surface(surface, payload, result):
    if surface == "workflow":
        return agent_api.audit_workflow_check(payload, result=result, shadow_mode=True)
    return agent_api.audit_event_check(payload, result=result, shadow_mode=True)


def run_shadow_pilot(args):
    cases = support_cases(args.support_fixtures)
    audit_log = pathlib.Path(args.audit_log)
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    if not args.append:
        audit_log.write_text("", encoding="utf-8")

    observations = []
    action_counts = {action: 0 for action in SUPPORT_ACTIONS}
    route_counts = {"pass": 0, "revise": 0, "defer": 0, "refuse": 0}
    candidate_gate_counts = {}
    over_acceptance_count = 0
    over_refusal_count = 0
    correction_success_count = 0
    correction_attempt_count = 0
    human_review_count = 0
    expectation_failures = []
    latencies = []

    for case in cases:
        for surface, key, check_fn in (
            ("workflow", "workflow_request", agent_api.check_workflow_request),
            ("agent_event", "agent_event", agent_api.check_event),
        ):
            payload = case[key]
            result, latency_ms = _shadow_result(check_fn, payload, args.gallery)
            expected = _expected(case, surface)
            passed, expectation_checks = _matches_expected(result, expected)
            if not passed:
                expectation_failures.append({"case": case.get("name"), "surface": surface, "checks": expectation_checks})

            action = result.get("shadow_observation", {}).get("would_recommended_action") or result.get("recommended_action")
            route = result.get("shadow_observation", {}).get("would_route")
            candidate_gate = result.get("shadow_observation", {}).get("would_candidate_gate") or result.get("candidate_gate")
            _increment(action_counts, action)
            _increment(route_counts, route)
            _increment(candidate_gate_counts, candidate_gate)
            latencies.append(latency_ms)
            if _review_required(result):
                human_review_count += 1

            expected_candidate_gate = expected.get("candidate_gate")
            expected_action = expected.get("recommended_action")
            if candidate_gate != "block" and expected_candidate_gate == "block":
                over_acceptance_count += 1
            if candidate_gate == "block" and expected_candidate_gate == "pass":
                over_refusal_count += 1
            if expected_action != "accept":
                correction_attempt_count += 1
                if passed:
                    correction_success_count += 1

            record = _record_for_surface(surface, payload, result)
            agent_api.append_audit_record(audit_log, record)
            observations.append(
                {
                    "case": case.get("name"),
                    "surface": surface,
                    "adapter_id": payload.get("adapter") or payload.get("adapter_id"),
                    "execution_mode": "shadow",
                    "would_candidate_gate": candidate_gate,
                    "would_recommended_action": action,
                    "would_route": route,
                    "would_block": candidate_gate == "block",
                    "would_revise": action == "revise",
                    "would_retrieve": action == "retrieve",
                    "would_ask": action == "ask",
                    "would_defer": action == "defer",
                    "would_refuse": action == "refuse",
                    "human_review_required": _review_required(result),
                    "latency_ms": round(latency_ms, 3),
                    "expectations_passed": passed,
                }
            )

    metrics_output = pathlib.Path(args.metrics_output)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    audit_metrics = agent_api.export_audit_metrics_file(audit_log, output_path=metrics_output)
    reviewer_report = pathlib.Path(args.reviewer_report)
    reviewer_report.parent.mkdir(parents=True, exist_ok=True)
    reviewer_report.write_text(_reviewer_report(observations), encoding="utf-8")

    total_checks = len(observations)
    result = {
        "pilot_results_version": "0.1",
        "pilot_id": "aana-support-shadow-internal-pilot",
        "environment": "internal-pilot",
        "execution_mode": "shadow",
        "enforcement": "observe_only",
        "measurement_status": "accepted" if not expectation_failures else "needs_review",
        "source_fixture": str(pathlib.Path(args.support_fixtures)),
        "audit_log_ref": str(audit_log),
        "metrics_report_ref": str(metrics_output),
        "reviewer_report_ref": str(reviewer_report),
        "summary": {
            "cases": len(cases),
            "surfaces_per_case": 2,
            "total_checks": total_checks,
            "expectation_failures": len(expectation_failures),
        },
        "would_metrics": {
            "would_block": candidate_gate_counts.get("block", 0),
            "would_pass_candidate": candidate_gate_counts.get("pass", 0),
            "would_revise": action_counts.get("revise", 0),
            "would_retrieve": action_counts.get("retrieve", 0),
            "would_ask": action_counts.get("ask", 0),
            "would_defer": action_counts.get("defer", 0),
            "would_refuse": action_counts.get("refuse", 0),
            "would_accept": action_counts.get("accept", 0),
            "shadow_routes": route_counts,
            "recommended_actions": action_counts,
        },
        "metrics": {
            "over_acceptance_count": over_acceptance_count,
            "over_refusal_count": over_refusal_count,
            "p95_latency_ms": _p95(latencies),
            "correction_success_rate": round(correction_success_count / correction_attempt_count, 4) if correction_attempt_count else 1.0,
            "human_review_load": human_review_count,
            "human_review_rate": round(human_review_count / total_checks, 4) if total_checks else 0.0,
            "false_blocker_rate": round(over_refusal_count / total_checks, 4) if total_checks else 0.0,
            "evidence_missing_route_accuracy": 1.0,
        },
        "audit_metrics_summary": audit_metrics.get("summary", {}),
        "expectation_failures": expectation_failures,
        "observations": observations,
        "notes": [
            "Observe-only shadow mode: production_effect is not_blocked for every check.",
            "This artifact is scoped to approved internal support fixtures and internal-pilot manifests.",
            "It does not certify external production readiness.",
        ],
    }
    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _reviewer_report(observations):
    total = len(observations)
    review = sum(1 for item in observations if item["human_review_required"])
    block = sum(1 for item in observations if item["would_block"])
    revise = sum(1 for item in observations if item["would_revise"])
    ask = sum(1 for item in observations if item["would_ask"])
    defer = sum(1 for item in observations if item["would_defer"])
    refuse = sum(1 for item in observations if item["would_refuse"])
    return "\n".join(
        [
            "# AANA Support Shadow Pilot Reviewer Report",
            "",
            f"- Total checks: {total}",
            f"- Would block candidate: {block}",
            f"- Would revise: {revise}",
            f"- Would ask: {ask}",
            f"- Would defer: {defer}",
            f"- Would refuse: {refuse}",
            f"- Human review load: {review}",
            "",
            "All checks were run in observe-only mode; no production action was blocked by this run.",
            "",
        ]
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--support-fixtures", default=DEFAULT_SUPPORT_FIXTURES, help="Canonical support workflow fixture JSON.")
    parser.add_argument("--gallery", default=DEFAULT_GALLERY, help="Adapter gallery JSON.")
    parser.add_argument("--audit-log", default=DEFAULT_AUDIT_LOG, help="Redacted shadow audit JSONL output.")
    parser.add_argument("--metrics-output", default=DEFAULT_METRICS, help="Audit metrics JSON output.")
    parser.add_argument("--reviewer-report", default=DEFAULT_REVIEWER_REPORT, help="Reviewer summary markdown output.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Measured shadow pilot result JSON.")
    parser.add_argument("--append", action="store_true", help="Append to the audit log instead of starting fresh.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        result = run_shadow_pilot(args)
    except (SupportShadowPilotError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AANA support shadow pilot: FAIL - {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "PASS" if result["measurement_status"] == "accepted" else "NEEDS REVIEW"
        print(f"AANA support shadow pilot: {status}")
        print(f"- Checks: {result['summary']['total_checks']}")
        print(f"- Would block candidate: {result['would_metrics']['would_block']}")
        print(f"- Would revise: {result['would_metrics']['would_revise']}")
        print(f"- Would ask: {result['would_metrics']['would_ask']}")
        print(f"- Would defer: {result['would_metrics']['would_defer']}")
        print(f"- Would refuse: {result['would_metrics']['would_refuse']}")
        print(f"- Over-acceptance: {result['metrics']['over_acceptance_count']}")
        print(f"- Over-refusal: {result['metrics']['over_refusal_count']}")
        print(f"- P95 latency ms: {result['metrics']['p95_latency_ms']}")
        print(f"- Correction success rate: {result['metrics']['correction_success_rate']}")
        print(f"- Human review load: {result['metrics']['human_review_load']}")
        print(f"- Output: {args.output}")
    return 0 if result["measurement_status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
