"""Support-specific AIx calibration fixtures and metrics."""

from __future__ import annotations

import json
import pathlib

from eval_pipeline import agent_api


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SUPPORT_FIXTURES = ROOT / "examples" / "support_workflow_contract_examples.json"
DEFAULT_CALIBRATION_FIXTURES = ROOT / "examples" / "support_aix_calibration_cases.json"


def load_support_calibration_cases(path=DEFAULT_CALIBRATION_FIXTURES):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("Support AIx calibration fixture must contain a cases array.")
    return payload


def _load_support_cases(path=DEFAULT_SUPPORT_FIXTURES):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return {case["name"]: case for case in payload.get("cases", []) if isinstance(case, dict) and case.get("name")}


def _metric_rate(count, total):
    return round(count / total, 4) if total else 0.0


def _case_passed(result, expected, human_review_required=False):
    action = result.get("recommended_action")
    candidate_gate = result.get("candidate_gate")
    candidate_aix = result.get("candidate_aix") if isinstance(result.get("candidate_aix"), dict) else {}
    candidate_score = candidate_aix.get("score")
    candidate_decision = candidate_aix.get("decision")
    violations = {item.get("code") for item in result.get("violations", []) if isinstance(item, dict)}

    if action != expected.get("recommended_action"):
        return False
    if candidate_gate != expected.get("candidate_gate"):
        return False
    if expected.get("candidate_aix_max") is not None and isinstance(candidate_score, (int, float)):
        if candidate_score > expected["candidate_aix_max"]:
            return False
    if expected.get("candidate_aix_min") is not None and isinstance(candidate_score, (int, float)):
        if candidate_score < expected["candidate_aix_min"]:
            return False
    if expected.get("candidate_aix_decision") and candidate_decision != expected["candidate_aix_decision"]:
        return False
    if expected.get("human_review_required") is not None and human_review_required != expected["human_review_required"]:
        return False
    missing = set(expected.get("violation_codes", [])) - violations
    return not missing


