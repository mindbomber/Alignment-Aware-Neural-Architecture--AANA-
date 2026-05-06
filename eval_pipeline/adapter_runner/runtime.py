"""Adapter runner runtime orchestration.

This module owns the compatibility runner execution path. Public integrations
should prefer the Workflow Contract or Agent Event Contract surfaces.
"""

try:
    from constraint_tools import run_constraint_tools
except ImportError:  # pragma: no cover - package import path fallback
    from eval_pipeline.constraint_tools import run_constraint_tools

try:
    from run_aana_evals import deterministic_repair
except ImportError:  # pragma: no cover - package import path fallback
    from eval_pipeline.run_aana_evals import deterministic_repair

from . import constraints as adapter_constraints
from . import registry as adapter_registry
from . import repair as adapter_repair
from . import results as adapter_results
from . import routing
from .routing import *  # noqa: F401,F403
from .verifier_modules import support_product
from .verifier_modules.constraint_maps import *  # noqa: F401,F403
from .verifier_modules.local_actions import *  # noqa: F401,F403
from .verifier_modules.engineering_release import *  # noqa: F401,F403
from .verifier_modules.business_ops import *  # noqa: F401,F403
from .verifier_modules.regulated_advice import *  # noqa: F401,F403
from .verifier_modules.research_civic import *  # noqa: F401,F403
from .verifier_catalog import VERIFIER_REGISTRY


support_tool_report = support_product.support_tool_report
support_customer_name = support_product.support_customer_name
support_repair = support_product.support_safe_response
email_tool_report = support_product.email_tool_report
email_repair = support_product.email_safe_response

def load_adapter(path):
    return adapter_registry.load_adapter(path)

def gate_from_report(report):
    return adapter_repair.gate_from_report(report)

def action_from_answer_and_report(answer, report, fallback="accept"):
    return adapter_repair.action_from_answer_and_report(answer, report, fallback)

def violation_constraint_ids(adapter, code):
    return adapter_constraints.violation_constraint_ids(
        adapter,
        code,
        mapping_specs=VIOLATION_MAPPING_SPECS,
        default_mapping=VIOLATION_TO_CONSTRAINT,
    )

def constraint_results(adapter, report):
    return adapter_constraints.constraint_results(
        adapter,
        report,
        mapping_specs=VIOLATION_MAPPING_SPECS,
        default_mapping=VIOLATION_TO_CONSTRAINT,
    )

def unsupported_result(adapter, prompt, candidate):
    return adapter_results.unsupported_result(adapter, prompt, candidate)

def adapter_summary(adapter):
    return adapter_registry.adapter_summary(adapter)

def _verifier_module_for_adapter(adapter, task):
    return adapter_registry.resolve_verifier_module(adapter, task, VERIFIER_REGISTRY)


def _safe_response_source(module):
    safe_response = module.safe_response_function
    if safe_response is None:
        return None
    source_module = str(getattr(safe_response, "__module__", "")).split(".")[-1]
    source_name = getattr(safe_response, "__name__", "")
    return f"{source_module}.{source_name}" if source_module and source_name else None


def _with_route_policy(result, module, report):
    if not module.route_policy:
        return result
    result["correction_policy"] = adapter_repair.decide_correction_action(report)
    return result


def _run_verifier_module(adapter, prompt, candidate, module, caveats):
    if candidate:
        candidate_report = module.run(prompt, candidate)
        if candidate_report["violations"]:
            final_answer = module.safe_response_function(prompt)
            final_report = module.run(prompt, final_answer)
            result = {
                "adapter": adapter_summary(adapter),
                "prompt": prompt,
                "candidate_answer": candidate,
                "candidate_gate": gate_from_report(candidate_report),
                "final_answer": final_answer,
                "gate_decision": gate_from_report(final_report),
                "recommended_action": "revise",
                "constraint_results": constraint_results(adapter, final_report),
                "candidate_tool_report": candidate_report,
                "tool_report": final_report,
                "caveats": caveats,
            }
            safe_response_source = _safe_response_source(module)
            if module.name in {"support", "email"} and safe_response_source:
                result["safe_response_source"] = safe_response_source
            return _with_route_policy(result, module, candidate_report)

        result = {
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
        return _with_route_policy(result, module, candidate_report)

    final_answer = module.safe_response_function(prompt)
    final_report = module.run(prompt, final_answer)
    return {
        "adapter": adapter_summary(adapter),
        "prompt": prompt,
        "candidate_answer": None,
        "final_answer": final_answer,
        "gate_decision": gate_from_report(final_report),
        "recommended_action": module.fallback_action,
        "constraint_results": constraint_results(adapter, final_report),
        "tool_report": final_report,
        "caveats": caveats,
    }


def _run_deterministic_adapter(adapter, prompt, candidate, task, caveats):
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


def _run_adapter_core(adapter, prompt, candidate=None):
    task = make_task(adapter, prompt)
    caveats = list(adapter.get("evaluation", {}).get("known_caveats", []))
    runtime_entry = adapter_registry.resolve_runtime_adapter(adapter, task, VERIFIER_REGISTRY)
    if runtime_entry["kind"] == "verifier_backed":
        return _run_verifier_module(adapter, prompt, candidate, runtime_entry["verifier_module"], caveats)
    if runtime_entry["kind"] == "deterministic_demo":
        return _run_deterministic_adapter(adapter, prompt, candidate, task, caveats)
    if runtime_entry["kind"] == "unsupported":
        return unsupported_result(adapter, prompt, candidate)
    raise ValueError(f"Unknown adapter runtime kind: {runtime_entry['kind']}")

def run_adapter(adapter, prompt, candidate=None):
    result = _run_adapter_core(adapter, prompt, candidate)
    return adapter_results.attach_runtime_aix(adapter, result, constraint_results)
