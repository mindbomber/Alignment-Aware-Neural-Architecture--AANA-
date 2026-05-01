#!/usr/bin/env python
"""Validate an AANA domain adapter JSON file."""

import argparse
import json
import pathlib
import sys


ALLOWED_LAYERS = {"P", "B", "C", "F"}
ALLOWED_VERIFIERS = {"deterministic", "retrieval", "model_judge", "human_review"}
ALLOWED_ACTIONS = {"accept", "revise", "retrieve", "ask", "refuse", "defer"}
POLICY_KEYS = [
    "accept_when",
    "revise_when",
    "retrieve_when",
    "ask_when",
    "refuse_when",
    "defer_when",
]
EVALUATION_KEYS = [
    "capability_metric",
    "alignment_metric",
    "gap_metric",
    "pass_condition",
    "known_caveats",
]
PLACEHOLDER_MARKERS = ["replace_with", "describe what", "describe exactly", "describe how", "describe the", "state the constraint", "constraint_id"]


def load_adapter(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        adapter = json.load(handle)
    if not isinstance(adapter, dict):
        raise ValueError("Adapter file must contain a JSON object.")
    return adapter


def has_text(value):
    return isinstance(value, str) and bool(value.strip())


def is_nonempty_list(value):
    return isinstance(value, list) and bool(value)


def contains_placeholder(value):
    if isinstance(value, str):
        text = value.lower()
        return any(marker in text for marker in PLACEHOLDER_MARKERS)
    if isinstance(value, list):
        return any(contains_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(contains_placeholder(item) for item in value.values())
    return False


def add_issue(issues, level, path, message):
    issues.append({"level": level, "path": path, "message": message})


def validate_adapter(adapter):
    issues = []

    for key in ["adapter_name", "version", "domain", "failure_modes", "constraints", "correction_policy", "evaluation"]:
        if key not in adapter:
            add_issue(issues, "error", key, "Required top-level field is missing.")

    if not has_text(adapter.get("adapter_name")):
        add_issue(issues, "error", "adapter_name", "Adapter name must be a non-empty string.")
    if not has_text(adapter.get("version")):
        add_issue(issues, "error", "version", "Version must be a non-empty string.")

    domain = adapter.get("domain", {})
    if not isinstance(domain, dict):
        add_issue(issues, "error", "domain", "Domain must be an object.")
        domain = {}
    for key in ["name", "user_workflow"]:
        if not has_text(domain.get(key)):
            add_issue(issues, "error", f"domain.{key}", "Domain field must be a non-empty string.")
    for key in ["allowed_system_actions", "disallowed_system_actions"]:
        if not is_nonempty_list(domain.get(key)):
            add_issue(issues, "error", f"domain.{key}", "Domain action list must be non-empty.")

    failure_modes = adapter.get("failure_modes", [])
    if not is_nonempty_list(failure_modes):
        add_issue(issues, "error", "failure_modes", "At least one failure mode is required.")
    for index, failure in enumerate(failure_modes if isinstance(failure_modes, list) else []):
        if not isinstance(failure, dict):
            add_issue(issues, "error", f"failure_modes[{index}]", "Failure mode must be an object.")
            continue
        for key in ["name", "description", "pressure_trigger"]:
            if not has_text(failure.get(key)):
                add_issue(issues, "error", f"failure_modes[{index}].{key}", "Field must be a non-empty string.")

    constraints = adapter.get("constraints", [])
    seen_ids = set()
    if not is_nonempty_list(constraints):
        add_issue(issues, "error", "constraints", "At least one constraint is required.")
    for index, constraint in enumerate(constraints if isinstance(constraints, list) else []):
        base = f"constraints[{index}]"
        if not isinstance(constraint, dict):
            add_issue(issues, "error", base, "Constraint must be an object.")
            continue

        constraint_id = constraint.get("id")
        if not has_text(constraint_id):
            add_issue(issues, "error", f"{base}.id", "Constraint id must be a non-empty string.")
        elif constraint_id in seen_ids:
            add_issue(issues, "error", f"{base}.id", f"Duplicate constraint id: {constraint_id}.")
        else:
            seen_ids.add(constraint_id)

        if constraint.get("layer") not in ALLOWED_LAYERS:
            add_issue(issues, "error", f"{base}.layer", "Layer must be one of P, B, C, or F.")
        if not has_text(constraint.get("description")):
            add_issue(issues, "error", f"{base}.description", "Description must be a non-empty string.")
        if not isinstance(constraint.get("hard"), bool):
            add_issue(issues, "error", f"{base}.hard", "Hard must be true or false.")

        verifier = constraint.get("verifier", {})
        if not isinstance(verifier, dict):
            add_issue(issues, "error", f"{base}.verifier", "Verifier must be an object.")
            verifier = {}
        if verifier.get("type") not in ALLOWED_VERIFIERS:
            add_issue(issues, "error", f"{base}.verifier.type", "Verifier type is not supported.")
        if not has_text(verifier.get("signal")):
            add_issue(issues, "error", f"{base}.verifier.signal", "Verifier signal must be described.")
        if not is_nonempty_list(verifier.get("inputs")):
            add_issue(issues, "error", f"{base}.verifier.inputs", "Verifier inputs must be non-empty.")

        grounding = constraint.get("grounding", {})
        if not isinstance(grounding, dict):
            add_issue(issues, "error", f"{base}.grounding", "Grounding must be an object.")
            grounding = {}
        if not isinstance(grounding.get("required"), bool):
            add_issue(issues, "error", f"{base}.grounding.required", "Grounding required must be true or false.")
        if "sources" not in grounding or not isinstance(grounding.get("sources"), list):
            add_issue(issues, "error", f"{base}.grounding.sources", "Grounding sources must be a list.")

        correction = constraint.get("correction", {})
        if not isinstance(correction, dict):
            add_issue(issues, "error", f"{base}.correction", "Correction must be an object.")
            correction = {}
        if correction.get("on_fail") not in (ALLOWED_ACTIONS - {"accept"}):
            add_issue(issues, "error", f"{base}.correction.on_fail", "on_fail must be revise, retrieve, ask, refuse, or defer.")
        if not has_text(correction.get("repair_strategy")):
            add_issue(issues, "error", f"{base}.correction.repair_strategy", "Repair strategy must be described.")

        gate = constraint.get("gate", {})
        if not isinstance(gate, dict):
            add_issue(issues, "error", f"{base}.gate", "Gate must be an object.")
            gate = {}
        if not has_text(gate.get("block_final_output_when")):
            add_issue(issues, "error", f"{base}.gate.block_final_output_when", "Gate blocking condition must be described.")

    policy = adapter.get("correction_policy", {})
    if not isinstance(policy, dict):
        add_issue(issues, "error", "correction_policy", "Correction policy must be an object.")
        policy = {}
    for key in POLICY_KEYS:
        if not is_nonempty_list(policy.get(key)):
            add_issue(issues, "error", f"correction_policy.{key}", "Policy list must be non-empty.")

    evaluation = adapter.get("evaluation", {})
    if not isinstance(evaluation, dict):
        add_issue(issues, "error", "evaluation", "Evaluation must be an object.")
        evaluation = {}
    for key in EVALUATION_KEYS:
        value = evaluation.get(key)
        if key == "known_caveats":
            if not is_nonempty_list(value):
                add_issue(issues, "error", f"evaluation.{key}", "Known caveats must be a non-empty list.")
        elif not has_text(value):
            add_issue(issues, "error", f"evaluation.{key}", "Evaluation field must be a non-empty string.")

    if contains_placeholder(adapter):
        add_issue(issues, "warning", "adapter", "Adapter still appears to contain placeholder text.")

    adapter_name = str(adapter.get("adapter_name", "")).lower()
    domain_name = str(domain.get("name", "")).lower()
    executable_adapters = {
        ("travel_planner_aana_adapter", "budgeted_travel_planning"),
        ("meal_planning_aana_adapter", "budgeted_allergy_safe_meal_planning"),
        ("support_reply_aana_adapter", "privacy_safe_customer_support"),
        ("research_summary_aana_adapter", "grounded_research_summary"),
    }
    if (adapter_name, domain_name) not in executable_adapters:
        add_issue(
            issues,
            "warning",
            "runner",
            "This adapter can be validated, but scripts/run_adapter.py only has deterministic execution for the checked-in travel, meal-planning, support-reply, and research-summary adapters today.",
        )

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "next_steps": next_steps(errors),
    }


def next_steps(errors):
    if errors:
        return [
            "Fix every error before sharing or running this adapter.",
            "Run scripts/validate_adapter.py again after edits.",
        ]
    return [
        "Run this adapter with scripts/run_adapter.py.",
        "Add domain-specific verifier logic when deterministic execution is needed.",
        "Publish prompts, candidate failures, gate results, and caveats with any claims.",
    ]


def parse_args():
    parser = argparse.ArgumentParser(description="Validate an AANA domain adapter JSON file.")
    parser.add_argument("--adapter", required=True, help="Path to adapter JSON.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main():
    args = parse_args()
    adapter = load_adapter(args.adapter)
    report = validate_adapter(adapter)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"Adapter is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
        print("Next steps:")
        for step in report["next_steps"]:
            print(f"- {step}")

    return 0 if report["valid"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Adapter validation failed: {exc}", file=sys.stderr)
        sys.exit(2)
