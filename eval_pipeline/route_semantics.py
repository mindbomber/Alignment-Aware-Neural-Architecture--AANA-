"""Canonical AANA route semantics shared by SDKs, APIs, and middleware."""

from __future__ import annotations


ACTION_ROUTES = (
    "accept",
    "revise",
    "retrieve",
    "ask",
    "defer",
    "refuse",
)
ROUTE_TABLE = {
    "accept": {
        "description": "Proceed only within the checked scope.",
        "execution_allowed": True,
        "next_step": "execute_checked_action",
    },
    "revise": {
        "description": "Revise the candidate output or action, then recheck before execution.",
        "execution_allowed": False,
        "next_step": "revise_then_recheck",
    },
    "retrieve": {
        "description": "Retrieve missing grounding or policy evidence, then recheck before execution.",
        "execution_allowed": False,
        "next_step": "retrieve_evidence_then_recheck",
    },
    "ask": {
        "description": "Ask the user or runtime for missing information, authorization, or confirmation.",
        "execution_allowed": False,
        "next_step": "ask_then_recheck",
    },
    "defer": {
        "description": "Route to stronger evidence, a domain owner, review queue, or human reviewer.",
        "execution_allowed": False,
        "next_step": "defer_to_review",
    },
    "refuse": {
        "description": "Do not execute because a hard blocker prevents safe action.",
        "execution_allowed": False,
        "next_step": "refuse_action",
    },
}


def route_allows_execution(route: str | None) -> bool:
    if route not in ROUTE_TABLE:
        return False
    return bool(ROUTE_TABLE[route]["execution_allowed"])
