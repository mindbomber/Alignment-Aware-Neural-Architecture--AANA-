#!/usr/bin/env python
"""Run an AANA domain adapter against one prompt.

The first executable adapter is the travel-planning adapter. Other adapter JSON
files still load and produce a structured result, but they need a domain-specific
runner before the CLI can verify and repair their constraints.
"""

import argparse
import json
import pathlib
import sys
from collections import defaultdict


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from constraint_tools import is_clarification_request, run_constraint_tools
from run_aana_evals import deterministic_repair


VIOLATION_TO_CONSTRAINT = {
    "explicit_total_over_cap": "total_budget_cap",
    "missing_explicit_total": "total_budget_cap",
    "budget_cap_violation": "total_budget_cap",
    "missing_budget_accounting": "total_budget_cap",
    "paid_item_cap_violation": "paid_ticket_cap",
    "paid_activity_cap_violation": "paid_ticket_cap",
    "public_transit_only_violation": "public_transit_only",
    "forbidden_transport_violation": "public_transit_only",
    "car_constraint_violation": "public_transit_only",
    "missing_lunch": "required_lunch",
    "incomplete_day_plan": "required_day_count",
}


def load_adapter(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        adapter = json.load(handle)
    if not isinstance(adapter, dict):
        raise ValueError("Adapter file must contain a JSON object.")
    if not adapter.get("adapter_name"):
        raise ValueError("Adapter file is missing adapter_name.")
    return adapter


def is_travel_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return "travel" in haystack or "itinerary" in haystack or "outing" in haystack


def make_task(adapter, prompt):
    if is_travel_adapter(adapter):
        task_type = "budgeted_travel_planner"
        block = "application_demo"
    else:
        task_type = "domain_adapter"
        block = "adapter"

    return {
        "id": "adapter_prompt",
        "block": block,
        "task_type": task_type,
        "capability_prompt": "Answer usefully while preserving every hard adapter constraint.",
        "low_pressure_prompt": prompt,
        "high_pressure_prompt": prompt,
        "reference_notes": "Adapter constraints: "
        + "; ".join(c.get("id", "") for c in adapter.get("constraints", [])),
    }


def gate_from_report(report):
    return "pass" if not report.get("violations") else "block"


def action_from_answer_and_report(answer, report, fallback="accept"):
    if answer and is_clarification_request(answer):
        return "ask"
    if report.get("violations"):
        return "revise"
    return fallback


def constraint_results(adapter, report):
    failures = defaultdict(list)
    for violation in report.get("violations", []):
        constraint_id = VIOLATION_TO_CONSTRAINT.get(violation.get("code"), "unmapped_constraint")
        failures[constraint_id].append(violation)

    results = []
    for constraint in adapter.get("constraints", []):
        constraint_id = constraint.get("id", "")
        mapped_failures = failures.get(constraint_id, [])
        results.append(
            {
                "id": constraint_id,
                "layer": constraint.get("layer"),
                "hard": bool(constraint.get("hard")),
                "status": "fail" if mapped_failures else "pass",
                "description": constraint.get("description", ""),
                "violations": mapped_failures,
            }
        )

    for violation in failures.get("unmapped_constraint", []):
        results.append(
            {
                "id": "unmapped_constraint",
                "layer": None,
                "hard": True,
                "status": "fail",
                "description": "A deterministic tool violation did not map to an adapter constraint.",
                "violations": [violation],
            }
        )

    return results


def unsupported_result(adapter, prompt, candidate):
    return {
        "adapter": adapter_summary(adapter),
        "prompt": prompt,
        "candidate_answer": candidate,
        "final_answer": candidate,
        "recommended_action": "defer",
        "gate_decision": "needs_adapter_implementation",
        "constraint_results": [
            {
                "id": c.get("id", ""),
                "layer": c.get("layer"),
                "hard": bool(c.get("hard")),
                "status": "unknown",
                "description": c.get("description", ""),
                "violations": [],
            }
            for c in adapter.get("constraints", [])
        ],
        "tool_report": None,
        "caveats": [
            "This adapter contract loaded successfully, but no deterministic runner is implemented for its domain yet."
        ],
    }


def adapter_summary(adapter):
    return {
        "name": adapter.get("adapter_name"),
        "version": adapter.get("version"),
        "domain": adapter.get("domain", {}).get("name"),
    }


def run_adapter(adapter, prompt, candidate=None):
    if not is_travel_adapter(adapter):
        return unsupported_result(adapter, prompt, candidate)

    task = make_task(adapter, prompt)
    caveats = list(adapter.get("evaluation", {}).get("known_caveats", []))

    if candidate:
        candidate_report = run_constraint_tools(task, prompt, candidate)
        if candidate_report["violations"]:
            final_answer = deterministic_repair(task, prompt, "hybrid_gate_direct")
            final_report = run_constraint_tools(task, prompt, final_answer)
            return {
                "adapter": adapter_summary(adapter),
                "prompt": prompt,
                "candidate_answer": candidate,
                "candidate_gate": gate_from_report(candidate_report),
                "final_answer": final_answer,
                "gate_decision": gate_from_report(final_report),
                "recommended_action": action_from_answer_and_report(final_answer, final_report, "revise"),
                "constraint_results": constraint_results(adapter, final_report),
                "candidate_tool_report": candidate_report,
                "tool_report": final_report,
                "caveats": caveats,
            }

        return {
            "adapter": adapter_summary(adapter),
            "prompt": prompt,
            "candidate_answer": candidate,
            "candidate_gate": "pass",
            "final_answer": candidate,
            "gate_decision": "pass",
            "recommended_action": "accept",
            "constraint_results": constraint_results(adapter, candidate_report),
            "candidate_tool_report": candidate_report,
            "tool_report": candidate_report,
            "caveats": caveats,
        }

    final_answer = deterministic_repair(task, prompt, "hybrid_gate_direct")
    final_report = run_constraint_tools(task, prompt, final_answer)
    return {
        "adapter": adapter_summary(adapter),
        "prompt": prompt,
        "candidate_answer": None,
        "final_answer": final_answer,
        "gate_decision": gate_from_report(final_report),
        "recommended_action": action_from_answer_and_report(final_answer, final_report),
        "constraint_results": constraint_results(adapter, final_report),
        "tool_report": final_report,
        "caveats": caveats,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Run an AANA domain adapter against one prompt.")
    parser.add_argument("--adapter", required=True, help="Path to an adapter JSON file.")
    parser.add_argument("--prompt", required=True, help="User prompt to test.")
    parser.add_argument("--candidate", default=None, help="Optional candidate answer to verify and repair.")
    parser.add_argument("--candidate-file", default=None, help="Read optional candidate answer from a text file.")
    return parser.parse_args()


def main():
    args = parse_args()
    candidate = args.candidate
    if args.candidate_file:
        candidate = pathlib.Path(args.candidate_file).read_text(encoding="utf-8")

    adapter = load_adapter(args.adapter)
    result = run_adapter(adapter, args.prompt, candidate)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
