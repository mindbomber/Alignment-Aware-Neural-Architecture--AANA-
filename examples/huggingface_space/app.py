"""Canonical public "Try AANA in 2 minutes" Hugging Face Space.

The public Space surface must keep accepting these seven frozen fields:
tool_name, tool_category, authorization_state, evidence_refs, risk_domain,
proposed_arguments, and recommended_route.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import aana


PUBLIC_MESSAGE = (
    "AANA is a pre-action control layer for AI agents: agents propose actions, "
    "AANA checks evidence/auth/risk, and tools execute only when the route is accept."
)

EXAMPLE_EVENTS: dict[str, dict[str, Any]] = {
    "Allowed: confirmed write": {
        "tool_name": "send_email",
        "tool_category": "write",
        "authorization_state": "confirmed",
        "evidence_refs": ["user_confirmed_send_email", "draft_id:123"],
        "risk_domain": "customer_support",
        "proposed_arguments": {"to": "customer@example.com"},
        "recommended_route": "accept",
    },
    "Blocked: write missing confirmation": {
        "tool_name": "send_email",
        "tool_category": "write",
        "authorization_state": "user_claimed",
        "evidence_refs": ["draft_id:123"],
        "risk_domain": "customer_support",
        "proposed_arguments": {"to": "customer@example.com"},
        "recommended_route": "accept",
    },
    "Blocked: private read missing auth": {
        "tool_name": "get_recent_transactions",
        "tool_category": "private_read",
        "authorization_state": "none",
        "evidence_refs": [],
        "risk_domain": "finance",
        "proposed_arguments": {"account_id": "acct_redacted", "limit": 5},
        "recommended_route": "accept",
    },
    "Blocked: unknown destructive tool": {
        "tool_name": "delete_database",
        "tool_category": "unknown",
        "authorization_state": "none",
        "evidence_refs": [],
        "risk_domain": "unknown",
        "proposed_arguments": {"database": "prod"},
        "recommended_route": "refuse",
    },
}


def example_event(name: str) -> str:
    """Return a formatted example event for a scenario button/dropdown."""

    return json.dumps(copy.deepcopy(EXAMPLE_EVENTS[name]), indent=2, sort_keys=True)


def _decision(result: dict[str, Any]) -> dict[str, Any]:
    architecture = result.get("architecture_decision")
    return architecture if isinstance(architecture, dict) else result


def _route(result: dict[str, Any]) -> str:
    decision = _decision(result)
    return str(decision.get("route") or result.get("route") or result.get("recommended_action") or "defer")


def _synthetic_tool(event: dict[str, Any]) -> dict[str, Any]:
    """Synthetic-only executor used to prove blocked tools do not run."""

    return {
        "synthetic_tool_executed": True,
        "tool_name": event.get("tool_name"),
        "argument_keys": sorted((event.get("proposed_arguments") or {}).keys()),
        "side_effects": "none_public_demo_only",
    }


def guarded_synthetic_execution(event: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Run the synthetic tool only when AANA returns accept."""

    route = _route(result)
    proof = {
        "required_route": "accept",
        "aana_route": route,
        "blocked_tool_non_execution_proven": route != "accept",
        "synthetic_executor_call_count_before": 0,
        "synthetic_executor_call_count_after": 0,
        "synthetic_executor_result": None,
    }
    if route == "accept":
        proof["synthetic_executor_result"] = _synthetic_tool(event)
        proof["synthetic_executor_call_count_after"] = 1
        proof["blocked_tool_non_execution_proven"] = False
    return proof


