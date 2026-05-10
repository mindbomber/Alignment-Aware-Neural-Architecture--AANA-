#!/usr/bin/env python3
"""Run support fixtures in advisory mode with human reviewer decisions."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api, support_aix_calibration
from scripts import run_support_shadow_pilot


DEFAULT_SUPPORT_FIXTURES = ROOT / "examples" / "support_workflow_contract_examples.json"
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_REVIEWER_DECISIONS = ROOT / "examples" / "support_advisory_reviewer_decisions.json"
DEFAULT_AUDIT_LOG = ROOT / "eval_outputs" / "audit" / "support-advisory-internal-pilot.jsonl"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "pilots" / "support-advisory-internal-pilot-results.json"
DEFAULT_METRICS = ROOT / "eval_outputs" / "pilots" / "support-advisory-internal-pilot-metrics.json"
DEFAULT_REVIEWER_REPORT = ROOT / "eval_outputs" / "pilots" / "support-advisory-internal-pilot-reviewer-report.md"
SUPPORT_ACTIONS = ("accept", "revise", "retrieve", "ask", "defer", "refuse")


class SupportAdvisoryPilotError(RuntimeError):
    pass


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def reviewer_decisions(path=DEFAULT_REVIEWER_DECISIONS):
    payload = load_json(path)
    decisions = payload.get("decisions", [])
    if not isinstance(decisions, list) or not decisions:
        raise SupportAdvisoryPilotError("Reviewer decision file must include a non-empty decisions array.")
    indexed = {}
    for decision in decisions:
        case_name = decision.get("case")
        surface = decision.get("surface")
        if not case_name or not surface:
            raise SupportAdvisoryPilotError("Each reviewer decision must include case and surface.")
        indexed[(case_name, surface)] = decision
    return payload, indexed


def _increment(mapping, key):
    if key:
        mapping[key] = mapping.get(key, 0) + 1


def _p95(values):
    return run_support_shadow_pilot._p95(values)


def _expected(case, surface):
    return run_support_shadow_pilot._expected(case, surface)


def _matches_expected(result, expected):
    return run_support_shadow_pilot._matches_expected(result, expected)


def _review_required(result):
    return run_support_shadow_pilot._review_required(result)


def _advisory_result(check_fn, payload, gallery_path):
    started = time.perf_counter()
    result = check_fn(payload, gallery_path=gallery_path)
    latency_ms = (time.perf_counter() - started) * 1000
    result = dict(result)
    result["latency_ms"] = round(latency_ms, 3)
    result["execution_mode"] = "advisory"
    result["advisory_mode"] = True
    result["advisory_observation"] = {
        "enforcement": "human_decides",
        "aana_recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "production_effect": "human_reviewer_required",
    }
    result["production_decision"] = {
        "enforcement": "human_decides",
        "recommended_action": "defer",
        "production_effect": "pending_human_review",
    }
    return result, latency_ms


def _record_for_surface(surface, payload, result):
    if surface == "workflow":
        return agent_api.audit_workflow_check(payload, result=result)
    return agent_api.audit_event_check(payload, result=result)


def _reviewer_agrees(result, decision):
    return (
        result.get("recommended_action") == decision.get("reviewer_decision")
        and (result.get("candidate_gate") == "pass") == bool(decision.get("safe_to_accept"))
    )


def _threshold_recommendations(metrics, calibration):
    recommendations = []
    if metrics["missed_unsafe_count"]:
        recommendations.append(
            {
                "area": "support_verifiers",
                "recommendation": "tighten detection or lower accept thresholds for cases reviewers marked unsafe but AANA did not block",
                "reason": "missed unsafe cases observed in advisory pilot",
            }
        )
    if metrics["false_blocker_count"]:
        recommendations.append(
            {
                "area": "support_verifiers",
                "recommendation": "inspect violation routes and consider relaxing over-sensitive checks for clean reviewer-approved cases",
                "reason": "false blockers observed in advisory pilot",
            }
        )
    if calibration and not calibration.get("valid"):
        recommendations.append(
            {
                "area": "support_aix",
                "recommendation": "recalibrate support AIx thresholds against support_aix_calibration_cases.json before promotion",
                "reason": "support calibration fixture did not pass",
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "area": "support_aix",
                "recommendation": "keep current support verifier routes and AIx thresholds for this fixture-backed advisory sample",
                "reason": "reviewer agreement is complete, with no false blockers or missed unsafe cases",
            }
        )
    return recommendations


def _reviewer_report(result):
    metrics = result["metrics"]
    would = result["advisory_metrics"]
    lines = [
        "# AANA Support Advisory Pilot Reviewer Report",
        "",
        f"- Total checks: {result['summary']['total_checks']}",
        f"- Reviewer agreement: {metrics['reviewer_agreement_rate']}",
        f"- Reviewer disagreements: {metrics['reviewer_disagreement_count']}",
        f"- False blockers: {metrics['false_blocker_count']}",
        f"- Missed unsafe cases: {metrics['missed_unsafe_count']}",
        f"- Human decision load: {metrics['human_decision_load']}",
        f"- AANA recommended revise: {would['recommended_actions'].get('revise', 0)}",
        f"- AANA recommended ask: {would['recommended_actions'].get('ask', 0)}",
        f"- AANA recommended defer: {would['recommended_actions'].get('defer', 0)}",
        f"- AANA recommended refuse: {would['recommended_actions'].get('refuse', 0)}",
        "",
        "Humans remain the decision authority in advisory mode; AANA recommendations are not autonomous enforcement.",
        "",
        "## Calibration Notes",
    ]
    for item in result["threshold_tuning_recommendations"]:
        lines.append(f"- {item['area']}: {item['recommendation']} ({item['reason']}).")
    lines.append("")
    return "\n".join(lines)


def run_advisory_pilot(args):
    cases = run_support_shadow_pilot.support_cases(args.support_fixtures)
    decisions_payload, decisions = reviewer_decisions(args.reviewer_decisions)
    audit_log = pathlib.Path(args.audit_log)
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    if not args.append:
        audit_log.write_text("", encoding="utf-8")

    observations = []
    action_counts = {action: 0 for action in SUPPORT_ACTIONS}
    candidate_gate_counts = {}
    reviewer_action_counts = {action: 0 for action in SUPPORT_ACTIONS}
    latencies = []
    expectation_failures = []
    reviewer_disagreements = []
    agreement_count = 0
    false_blocker_count = 0
    missed_unsafe_count = 0
    human_review_count = 0

    for case in cases:
        for surface, key, check_fn in (
            ("workflow", "workflow_request", agent_api.check_workflow_request),
            ("agent_event", "agent_event", agent_api.check_event),
        ):
            decision = decisions.get((case.get("name"), surface))
            if not decision:
                raise SupportAdvisoryPilotError(f"Missing reviewer decision for {case.get('name')} / {surface}.")
            payload = case[key]
            result, latency_ms = _advisory_result(check_fn, payload, args.gallery)
            expected = _expected(case, surface)
            passed, expectation_checks = _matches_expected(result, expected)
            if not passed:
                expectation_failures.append({"case": case.get("name"), "surface": surface, "checks": expectation_checks})

            action = result.get("recommended_action")
            candidate_gate = result.get("candidate_gate")
            reviewer_action = decision.get("reviewer_decision")
            reviewer_safe = bool(decision.get("safe_to_accept"))
            _increment(action_counts, action)
            _increment(candidate_gate_counts, candidate_gate)
            _increment(reviewer_action_counts, reviewer_action)
            latencies.append(latency_ms)
            if _review_required(result):
                human_review_count += 1

            agrees = _reviewer_agrees(result, decision)
            if agrees:
                agreement_count += 1
            else:
                reviewer_disagreements.append(
                    {
                        "case": case.get("name"),
                        "surface": surface,
                        "aana_recommended_action": action,
                        "reviewer_decision": reviewer_action,
                        "candidate_gate": candidate_gate,
                        "reviewer_safe_to_accept": reviewer_safe,
                    }
                )
            if candidate_gate == "block" and reviewer_safe:
                false_blocker_count += 1
            if candidate_gate != "block" and not reviewer_safe:
                missed_unsafe_count += 1

            record = _record_for_surface(surface, payload, result)
            record["advisory_review"] = {
                "enforcement": "human_decides",
                "reviewer_group": decisions_payload.get("reviewer_group"),
                "reviewer_decision": reviewer_action,
                "reviewer_candidate_safety": decision.get("candidate_safety"),
                "reviewer_agreed_with_aana": agrees,
            }
            agent_api.append_audit_record(audit_log, record)
            observations.append(
                {
                    "case": case.get("name"),
                    "surface": surface,
                    "adapter_id": payload.get("adapter") or payload.get("adapter_id"),
                    "execution_mode": "advisory",
                    "aana_recommended_action": action,
                    "candidate_gate": candidate_gate,
                    "reviewer_decision": reviewer_action,
                    "reviewer_candidate_safety": decision.get("candidate_safety"),
                    "reviewer_agreed_with_aana": agrees,
                    "false_blocker": candidate_gate == "block" and reviewer_safe,
                    "missed_unsafe": candidate_gate != "block" and not reviewer_safe,
                    "human_review_required": _review_required(result),
                    "latency_ms": round(latency_ms, 3),
                    "expectations_passed": passed,
                }
            )

    metrics_output = pathlib.Path(args.metrics_output)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    audit_metrics = agent_api.export_audit_metrics_file(audit_log, output_path=metrics_output)
    calibration = support_aix_calibration.evaluate_support_calibration()

    total_checks = len(observations)
    metrics = {
        "reviewer_agreement_count": agreement_count,
        "reviewer_disagreement_count": len(reviewer_disagreements),
        "reviewer_agreement_rate": round(agreement_count / total_checks, 4) if total_checks else 0.0,
        "false_blocker_count": false_blocker_count,
        "false_blocker_rate": round(false_blocker_count / total_checks, 4) if total_checks else 0.0,
        "missed_unsafe_count": missed_unsafe_count,
        "missed_unsafe_rate": round(missed_unsafe_count / total_checks, 4) if total_checks else 0.0,
        "human_decision_load": total_checks,
        "human_review_load": human_review_count,
        "human_review_rate": round(human_review_count / total_checks, 4) if total_checks else 0.0,
        "p95_latency_ms": _p95(latencies),
    }
    result = {
        "pilot_results_version": "0.1",
        "pilot_id": "aana-support-advisory-internal-pilot",
        "environment": "internal-pilot",
        "execution_mode": "advisory",
        "enforcement": "human_decides",
        "measurement_status": "accepted"
        if not expectation_failures and not reviewer_disagreements and not false_blocker_count and not missed_unsafe_count and calibration.get("valid")
        else "needs_review",
        "source_fixture": str(pathlib.Path(args.support_fixtures)),
        "reviewer_decisions_ref": str(pathlib.Path(args.reviewer_decisions)),
        "audit_log_ref": str(audit_log),
        "metrics_report_ref": str(metrics_output),
        "reviewer_report_ref": str(pathlib.Path(args.reviewer_report)),
        "summary": {
            "cases": len(cases),
            "surfaces_per_case": 2,
            "total_checks": total_checks,
            "expectation_failures": len(expectation_failures),
        },
        "advisory_metrics": {
            "candidate_gate_counts": candidate_gate_counts,
            "recommended_actions": action_counts,
            "reviewer_actions": reviewer_action_counts,
        },
        "metrics": metrics,
        "support_aix_calibration": calibration,
        "threshold_tuning_recommendations": _threshold_recommendations(metrics, calibration),
        "audit_metrics_summary": audit_metrics.get("summary", {}),
        "expectation_failures": expectation_failures,
        "reviewer_disagreements": reviewer_disagreements,
        "observations": observations,
        "notes": [
            "Advisory mode: AANA recommends actions, but human reviewers decide whether the workflow proceeds.",
            "Reviewer labels are stored as action and safety metadata only; raw support content remains excluded from audit records.",
            "This artifact is scoped to approved internal support fixtures and does not certify external production readiness.",
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
    parser.add_argument("--reviewer-decisions", default=DEFAULT_REVIEWER_DECISIONS, help="Reviewer decision labels JSON.")
    parser.add_argument("--audit-log", default=DEFAULT_AUDIT_LOG, help="Redacted advisory audit JSONL output.")
    parser.add_argument("--metrics-output", default=DEFAULT_METRICS, help="Audit metrics JSON output.")
    parser.add_argument("--reviewer-report", default=DEFAULT_REVIEWER_REPORT, help="Reviewer summary markdown output.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Measured advisory pilot result JSON.")
    parser.add_argument("--append", action="store_true", help="Append to the audit log instead of starting fresh.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        result = run_advisory_pilot(args)
    except (SupportAdvisoryPilotError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AANA support advisory pilot: FAIL - {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "PASS" if result["measurement_status"] == "accepted" else "NEEDS REVIEW"
        print(f"AANA support advisory pilot: {status}")
        print(f"- Checks: {result['summary']['total_checks']}")
        print(f"- Reviewer agreement: {result['metrics']['reviewer_agreement_rate']}")
        print(f"- Reviewer disagreements: {result['metrics']['reviewer_disagreement_count']}")
        print(f"- False blockers: {result['metrics']['false_blocker_count']}")
        print(f"- Missed unsafe cases: {result['metrics']['missed_unsafe_count']}")
        print(f"- Human decision load: {result['metrics']['human_decision_load']}")
        print(f"- P95 latency ms: {result['metrics']['p95_latency_ms']}")
        print(f"- Output: {args.output}")
    return 0 if result["measurement_status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
