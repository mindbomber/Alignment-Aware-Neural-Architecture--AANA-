"""AANA wrapper example for OpenAI Agents SDK tools.

The current OpenAI Agents SDK runs agents with `Agent` plus `Runner`, and tools
can be ordinary Python functions registered with the SDK's function-tool
primitive. This example keeps the smoke path dependency-free while showing where
the AANA wrapper sits.
"""

from __future__ import annotations

import aana


def get_public_status(service: str) -> dict:
    return {"service": service, "status": "ok"}


guarded_get_public_status = aana.wrap_agent_tool(get_public_status)


def build_openai_agents_sdk_tool():
    """Return an OpenAI Agents SDK function tool when `openai-agents` is installed."""

    try:
        from agents import function_tool
    except ImportError as exc:  # pragma: no cover - example path for optional dependency.
        raise RuntimeError("Install openai-agents to register this with the OpenAI Agents SDK.") from exc

    return function_tool(guarded_get_public_status)


def build_agent():
    """Illustrative Agent construction for real OpenAI Agents SDK projects."""

    try:
        from agents import Agent
    except ImportError as exc:  # pragma: no cover - example path for optional dependency.
        raise RuntimeError("Install openai-agents to build the SDK Agent.") from exc

    return Agent(
        name="AANA guarded support agent",
        instructions="Use tools only after AANA has checked the proposed action.",
        tools=[build_openai_agents_sdk_tool()],
    )


if __name__ == "__main__":
    result = guarded_get_public_status(service="docs")
    decision = guarded_get_public_status.aana_last_gate["result"]["architecture_decision"]
    print({"tool_result": result, "aana_route": decision["route"]})

