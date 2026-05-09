"""AANA wrapper example for CrewAI-style tool objects."""

from __future__ import annotations

import aana


class PublicStatusTool:
    name = "get_public_status"
    description = "Read public service status."

    def _run(self, service: str) -> dict:
        return {"service": service, "status": "ok"}


guarded_tool = aana.crewai_tool_middleware(PublicStatusTool())


if __name__ == "__main__":
    result = guarded_tool._run(service="docs")
    decision = guarded_tool.aana_last_gate["result"]["architecture_decision"]
    print({"tool_result": result, "aana_route": decision["route"]})

