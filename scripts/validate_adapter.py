#!/usr/bin/env python
"""Validate an AANA domain adapter JSON file."""

import argparse
import json
import pathlib
import sys


ALLOWED_LAYERS = {"P", "B", "C", "F"}
ALLOWED_VERIFIERS = {"deterministic", "retrieval", "model_judge", "human_review"}
ALLOWED_ACTIONS = {"accept", "revise", "retrieve", "ask", "refuse", "defer"}
ALLOWED_AIX_RISK_TIERS = {"standard", "elevated", "high", "strict"}
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
PRODUCTION_READINESS_KEYS = [
    "status",
    "owner",
    "evidence_requirements",
    "verifier_fallbacks",
    "calibration_notes",
    "fixture_coverage",
    "escalation_policy",
    "audit_requirements",
    "human_review_escalation",
    "production_caveats",
]
AIX_KEYS = ["risk_tier", "beta", "layer_weights", "thresholds"]
AIX_TIER_REQUIREMENTS = {
    "standard": {"beta": 1.0, "B": 1.0, "accept": 0.85, "revise": 0.65, "defer": 0.5},
    "elevated": {"beta": 1.15, "B": 1.1, "accept": 0.88, "revise": 0.68, "defer": 0.52},
    "high": {"beta": 1.3, "B": 1.25, "accept": 0.91, "revise": 0.72, "defer": 0.56},
    "strict": {"beta": 1.5, "B": 1.4, "accept": 0.94, "revise": 0.78, "defer": 0.62},
}
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


