"""Plain Python AANA tool wrapper example.

This is the smallest integration surface: a normal Python callable is wrapped
with AANA before an agent runtime can execute it.
"""

from __future__ import annotations

import json

import aana


LEDGER: list[dict] = []


def get_public_status(service: str) -> dict:
    LEDGER.append({"tool_name": "get_public_status", "service": service})
    return {"service": service, "status": "ok"}


def send_email(to: str, body: str) -> dict:
    LEDGER.append({"tool_name": "send_email", "to": to})
    return {"sent": True, "to": to}


guarded_status = aana.wrap_agent_tool(get_public_status)
guarded_send_email = aana.wrap_agent_tool(
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


def run_smoke() -> dict:
    LEDGER.clear()
    accepted = guarded_status(service="docs")
    blocked = guarded_send_email(to="customer@example.com", body="Needs confirmation")
    accepted_route = guarded_status.aana_last_gate["result"]["architecture_decision"]["route"]
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
