"""HTTP-only AANA API guard for OpenAI-style tool calls.

Use this when an OpenAI-powered app should call AANA's FastAPI service instead
of importing the Python package directly. The guard fails closed: a tool body
runs only when the API response says the route is `accept` and the execution
policy allows enforcement execution.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable


class AANAApiGuardError(RuntimeError):
    """Raised when the AANA API guard cannot obtain a usable decision."""


def post_json(url: str, payload: dict[str, Any], *, token: str | None = None, timeout: float = 10.0) -> dict[str, Any]:
    """POST JSON to the AANA API and return the decoded JSON body."""

    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AANAApiGuardError(f"AANA API returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise AANAApiGuardError(f"AANA API request failed: {exc.reason}") from exc


def api_allows_execution(decision: dict[str, Any]) -> bool:
    """Return True only for an API decision that explicitly permits execution."""

    architecture = decision.get("architecture_decision") if isinstance(decision.get("architecture_decision"), dict) else {}
    policy = decision.get("execution_policy") if isinstance(decision.get("execution_policy"), dict) else {}
    route = decision.get("route") or architecture.get("route") or decision.get("recommended_action")
    return bool(
        route == "accept"
        and decision.get("gate_decision") == "pass"
        and decision.get("recommended_action") == "accept"
        and not (decision.get("hard_blockers") or architecture.get("hard_blockers"))
        and not decision.get("validation_errors")
        and policy.get("execution_allowed", True)
    )


class AANAApiGuard:
    """Small client for guarding OpenAI agent tools through AANA FastAPI."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8766",
        token: str | None = None,
        post: Callable[..., dict[str, Any]] = post_json,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._post = post

    def pre_tool_check(self, event: dict[str, Any]) -> dict[str, Any]:
        return self._post(f"{self.base_url}/pre-tool-check", event, token=self.token)

    def agent_check(self, event: dict[str, Any]) -> dict[str, Any]:
        return self._post(f"{self.base_url}/agent-check", event, token=self.token)

    def guard_tool(
        self,
        tool: Callable[..., Any],
        *,
        tool_name: str,
        tool_category: str,
        authorization_state: str,
        evidence_refs: list[str | dict[str, Any]],
        risk_domain: str,
        recommended_route: str = "accept",
    ) -> Callable[..., Any]:
        """Wrap a side-effecting OpenAI tool function with the AANA API guard."""

        def guarded_tool(**kwargs: Any) -> Any:
            event = {
                "tool_name": tool_name,
                "tool_category": tool_category,
                "authorization_state": authorization_state,
                "evidence_refs": evidence_refs,
                "risk_domain": risk_domain,
                "proposed_arguments": dict(kwargs),
                "recommended_route": recommended_route,
            }
            decision = self.pre_tool_check(event)
            if not api_allows_execution(decision):
                return {"blocked": True, "aana": decision}
            return tool(**kwargs)

        return guarded_tool


def send_email(to: str, body: str) -> dict[str, Any]:
    """Example OpenAI tool body. Replace with a real integration in apps."""

    return {"sent": True, "to": to}


def build_guarded_send_email() -> Callable[..., Any]:
    """Build a guarded OpenAI-style email tool from environment config."""

    guard = AANAApiGuard(
        base_url=os.environ.get("AANA_API_URL", "http://127.0.0.1:8766"),
        token=os.environ.get("AANA_BRIDGE_TOKEN"),
    )
    return guard.guard_tool(
        send_email,
        tool_name="send_email",
        tool_category="write",
        authorization_state="user_claimed",
        evidence_refs=["draft_id:123"],
        risk_domain="customer_support",
    )


if __name__ == "__main__":
    guarded_send_email = build_guarded_send_email()
    print(json.dumps(guarded_send_email(to="customer@example.com", body="Needs confirmation"), indent=2, sort_keys=True))