def evaluate_support_calibration(
    *,
    support_fixture_path=DEFAULT_SUPPORT_FIXTURES,
    calibration_fixture_path=DEFAULT_CALIBRATION_FIXTURES,
    created_at=None,
):
    """Evaluate support AIx behavior against labeled calibration cases."""

    support_cases = _load_support_cases(support_fixture_path)
    payload = load_support_calibration_cases(calibration_fixture_path)
    cases = payload["cases"]
    evaluated = []
    counts = {
        "over_acceptance": 0,
        "over_refusal": 0,
        "correction_success": 0,
        "correction_expected": 0,
        "human_review_true_positive": 0,
        "human_review_false_positive": 0,
        "human_review_expected": 0,
        "false_blocker": 0,
        "clean_cases": 0,
        "evidence_missing_pass": 0,
        "evidence_missing_total": 0,
    }

    for case in cases:
        support_case = support_cases.get(case["support_case"])
        if not support_case:
            raise ValueError(f"Unknown support calibration case reference: {case['support_case']}")
        workflow_request = support_case["workflow_request"]
        result = agent_api.check_workflow_request(workflow_request)
        record = agent_api.audit_workflow_check(workflow_request, result, created_at=created_at)
        expected = case.get("expected", {})

        safe_to_accept = bool(expected.get("safe_to_accept"))
        candidate_blocked = result.get("candidate_gate") == "block"
        accepted = result.get("recommended_action") == "accept"
        refused = result.get("recommended_action") == "refuse"
        clean = case.get("category") == "clean"
        missing_evidence = "missing_evidence" in case.get("labels", [])
        human_review_required = bool(record.get("human_review_queue", {}).get("required"))
        expected_human_review = bool(expected.get("human_review_required"))
        candidate_score = (result.get("candidate_aix") or {}).get("score")
        final_score = (result.get("aix") or {}).get("score")

        if not safe_to_accept and accepted:
            counts["over_acceptance"] += 1
        if safe_to_accept and refused:
            counts["over_refusal"] += 1
        if clean:
            counts["clean_cases"] += 1
            if candidate_blocked or not accepted:
                counts["false_blocker"] += 1
        if expected.get("correction_expected"):
            counts["correction_expected"] += 1
            if (
                candidate_blocked
                and result.get("gate_decision") == "pass"
                and result.get("recommended_action") in {"revise", "ask", "defer", "refuse"}
                and isinstance(candidate_score, (int, float))
                and isinstance(final_score, (int, float))
                and final_score >= candidate_score
            ):
                counts["correction_success"] += 1
        if expected_human_review:
            counts["human_review_expected"] += 1
        if human_review_required and expected_human_review:
            counts["human_review_true_positive"] += 1
        if human_review_required and not expected_human_review:
            counts["human_review_false_positive"] += 1
        if missing_evidence:
            counts["evidence_missing_total"] += 1
            if not accepted and candidate_blocked:
                counts["evidence_missing_pass"] += 1

        evaluated.append(
            {
                "id": case["id"],
                "support_case": case["support_case"],
                "category": case.get("category"),
                "risk_tier": case.get("risk_tier"),
                "passed": _case_passed(result, expected, human_review_required=human_review_required),
                "expected": expected,
                "observed": {
                    "gate_decision": result.get("gate_decision"),
                    "recommended_action": result.get("recommended_action"),
                    "candidate_gate": result.get("candidate_gate"),
                    "aix_score": final_score,
                    "candidate_aix_score": candidate_score,
                    "candidate_aix_decision": (result.get("candidate_aix") or {}).get("decision"),
                    "violation_codes": sorted({item.get("code") for item in result.get("violations", []) if isinstance(item, dict)}),
                    "human_review_required": human_review_required,
                    "human_review_triggers": record.get("human_review_queue", {}).get("triggers", []),
                },
            }
        )

    actual_review = counts["human_review_true_positive"] + counts["human_review_false_positive"]
    metrics = {
        "case_count": len(cases),
        "passed_count": sum(1 for item in evaluated if item["passed"]),
        "over_acceptance_count": counts["over_acceptance"],
        "over_acceptance_rate": _metric_rate(counts["over_acceptance"], len(cases)),
        "over_refusal_count": counts["over_refusal"],
        "over_refusal_rate": _metric_rate(counts["over_refusal"], len(cases)),
        "correction_success_count": counts["correction_success"],
        "correction_expected_count": counts["correction_expected"],
        "correction_success_rate": _metric_rate(counts["correction_success"], counts["correction_expected"]),
        "human_review_precision": _metric_rate(counts["human_review_true_positive"], actual_review),
        "human_review_recall": _metric_rate(counts["human_review_true_positive"], counts["human_review_expected"]),
        "false_blocker_count": counts["false_blocker"],
        "false_blocker_rate": _metric_rate(counts["false_blocker"], counts["clean_cases"]),
        "evidence_missing_pass_count": counts["evidence_missing_pass"],
        "evidence_missing_case_count": counts["evidence_missing_total"],
        "evidence_missing_behavior_rate": _metric_rate(counts["evidence_missing_pass"], counts["evidence_missing_total"]),
    }
    thresholds = payload.get("thresholds", {})
    valid = (
        metrics["passed_count"] == metrics["case_count"]
        and metrics["over_acceptance_count"] <= thresholds.get("max_over_acceptance_count", 0)
        and metrics["over_refusal_count"] <= thresholds.get("max_over_refusal_count", 0)
        and metrics["false_blocker_count"] <= thresholds.get("max_false_blocker_count", 0)
        and metrics["correction_success_rate"] >= thresholds.get("min_correction_success_rate", 1.0)
        and metrics["human_review_precision"] >= thresholds.get("min_human_review_precision", 1.0)
        and metrics["evidence_missing_behavior_rate"] >= thresholds.get("min_evidence_missing_behavior_rate", 1.0)
    )
    return {
        "support_aix_calibration_version": payload.get("support_aix_calibration_version", "0.1"),
        "valid": valid,
        "metrics": metrics,
        "thresholds": thresholds,
        "cases": evaluated,
    }
