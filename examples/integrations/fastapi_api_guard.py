"""FastAPI API-guard example for AANA.

Use this pattern when an agent app should call AANA as a policy service instead
of importing the Python package directly. The example uses FastAPI's in-process
test client so it is runnable without starting a background server.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[2]
while str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from eval_pipeline.fastapi_app import create_app
from examples.integrations.openai_agents.api_guard import AANAApiGuard


LEDGER: list[dict] = []
AANA_DEMO_AUTH_TOKEN = "AANA_DEMO_TOKEN"


def get_public_status(service: str) -> dict:
    LEDGER.append({"tool_name": "get_public_status", "service": service})
    return {"service": service, "status": "ok"}


def send_email(to: str, body: str) -> dict:
    LEDGER.append({"tool_name": "send_email", "to": to})
    return {"sent": True, "to": to}


def run_smoke() -> dict:
    LEDGER.clear()
    app = create_app(auth_token=AANA_DEMO_AUTH_TOKEN, rate_limit_per_minute=0, max_request_bytes=0)
    client = TestClient(app)

    def post_to_fastapi(url: str, payload: dict[str, Any], *, token: str | None = None) -> dict[str, Any]:
        path = "/" + url.rstrip("/").split("/")[-1]
        response = client.post(path, json=payload, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        return response.json()

    guard = AANAApiGuard(base_url="http://aana.local", token=AANA_DEMO_AUTH_TOKEN, post=post_to_fastapi)
    guarded_status = guard.guard_tool(
        get_public_status,
        tool_name="get_public_status",
        tool_category="public_read",
        authorization_state="none",
        evidence_refs=[
            {
                "source_id": "docs.public_status",
                "kind": "policy",
                "trust_tier": "verified",
                "redaction_status": "redacted",
                "summary": "Public status checks do not require identity authorization.",
            }
        ],
        risk_domain="public_information",
    )
    guarded_send_email = guard.guard_tool(
        send_email,
        tool_name="send_email",
        tool_category="write",
        authorization_state="validated",
        evidence_refs=[
            {
                "source_id": "policy.email.confirmation",
                "kind": "policy",
                "trust_tier": "verified",
                "redaction_status": "redacted",
                "summary": "Outbound customer email requires explicit user confirmation before sending.",
            }
        ],
        risk_domain="customer_support",
    )
    accepted = guarded_status(service="docs")
    blocked = guarded_send_email(to="customer@example.com", body="Needs confirmation")
    decision = blocked["aana"]["architecture_decision"]
    return {
        "pattern": "agent proposes -> AANA API checks -> blocked tools do not execute",
        "accepted_route": "accept",
        "accepted_tool_result": accepted,
        "blocked_route": decision["route"],
        "blocked_result": {
            "execution_allowed": blocked["aana"]["execution_policy"]["execution_allowed"],
            "blocked": blocked["blocked"],
        },
        "executed_tool_calls": list(LEDGER),
        "blocked_tool_executed": any(call["tool_name"] == "send_email" for call in LEDGER),
    }


if __name__ == "__main__":
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))
