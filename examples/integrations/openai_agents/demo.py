"""Repo-owned AANA demo for OpenAI Agents SDK tool enforcement.

This example is runnable without OpenAI credentials or the optional
`openai-agents` package. The scripted proposal path mirrors what an OpenAI
agent would hand to a tool runtime: a tool name, arguments, metadata, and
evidence. AANA gates the call first, and the underlying tool body only runs
when the route is truly `accept`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

import aana


@dataclass(frozen=True)
class ToolProposal:
    """One proposed tool call emitted by an agent runtime."""

    tool_name: str
    arguments: dict[str, Any]
    metadata: dict[str, Any]
    evidence_refs: list[dict[str, Any]]


class ToolLedger:
    """Small side-effect ledger used to prove blocked tools do not execute."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record(self, tool_name: str, arguments: dict[str, Any]) -> None:
        self.calls.append({"tool_name": tool_name, "arguments": dict(arguments)})

    def count(self, tool_name: str) -> int:
        return sum(1 for call in self.calls if call["tool_name"] == tool_name)


def public_status_tool(ledger: ToolLedger) -> Callable[..., dict[str, Any]]:
    def get_public_status(service: str) -> dict[str, Any]:
        ledger.record("get_public_status", {"service": service})
        return {"service": service, "status": "ok"}

    return get_public_status


def email_tool(ledger: ToolLedger) -> Callable[..., dict[str, Any]]:
    def send_customer_email(to: str, body: str) -> dict[str, Any]:
        ledger.record("send_customer_email", {"to": to, "body": body})
        return {"sent": True, "to": to}

    return send_customer_email


def _policy_ref(summary: str, *, source_id: str = "policy.customer_support.email") -> dict[str, Any]:
    return aana.tool_evidence_ref(
        source_id=source_id,
        kind="policy",
        trust_tier="verified",
        redaction_status="redacted",
        summary=summary,
    )


def _approval_ref(summary: str) -> dict[str, Any]:
    return aana.tool_evidence_ref(
        source_id="approval.user.confirmed_send",
        kind="approval",
        trust_tier="verified",
        redaction_status="redacted",
        summary=summary,
    )


def scripted_agent_proposals() -> list[ToolProposal]:
    """Return three realistic proposals from an OpenAI-style tool runtime."""

    return [
        ToolProposal(
            tool_name="get_public_status",
            arguments={"service": "docs"},
            metadata={
                "tool_category": "public_read",
                "authorization_state": "none",
                "risk_domain": "public_information",
                "user_intent": "Check whether the public documentation service is available.",
            },
            evidence_refs=[_policy_ref("Public service status checks do not require identity authorization.")],
        ),
        ToolProposal(
            tool_name="send_customer_email",
            arguments={"to": "customer@example.com", "body": "Your case has been updated."},
            metadata={
                "tool_category": "write",
                "authorization_state": "validated",
                "risk_domain": "customer_support",
                "user_intent": "Send the customer an update email.",
            },
            evidence_refs=[_policy_ref("Outbound customer email requires explicit user confirmation before sending.")],
        ),
        ToolProposal(
            tool_name="send_customer_email",
            arguments={"to": "customer@example.com", "body": "Your confirmed case update is ready."},
            metadata={
                "tool_category": "write",
                "authorization_state": "confirmed",
                "risk_domain": "customer_support",
                "user_intent": "Send the confirmed customer update email.",
            },
            evidence_refs=[
                _policy_ref("Outbound customer email requires explicit user confirmation before sending."),
                _approval_ref("The user explicitly confirmed this redacted draft should be sent."),
            ],
        ),
    ]


def _tool_registry(ledger: ToolLedger) -> dict[str, Callable[..., dict[str, Any]]]:
    return {
        "get_public_status": public_status_tool(ledger),
        "send_customer_email": email_tool(ledger),
    }


def run_demo() -> dict[str, Any]:
    """Run the AANA enforcement proof and return a JSON-serializable summary."""

    ledger = ToolLedger()
    tools = _tool_registry(ledger)
    decisions: list[dict[str, Any]] = []

    for proposal in scripted_agent_proposals():
        output = aana.execute_tool_if_allowed(
            tools[proposal.tool_name],
            tool_name=proposal.tool_name,
            arguments=proposal.arguments,
            metadata=proposal.metadata,
            evidence_refs=proposal.evidence_refs,
            raise_on_block=False,
        )
        decision = output["gate"]["result"]["architecture_decision"]
        decisions.append(
            {
                "tool_name": proposal.tool_name,
                "route": decision["route"],
                "execution_allowed": output["gate"]["execution_allowed"],
                "hard_blockers": decision.get("hard_blockers", []),
                "tool_result": output["tool_result"],
            }
        )

    return {
        "pattern": "agent proposes -> AANA checks -> tool executes only if allowed",
        "decisions": decisions,
        "executed_tool_calls": ledger.calls,
        "blocked_send_email_executed": ledger.count("send_customer_email") > 1,
    }


def build_openai_agents_sdk_tools():
    """Build real OpenAI Agents SDK tools when the optional package is present.

    Register these guarded callables with an `Agent`. The demo still performs
    enforcement inside the function wrapper, so an SDK planner cannot execute
    the original side-effecting tool unless AANA returns `accept`.
    """

    try:
        from agents import function_tool
    except ImportError as exc:  # pragma: no cover - optional dependency path.
        raise RuntimeError("Install openai-agents to register this demo with the OpenAI Agents SDK.") from exc

    ledger = ToolLedger()
    guarded_status = aana.openai_agents_tool_middleware(
        public_status_tool(ledger),
        metadata={
            "tool_category": "public_read",
            "authorization_state": "none",
            "risk_domain": "public_information",
            "evidence_refs": [_policy_ref("Public service status checks do not require identity authorization.")],
        },
    )
    guarded_email = aana.openai_agents_tool_middleware(
        email_tool(ledger),
        metadata={
            "tool_category": "write",
            "authorization_state": "user_claimed",
            "risk_domain": "customer_support",
            "evidence_refs": [_policy_ref("Outbound customer email requires explicit user confirmation before sending.")],
        },
        raise_on_block=False,
    )
    return [function_tool(guarded_status), function_tool(guarded_email)]


def build_agent():
    """Build an illustrative OpenAI Agents SDK Agent around AANA-guarded tools."""

    try:
        from agents import Agent
    except ImportError as exc:  # pragma: no cover - optional dependency path.
        raise RuntimeError("Install openai-agents to build the SDK Agent.") from exc

    return Agent(
        name="AANA guarded support agent",
        instructions=(
            "Propose tool calls normally. The host runtime enforces AANA before "
            "any tool body runs, and non-accept AANA routes must be surfaced to "
            "the user as ask, defer, or refuse."
        ),
        tools=build_openai_agents_sdk_tools(),
    )


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True))
