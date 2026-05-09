"""OpenAI Agents SDK-style tools wrapped with AANA.

This example keeps the smoke path dependency-free while matching the shape used
by OpenAI Agents SDK apps: define Python tool functions, wrap them with AANA,
then register the guarded functions with `function_tool(...)` when
`openai-agents` is installed.
"""

from __future__ import annotations

import json
from typing import Any

import aana


EXECUTION_LEDGER: list[dict[str, Any]] = []


def _record(tool_name: str, arguments: dict[str, Any]) -> None:
    EXECUTION_LEDGER.append({"tool_name": tool_name, "arguments": dict(arguments)})


def _policy_ref(summary: str) -> dict[str, Any]:
    return aana.tool_evidence_ref(
        source_id="policy.customer_support.email",
        kind="policy",
        trust_tier="verified",
        redaction_status="redacted",
        summary=summary,
    )


def _auth_ref(summary: str) -> dict[str, Any]:
    return aana.tool_evidence_ref(
        source_id="auth.session.verified",
        kind="auth_event",
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


@aana.openai_agents_tool_middleware(
    tool_name="get_public_status",
    metadata={
        "tool_category": "public_read",
        "authorization_state": "none",
        "risk_domain": "public_information",
        "evidence_refs": [
            aana.tool_evidence_ref(
                source_id="policy.public_status",
                kind="policy",
                trust_tier="verified",
                redaction_status="redacted",
                summary="Public status checks do not require identity authorization.",
            )
        ],
    },
)
def get_public_status(service: str) -> dict[str, Any]:
    _record("get_public_status", {"service": service})
    return {"service": service, "status": "ok"}


@aana.openai_agents_tool_middleware(
    tool_name="get_customer_profile",
    metadata={
        "tool_category": "private_read",
        "authorization_state": "authenticated",
        "risk_domain": "customer_support",
        "evidence_refs": [_auth_ref("The runtime verified the customer session before the profile lookup.")],
    },
)
def get_customer_profile(customer_id: str) -> dict[str, Any]:
    _record("get_customer_profile", {"customer_id": customer_id})
    return {"customer_id": customer_id, "profile": "redacted"}


@aana.openai_agents_tool_middleware(
    tool_name="send_customer_email",
    metadata={
        "tool_category": "write",
        "authorization_state": "validated",
        "risk_domain": "customer_support",
        "evidence_refs": [_policy_ref("Outbound customer email requires explicit user confirmation before sending.")],
    },
    raise_on_block=False,
)
def send_customer_email_without_confirmation(to: str, body: str) -> dict[str, Any]:
    _record("send_customer_email_without_confirmation", {"to": to, "body": body})
    return {"sent": True, "to": to}


@aana.openai_agents_tool_middleware(
    tool_name="send_customer_email",
    metadata={
        "tool_category": "write",
        "authorization_state": "confirmed",
        "risk_domain": "customer_support",
        "evidence_refs": [
            _policy_ref("Outbound customer email requires explicit user confirmation before sending."),
            _approval_ref("The user explicitly confirmed this redacted draft should be sent."),
        ],
    },
    raise_on_block=False,
)
def send_customer_email_confirmed(to: str, body: str) -> dict[str, Any]:
    _record("send_customer_email_confirmed", {"to": to, "body": body})
    return {"sent": True, "to": to}


def build_openai_agents_sdk_tools():
    """Return function tools for real OpenAI Agents SDK apps."""

    try:
        from agents import function_tool
    except ImportError as exc:  # pragma: no cover - optional dependency path.
        raise RuntimeError("Install openai-agents to register these tools with the OpenAI Agents SDK.") from exc

    return [
        function_tool(get_public_status),
        function_tool(get_customer_profile),
        function_tool(send_customer_email_without_confirmation),
        function_tool(send_customer_email_confirmed),
    ]


def build_agent():
    """Return an illustrative OpenAI Agents SDK Agent using AANA-wrapped tools."""

    try:
        from agents import Agent
    except ImportError as exc:  # pragma: no cover - optional dependency path.
        raise RuntimeError("Install openai-agents to build the SDK Agent.") from exc

    return Agent(
        name="AANA wrapped-tools support agent",
        instructions=(
            "Use the registered tools normally. Each tool is wrapped by AANA and "
            "will execute only when the pre-tool route is accept."
        ),
        tools=build_openai_agents_sdk_tools(),
    )


def _route(wrapper) -> str:
    return wrapper.aana_last_gate["result"]["architecture_decision"]["route"]


def run_smoke() -> dict[str, Any]:
    EXECUTION_LEDGER.clear()
    public_result = get_public_status(service="docs")
    private_result = get_customer_profile(customer_id="cust_redacted")
    blocked_result = send_customer_email_without_confirmation(to="customer@example.com", body="Needs confirmation")
    confirmed_result = send_customer_email_confirmed(to="customer@example.com", body="Confirmed update")

    return {
        "routes": {
            "get_public_status": _route(get_public_status),
            "get_customer_profile": _route(get_customer_profile),
            "send_customer_email_without_confirmation": blocked_result["result"]["architecture_decision"]["route"],
            "send_customer_email_confirmed": _route(send_customer_email_confirmed),
        },
        "tool_results": {
            "get_public_status": public_result,
            "get_customer_profile": private_result,
            "send_customer_email_without_confirmation": blocked_result.get("tool_result"),
            "send_customer_email_confirmed": confirmed_result,
        },
        "executed_tool_calls": list(EXECUTION_LEDGER),
        "blocked_write_executed": any(
            call["tool_name"] == "send_customer_email_without_confirmation" for call in EXECUTION_LEDGER
        ),
    }


if __name__ == "__main__":
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))
