"""Examples for wrapping agent tools with AANA.

Pattern:
    agent proposes -> AANA checks -> tool executes only if allowed
"""

import aana


def print_decision(gate):
    decision = gate["result"]["architecture_decision"]
    print(decision["route"], decision["aix_score"], decision["hard_blockers"])


def get_public_status(service: str):
    return {"service": service, "status": "ok"}


safe_public_status = aana.wrap_agent_tool(get_public_status, on_decision=print_decision)


@aana.openai_agents_tool_middleware(
    metadata={
        "tool_category": "write",
        "authorization_state": "confirmed",
        "risk_domain": "customer_support",
        "evidence_refs": [
            aana.tool_evidence_ref(
                source_id="approval.user-confirmed-send",
                kind="approval",
                trust_tier="verified",
                redaction_status="redacted",
                summary="User confirmed the final customer email send.",
            )
        ],
    }
)
def send_customer_email(to: str, body: str):
    return {"sent": True, "to": to}


def mcp_lookup(arguments):
    return {"result": f"public lookup for {arguments['query']}"}


guarded_mcp_lookup = aana.mcp_tool_middleware(
    mcp_lookup,
    tool_name="search_public_docs",
    metadata={
        "tool_category": "public_read",
        "authorization_state": "none",
        "risk_domain": "research",
    },
)


if __name__ == "__main__":
    print(safe_public_status("docs"))
    print(send_customer_email(to="customer@example.com", body="Approved draft"))
    print(guarded_mcp_lookup({"query": "AANA pre-tool-call contract"}))
