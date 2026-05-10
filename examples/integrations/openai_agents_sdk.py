"""AANA wrapper example for OpenAI Agents SDK tools.

The current OpenAI Agents SDK runs agents with `Agent` plus `Runner`, and tools
can be ordinary Python functions registered with the SDK's function-tool
primitive. This example keeps the smoke path dependency-free while showing where
the AANA wrapper sits.
"""

from __future__ import annotations

import json

import aana


LEDGER: list[dict] = []


def get_public_status(service: str) -> dict:
    LEDGER.append({"tool_name": "get_public_status", "service": service})
    return {"service": service, "status": "ok"}


guarded_get_public_status = aana.wrap_agent_tool(get_public_status)


def send_email(to: str, body: str) -> dict:
    LEDGER.append({"tool_name": "send_email", "to": to})
    return {"sent": True, "to": to}


guarded_send_email = aana.openai_agents_tool_middleware(
    send_email,
    metadata={
        "tool_category": "write",
        "authorization_state": "validated",
        "risk_domain": "customer_support",
        "evidence_refs": [
            {
                "source_id": "policy.email.confirmation",
                "kind": "policy",
                "trust_tier": "verified",
                "redaction_status": "redacted",
                "summary": "Outbound customer email requires explicit user confirmation before sending.",
            }
        ],
    },
    raise_on_block=False,
)


def build_openai_agents_sdk_tool():
    """Return an OpenAI Agents SDK function tool when `openai-agents` is installed."""

    try:
        from agents import function_tool
    except ImportError as exc:  # pragma: no cover - example path for optional dependency.
        raise RuntimeError("Install openai-agents to register this with the OpenAI Agents SDK.") from exc

    return [function_tool(guarded_get_public_status), function_tool(guarded_send_email)]


def build_agent():
    """Illustrative Agent construction for real OpenAI Agents SDK projects."""

    try:
        from agents import Agent
    except ImportError as exc:  # pragma: no cover - example path for optional dependency.
        raise RuntimeError("Install openai-agents to build the SDK Agent.") from exc

    return Agent(
        name="AANA guarded support agent",
        instructions="Use tools only after AANA has checked the proposed action.",
        tools=build_openai_agents_sdk_tool(),
    )


def run_smoke() -> dict:
    """Run the dependency-free enforcement proof."""

    LEDGER.clear()
    accepted = guarded_get_public_status(service="docs")
    blocked = guarded_send_email(to="customer@example.com", body="Needs confirmation")
    accepted_route = guarded_get_public_status.aana_last_gate["result"]["architecture_decision"]["route"]
    blocked_route = guarded_send_email.aana_last_gate["result"]["architecture_decision"]["route"]
    return {
        "pattern": "agent proposes -> AANA checks -> blocked tools do not execute",
        "accepted_route": accepted_route,
        "accepted_tool_result": accepted,
        "blocked_route": blocked_route,
        "blocked_result": {
            "execution_allowed": blocked["execution_allowed"],
            "error_type": blocked["error"]["error_type"],
        },
        "executed_tool_calls": list(LEDGER),
        "blocked_tool_executed": any(call["tool_name"] == "send_email" for call in LEDGER),
    }


if __name__ == "__main__":
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))