def aix_tier_issues(aix, base_path="aix"):
    issues = []
    if not isinstance(aix, dict):
        return issues

    tier = aix.get("risk_tier")
    if tier is None:
        return issues
    if tier not in ALLOWED_AIX_RISK_TIERS:
        add_issue(
            issues,
            "error",
            f"{base_path}.risk_tier",
            "AIx risk_tier must be one of standard, elevated, high, or strict.",
        )
        return issues

    requirements = AIX_TIER_REQUIREMENTS[tier]
    beta = aix.get("beta")
    if isinstance(beta, (int, float)) and beta < requirements["beta"]:
        add_issue(issues, "warning", f"{base_path}.beta", f"AIx beta is below the {tier} tier minimum of {requirements['beta']}.")

    layer_weights = aix.get("layer_weights", {})
    if isinstance(layer_weights, dict):
        b_weight = layer_weights.get("B")
        if isinstance(b_weight, (int, float)) and b_weight < requirements["B"]:
            add_issue(issues, "warning", f"{base_path}.layer_weights.B", f"AIx B-layer weight is below the {tier} tier minimum of {requirements['B']}.")

    thresholds = aix.get("thresholds", {})
    if isinstance(thresholds, dict):
        for action in ("accept", "revise", "defer"):
            value = thresholds.get(action)
            if isinstance(value, (int, float)) and value < requirements[action]:
                add_issue(
                    issues,
                    "warning",
                    f"{base_path}.thresholds.{action}",
                    f"AIx {action} threshold is below the {tier} tier minimum of {requirements[action]}.",
                )
    return issues


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

    aix = adapter.get("aix")
    if aix is not None:
        if not isinstance(aix, dict):
            add_issue(issues, "error", "aix", "AIx config must be an object when provided.")
        else:
            for key in AIX_KEYS:
                if key not in aix:
                    add_issue(issues, "warning", f"aix.{key}", "AIx config field is missing; runtime defaults will be used.")
            beta = aix.get("beta")
            if beta is not None and not isinstance(beta, (int, float)):
                add_issue(issues, "error", "aix.beta", "AIx beta must be numeric.")
            layer_weights = aix.get("layer_weights")
            if layer_weights is not None:
                if not isinstance(layer_weights, dict):
                    add_issue(issues, "error", "aix.layer_weights", "AIx layer_weights must be an object.")
                else:
                    for layer, value in layer_weights.items():
                        if layer not in ALLOWED_LAYERS or not isinstance(value, (int, float)):
                            add_issue(issues, "error", f"aix.layer_weights.{layer}", "AIx layer weights must be numeric values for P, B, C, or F.")
            thresholds = aix.get("thresholds")
            if thresholds is not None:
                if not isinstance(thresholds, dict):
                    add_issue(issues, "error", "aix.thresholds", "AIx thresholds must be an object.")
                else:
                    for action in ("accept", "revise", "defer"):
                        value = thresholds.get(action)
                        if not isinstance(value, (int, float)) or value < 0 or value > 1:
                            add_issue(issues, "error", f"aix.thresholds.{action}", "AIx thresholds must include numeric accept, revise, and defer values between 0 and 1.")
            issues.extend(aix_tier_issues(aix))

    production = adapter.get("production_readiness")
    if production is not None and aix is None:
        add_issue(
            issues,
            "warning",
            "aix",
            "Production adapters should declare explicit AIx risk_tier, beta, layer_weights, and thresholds.",
        )
    if production is None:
        add_issue(
            issues,
            "warning",
            "production_readiness",
            "Production adapters should declare status, owner, evidence requirements, escalation policy, audit requirements, and caveats.",
        )
    elif not isinstance(production, dict):
        add_issue(issues, "error", "production_readiness", "Production readiness must be an object when provided.")
    else:
        for key in PRODUCTION_READINESS_KEYS:
            if key not in production:
                add_issue(issues, "warning", f"production_readiness.{key}", "Production readiness field is missing.")
        for key in ("status", "owner", "escalation_policy", "audit_requirements"):
            if key in production and not has_text(production.get(key)):
                add_issue(issues, "warning", f"production_readiness.{key}", "Field should be a non-empty string.")
        for key in (
            "evidence_requirements",
            "verifier_fallbacks",
            "calibration_notes",
            "human_review_escalation",
            "production_caveats",
        ):
            if key in production and not is_nonempty_list(production.get(key)):
                add_issue(issues, "warning", f"production_readiness.{key}", "Field should be a non-empty list.")
        fixture_coverage = production.get("fixture_coverage")
        if "fixture_coverage" in production:
            if not isinstance(fixture_coverage, dict):
                add_issue(issues, "warning", "production_readiness.fixture_coverage", "Fixture coverage should be an object.")
            else:
                for action in sorted(ALLOWED_ACTIONS):
                    if action not in fixture_coverage:
                        add_issue(
                            issues,
                            "warning",
                            f"production_readiness.fixture_coverage.{action}",
                            "Fixture coverage should state covered, not_applicable, or external_required.",
                        )

    adapter_name = str(adapter.get("adapter_name", "")).lower()
    domain_name = str(domain.get("name", "")).lower()
    executable_adapters = {
        ("travel_planner_aana_adapter", "budgeted_travel_planning"),
        ("meal_planning_aana_adapter", "budgeted_allergy_safe_meal_planning"),
        ("support_reply_aana_adapter", "privacy_safe_customer_support"),
        ("crm_support_reply_aana_adapter", "crm_support_reply"),
        ("email_send_guardrail_aana_adapter", "email_send_guardrail"),
        ("file_operation_guardrail_aana_adapter", "file_operation_guardrail"),
        ("code_change_review_aana_adapter", "code_change_review"),
        ("incident_response_update_aana_adapter", "incident_response_update"),
        ("security_vulnerability_disclosure_aana_adapter", "security_vulnerability_disclosure"),
        ("access_permission_change_aana_adapter", "access_permission_change"),
        ("database_migration_guardrail_aana_adapter", "database_migration_guardrail"),
        ("experiment_ab_test_launch_aana_adapter", "experiment_ab_test_launch"),
        ("product_requirements_checker_aana_adapter", "product_requirements_checker"),
        ("procurement_vendor_risk_aana_adapter", "procurement_vendor_risk"),
        ("hiring_candidate_feedback_aana_adapter", "hiring_candidate_feedback"),
        ("performance_review_aana_adapter", "performance_review"),
        ("learning_tutor_answer_checker_aana_adapter", "learning_tutor_answer_checker"),
        ("api_contract_change_aana_adapter", "api_contract_change"),
        ("infrastructure_change_guardrail_aana_adapter", "infrastructure_change_guardrail"),
        ("data_pipeline_change_aana_adapter", "data_pipeline_change"),
        ("model_evaluation_release_aana_adapter", "model_evaluation_release"),
        ("feature_flag_rollout_aana_adapter", "feature_flag_rollout"),
        ("sales_proposal_checker_aana_adapter", "sales_proposal_checker"),
        ("customer_success_renewal_aana_adapter", "customer_success_renewal"),
        ("invoice_billing_reply_aana_adapter", "invoice_billing_reply"),
        ("insurance_claim_triage_aana_adapter", "insurance_claim_triage"),
        ("grant_application_review_aana_adapter", "grant_application_review"),
        ("deployment_readiness_aana_adapter", "deployment_readiness"),
        ("legal_safety_router_aana_adapter", "legal_safety_router"),
        ("medical_safety_router_aana_adapter", "medical_safety_router"),
        ("financial_advice_router_aana_adapter", "financial_advice_router"),
        ("booking_purchase_guardrail_aana_adapter", "booking_purchase_guardrail"),
        ("calendar_scheduling_aana_adapter", "calendar_scheduling"),
        ("data_export_guardrail_aana_adapter", "data_export_guardrail"),
        ("publication_check_aana_adapter", "publication_check"),
        ("meeting_summary_checker_aana_adapter", "meeting_summary_checker"),
        ("ticket_update_checker_aana_adapter", "ticket_update_checker"),
        ("research_answer_grounding_aana_adapter", "research_answer_grounding"),
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