def summarize_decision(event: dict[str, Any], result: dict[str, Any], execution_proof: dict[str, Any]) -> dict[str, Any]:
    """Extract the reviewer-facing fields from the full AANA result."""

    decision = _decision(result)
    evidence_refs = decision.get("evidence_refs") if isinstance(decision.get("evidence_refs"), dict) else {}
    audit_event = decision.get("audit_safe_log_event") or decision.get("audit_event") or {}
    return {
        "route": decision.get("route") or result.get("route"),
        "aix_score": decision.get("aix_score") or (result.get("aix") or {}).get("score"),
        "hard_blockers": decision.get("hard_blockers") or result.get("hard_blockers") or [],
        "missing_evidence": decision.get("missing_evidence") or evidence_refs.get("missing") or [],
        "authorization_state": decision.get("authorization_state") or event.get("authorization_state"),
        "recovery_suggestion": decision.get("correction_recovery_suggestion") or decision.get("recovery_suggestion"),
        "audit_safe_log_event": audit_event,
        "execution_allowed": _route(result) == "accept",
        "synthetic_executor_call_count_after": execution_proof["synthetic_executor_call_count_after"],
        "blocked_tool_non_execution_proven": execution_proof["blocked_tool_non_execution_proven"],
    }


def check_event(event_json: str) -> tuple[str, str, str, str]:
    """Check a pasted tool-call event and return Gradio-friendly outputs."""

    event = json.loads(event_json)
    result = aana.check_tool_call(event)
    execution_proof = guarded_synthetic_execution(event, result)
    summary = summarize_decision(event, result, execution_proof)
    route = str(summary["route"])
    proof_line = (
        "Synthetic executor did not run because AANA did not return accept."
        if route != "accept"
        else "Synthetic executor ran because AANA returned accept."
    )
    markdown = "\n".join(
        [
            f"## Route: `{route}`",
            f"- AIx score: `{summary['aix_score']}`",
            f"- Authorization state: `{summary['authorization_state']}`",
            f"- Hard blockers: `{summary['hard_blockers'] or ['none']}`",
            f"- Missing evidence: `{summary['missing_evidence'] or ['none']}`",
            f"- Execution proof: {proof_line}",
        ]
    )
    return (
        markdown,
        json.dumps(summary, indent=2, sort_keys=True),
        json.dumps(execution_proof, indent=2, sort_keys=True),
        json.dumps(result, indent=2, sort_keys=True),
    )


def check_json_event(event_json: str) -> str:
    """Backward-compatible helper returning the full AANA decision as JSON."""

    return check_event(event_json)[3]


def build_demo():
    """Build the Gradio UI only when the Space runtime imports it."""

    import gradio as gr

    with gr.Blocks(title="Try AANA") as demo:
        gr.Markdown("# Try AANA in 2 minutes")
        gr.Markdown(PUBLIC_MESSAGE)
        gr.Markdown(
            "**What this demonstrates:** an agent proposes a tool call. AANA checks "
            "evidence/auth/risk. The tool only executes if the route is `accept`."
        )
        gr.Markdown(
            "**How to test it:** pick an example, click `Check With AANA`, then inspect "
            "the route and executor proof."
        )
        gr.Markdown(
            "**Reviewer checklist:** `accept` allows execution; `ask`, `defer`, and "
            "`refuse` block execution; missing auth/evidence becomes a blocker; an "
            "audit-safe event is emitted; and a bad runtime recommendation can be overridden."
        )
        gr.Markdown(
            "**Contrast:** a plain permissive agent would execute the proposed tool call. "
            "AANA blocks unless the contract is satisfied."
        )
        scenario = gr.Dropdown(
            choices=list(EXAMPLE_EVENTS),
            value="Blocked: write missing confirmation",
            label="Load example",
            interactive=True,
        )
        event = gr.Code(
            value=example_event("Blocked: write missing confirmation"),
            language="json",
            label="Paste Agent Action Contract v1 tool call",
        )
        with gr.Row():
            load = gr.Button("Load Example")
            check = gr.Button("Check With AANA", variant="primary")
        summary = gr.Markdown(label="Decision summary")
        compact = gr.Code(language="json", label="Route, AIx, blockers, missing evidence, auth state")
        proof = gr.Code(language="json", label="Blocked-tool non-execution proof")
        full = gr.Code(language="json", label="Full AANA decision")

        load.click(example_event, inputs=scenario, outputs=event)
        check.click(check_event, inputs=event, outputs=[summary, compact, proof, full])
    return demo


try:
    demo = build_demo()
except ModuleNotFoundError as exc:
    if exc.name != "gradio":
        raise
    demo = None


if __name__ == "__main__":
    build_demo().launch()
