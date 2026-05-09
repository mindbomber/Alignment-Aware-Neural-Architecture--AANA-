"""Canonical authorization-state semantics for AANA tool checks.

This module is intentionally dependency-light so the registry, SDK, gate,
adapters, and tests can share one source of truth for authorization ordering and
execution transitions.
"""

from __future__ import annotations

from typing import Any


AUTHORIZATION_STATES = ("none", "user_claimed", "authenticated", "validated", "confirmed")

AUTHORIZATION_STATE_TABLE: dict[str, dict[str, Any]] = {
    "none": {
        "rank": 0,
        "meaning": "No usable authorization context is available.",
        "private_read_allowed": False,
        "write_schema_accept_allowed": False,
        "write_execution_allowed": False,
    },
    "user_claimed": {
        "rank": 1,
        "meaning": "The user asked for or claimed authority, but identity is not verified.",
        "private_read_allowed": False,
        "write_schema_accept_allowed": False,
        "write_execution_allowed": False,
    },
    "authenticated": {
        "rank": 2,
        "meaning": "The user's identity/session is authenticated.",
        "private_read_allowed": True,
        "write_schema_accept_allowed": False,
        "write_execution_allowed": False,
    },
    "validated": {
        "rank": 3,
        "meaning": "The target object, ownership, policy, or eligibility was validated.",
        "private_read_allowed": True,
        "write_schema_accept_allowed": True,
        "write_execution_allowed": False,
    },
    "confirmed": {
        "rank": 4,
        "meaning": "The user explicitly confirmed this consequential action.",
        "private_read_allowed": True,
        "write_schema_accept_allowed": True,
        "write_execution_allowed": True,
    },
}

AUTHORIZATION_STATE_RANK = {state: meta["rank"] for state, meta in AUTHORIZATION_STATE_TABLE.items()}

AUTHORIZATION_STATE_ALIASES = {
    "": "none",
    "anonymous": "none",
    "unauthenticated": "none",
    "unauthorized": "none",
    "unknown": "none",
    "claimed": "user_claimed",
    "requested": "user_claimed",
    "user_requested": "user_claimed",
    "logged_in": "authenticated",
    "login": "authenticated",
    "session": "authenticated",
    "verified_identity": "authenticated",
    "verified": "validated",
    "eligible": "validated",
    "policy_validated": "validated",
    "ownership_validated": "validated",
    "approved": "confirmed",
    "confirmation": "confirmed",
    "explicit_confirmation": "confirmed",
    "user_confirmed": "confirmed",
}


def canonicalize_authorization_state(value: object, *, default: str = "none") -> str:
    """Return a canonical auth state, fail-closing to ``default`` for unknowns."""

    state = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if state in AUTHORIZATION_STATE_TABLE:
        return state
    if state in AUTHORIZATION_STATE_ALIASES:
        return AUTHORIZATION_STATE_ALIASES[state]
    return default


def authorization_rank(state: object) -> int:
    return AUTHORIZATION_STATE_RANK[canonicalize_authorization_state(state)]


def auth_state_at_least(state: object, minimum: str) -> bool:
    return authorization_rank(state) >= AUTHORIZATION_STATE_RANK[minimum]


def private_read_allowed(state: object) -> bool:
    return bool(AUTHORIZATION_STATE_TABLE[canonicalize_authorization_state(state)]["private_read_allowed"])


def write_schema_accept_allowed(state: object) -> bool:
    """Return True when a v1 write event may be schema-valid with accept.

    The schema allows ``validated`` for backward compatibility, but runtime
    execution still requires ``confirmed``.
    """

    return bool(AUTHORIZATION_STATE_TABLE[canonicalize_authorization_state(state)]["write_schema_accept_allowed"])


def write_execution_allowed(state: object) -> bool:
    return bool(AUTHORIZATION_STATE_TABLE[canonicalize_authorization_state(state)]["write_execution_allowed"])


def needs_confirmation_for_write(state: object) -> bool:
    return not write_execution_allowed(state)


def authorization_transition_report(state: object, *, source_state: object | None = None) -> dict[str, Any]:
    canonical = canonicalize_authorization_state(state)
    raw_source = state if source_state is None else source_state
    normalized_source = str(raw_source or "").strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "source_state": raw_source,
        "canonical_state": canonical,
        "ambiguous": normalized_source not in AUTHORIZATION_STATE_TABLE,
        "rank": AUTHORIZATION_STATE_RANK[canonical],
        "private_read_allowed": private_read_allowed(canonical),
        "write_schema_accept_allowed": write_schema_accept_allowed(canonical),
        "write_execution_allowed": write_execution_allowed(canonical),
        "needs_authentication": not auth_state_at_least(canonical, "authenticated"),
        "needs_validation": not auth_state_at_least(canonical, "validated"),
        "needs_confirmation": not auth_state_at_least(canonical, "confirmed"),
    }
