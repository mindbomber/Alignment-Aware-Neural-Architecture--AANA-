"""AANA wrapper example for MCP tool-call handlers."""

from __future__ import annotations

import json

import aana


LEDGER: list[dict] = []


def get_public_status(arguments: dict) -> dict:
    LEDGER.append({"tool_name": "get_public_status", "service": arguments["service"]})
    return {"service": arguments["service"], "status": "ok"}


guarded_handler = aana.mcp_tool_middleware(get_public_status, tool_name="get_public_status")


def export_customer_record(arguments: dict) -> dict:
    LEDGER.append({"tool_name": "export_customer_record", "customer_id": arguments["customer_id"]})
    return {"exported": True, "customer_id": arguments["customer_id"]}


guarded_export_handler = aana.mcp_tool_middleware(
    export_customer_record,
    tool_name="export_customer_record",
    metadata={
        "tool_category": "write",
        "authorization_state": "validated",
        "risk_domain": "customer_support",
        "evidence_refs": [
            {
                "source_id": "policy.export.confirmation",
                "kind": "policy",
                "trust_tier": "verified",
                "redaction_status": "redacted",
                "summary": "Customer record exports require explicit confirmation before execution.",
            }
        ],
    },
    raise_on_block=False,
)


def run_smoke() -> dict:
    LEDGER.clear()
    accepted = guarded_handler({"service": "docs"})
    blocked = guarded_export_handler({"customer_id": "cust_redacted"})
    accepted_route = guarded_handler.aana_last_gate["result"]["architecture_decision"]["route"]
    blocked_route = guarded_export_handler.aana_last_gate["result"]["architecture_decision"]["route"]
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
        "blocked_tool_executed": any(call["tool_name"] == "export_customer_record" for call in LEDGER),
    }


if __name__ == "__main__":
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))
