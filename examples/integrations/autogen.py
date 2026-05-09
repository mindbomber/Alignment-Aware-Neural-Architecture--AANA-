"""AANA wrapper example for AutoGen-style registered tool functions."""

from __future__ import annotations

import aana


@aana.autogen_tool_middleware(
    metadata={
        "tool_category": "public_read",
        "authorization_state": "none",
        "risk_domain": "public_information",
    }
)
def get_public_status(service: str) -> dict:
    return {"service": service, "status": "ok"}


if __name__ == "__main__":
    result = get_public_status(service="docs")
    decision = get_public_status.aana_last_gate["result"]["architecture_decision"]
    print({"tool_result": result, "aana_route": decision["route"]})

