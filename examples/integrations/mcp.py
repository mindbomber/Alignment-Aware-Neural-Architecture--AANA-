"""AANA wrapper example for MCP tool-call handlers."""

from __future__ import annotations

import aana


def get_public_status(arguments: dict) -> dict:
    return {"service": arguments["service"], "status": "ok"}


guarded_handler = aana.mcp_tool_middleware(get_public_status, tool_name="get_public_status")


if __name__ == "__main__":
    result = guarded_handler({"service": "docs"})
    decision = guarded_handler.aana_last_gate["result"]["architecture_decision"]
    print({"tool_result": result, "aana_route": decision["route"]})

