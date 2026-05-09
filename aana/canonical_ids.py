"""Canonical public IDs and backward-compatible aliases for AANA surfaces."""

from __future__ import annotations

import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]

ADAPTER_FAMILY_IDS = (
    "privacy_pii",
    "grounded_qa",
    "agent_tool_use",
    "governance_compliance",
    "security_devops",
    "domain_risk",
)
ADAPTER_FAMILY_ALIASES: dict[str, str] = {}

BUNDLE_IDS = (
    "enterprise",
    "personal_productivity",
    "government_civic",
)
BUNDLE_ALIASES = {
    "civic_government": "government_civic",
}

ACTION_ROUTES = (
    "accept",
    "revise",
    "retrieve",
    "ask",
    "refuse",
    "defer",
)
TOOL_PRECHECK_ROUTES = (
    "accept",
    "ask",
    "defer",
    "refuse",
)
ROUTE_ALIASES = {
    "block": "refuse",
    "route_to_review": "defer",
    "human_review": "defer",
    "request_approval": "ask",
    "request_confirmation": "ask",
    "retrieve_evidence": "retrieve",
    "revise_upstream_output": "revise",
    "ask_clarification": "ask",
    "defer_human_review": "defer",
}

TOOL_CATEGORIES = (
    "public_read",
    "private_read",
    "write",
    "unknown",
)
AUTHORIZATION_STATES = (
    "none",
    "user_claimed",
    "authenticated",
    "validated",
    "confirmed",
)
RISK_DOMAINS = (
    "devops",
    "finance",
    "education",
    "hr",
    "legal",
    "pharma",
    "healthcare",
    "commerce",
    "customer_support",
    "security",
    "research",
    "personal_productivity",
    "public_information",
    "unknown",
)
TOOL_EVIDENCE_TYPES = (
    "user_message",
    "assistant_message",
    "tool_result",
    "policy",
    "auth_event",
    "approval",
    "system_state",
    "audit_record",
    "other",
)
TOOL_EVIDENCE_TYPE_ALIASES = {
    "user_instruction": "user_message",
    "requested_action": "user_message",
    "draft": "assistant_message",
    "draft_email": "assistant_message",
    "recipient_metadata": "tool_result",
    "file_metadata": "tool_result",
    "calendar_freebusy": "tool_result",
    "attendee_list": "tool_result",
    "live_quote": "tool_result",
    "cart": "tool_result",
    "retrieved_documents": "tool_result",
    "citation_index": "tool_result",
    "approval_policy": "policy",
    "source_registry": "policy",
    "evidence_limits": "policy",
    "approval_state": "approval",
}
TRUST_TIERS = (
    "verified",
    "runtime",
    "user_claimed",
    "unverified",
    "unknown",
)
REDACTION_STATUSES = (
    "public",
    "redacted",
    "sensitive",
    "unknown",
)
RUNTIME_MODES = (
    "enforce",
    "shadow",
)
RUNTIME_MODE_ALIASES = {
    "enforced": "enforce",
    "enforcement": "enforce",
    "observe_only": "shadow",
    "advisory": "shadow",
}


def canonicalize(identifier: str, canonical_ids: tuple[str, ...], aliases: dict[str, str], *, surface: str) -> str:
    if identifier in canonical_ids:
        return identifier
    try:
        return aliases[identifier]
    except KeyError as exc:
        raise KeyError(f"Unknown AANA {surface} ID: {identifier}") from exc


def canonicalize_adapter_family_id(identifier: str) -> str:
    return canonicalize(identifier, ADAPTER_FAMILY_IDS, ADAPTER_FAMILY_ALIASES, surface="adapter family")


def canonicalize_bundle_id(identifier: str) -> str:
    return canonicalize(identifier, BUNDLE_IDS, BUNDLE_ALIASES, surface="product bundle")


def canonicalize_route(identifier: str) -> str:
    return canonicalize(identifier, ACTION_ROUTES, ROUTE_ALIASES, surface="route")


def canonicalize_tool_evidence_type(identifier: str) -> str:
    return canonicalize(identifier, TOOL_EVIDENCE_TYPES, TOOL_EVIDENCE_TYPE_ALIASES, surface="tool evidence type")


def canonicalize_runtime_mode(identifier: str) -> str:
    return canonicalize(identifier, RUNTIME_MODES, RUNTIME_MODE_ALIASES, surface="runtime mode")


def aliases_for(canonical_id: str, aliases: dict[str, str]) -> list[str]:
    return sorted(alias for alias, target in aliases.items() if target == canonical_id)


def _add_issue(issues: list[dict[str, str]], code: str, message: str) -> None:
    issues.append({"code": code, "message": message})


def _validate_surface(
    issues: list[dict[str, str]],
    *,
    surface: str,
    canonical_ids: tuple[str, ...],
    aliases: dict[str, str],
) -> None:
    if len(set(canonical_ids)) != len(canonical_ids):
        _add_issue(issues, "duplicate_canonical_id", f"{surface} contains duplicate canonical IDs.")
    canonical_set = set(canonical_ids)
    for alias, target in aliases.items():
        if alias in canonical_set:
            _add_issue(issues, "alias_redefines_canonical_id", f"{surface} alias {alias!r} redefines a canonical ID.")
        if target not in canonical_set:
            _add_issue(issues, "alias_targets_unknown_canonical_id", f"{surface} alias {alias!r} targets unknown ID {target!r}.")
        if target in aliases:
            _add_issue(issues, "alias_targets_alias", f"{surface} alias {alias!r} targets alias {target!r} instead of a canonical ID.")
        if alias == target:
            _add_issue(issues, "identity_alias_not_allowed", f"{surface} alias map contains identity alias {alias!r}.")


def _schema_enum(path: pathlib.Path, *keys: str) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    current: Any = payload
    for key in keys:
        current = current[key]
    return list(current)


def validate_canonical_ids() -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    for surface, canonical_ids, aliases in (
        ("adapter_family", ADAPTER_FAMILY_IDS, ADAPTER_FAMILY_ALIASES),
        ("bundle", BUNDLE_IDS, BUNDLE_ALIASES),
        ("route", ACTION_ROUTES, ROUTE_ALIASES),
        ("tool_evidence_type", TOOL_EVIDENCE_TYPES, TOOL_EVIDENCE_TYPE_ALIASES),
        ("runtime_mode", RUNTIME_MODES, RUNTIME_MODE_ALIASES),
    ):
        _validate_surface(issues, surface=surface, canonical_ids=canonical_ids, aliases=aliases)

    from aana import sdk
    from aana.adapters import FAMILY_IDS
    from aana.bundles import BUNDLE_ALIASES as CODE_BUNDLE_ALIASES
    from aana.bundles import BUNDLE_IDS as CODE_BUNDLE_IDS
    from eval_pipeline import agent_contract, workflow_contract
    from eval_pipeline.pre_tool_call_gate import AUTH_STATES_BY_ORDER, ROUTE_ORDER

    if tuple(FAMILY_IDS) != ADAPTER_FAMILY_IDS:
        _add_issue(issues, "adapter_family_constant_drift", "aana.adapters.FAMILY_IDS must match canonical adapter family IDs.")
    if tuple(CODE_BUNDLE_IDS) != BUNDLE_IDS:
        _add_issue(issues, "bundle_constant_drift", "aana.bundles.BUNDLE_IDS must match canonical bundle IDs.")
    if dict(CODE_BUNDLE_ALIASES) != BUNDLE_ALIASES:
        _add_issue(issues, "bundle_alias_drift", "aana.bundles.BUNDLE_ALIASES must match canonical backward-compatible aliases.")
    if tuple(agent_contract.ALLOWED_ACTIONS) != ACTION_ROUTES:
        _add_issue(issues, "agent_route_constant_drift", "eval_pipeline.agent_contract.ALLOWED_ACTIONS must match canonical action routes.")
    if set(workflow_contract.DEFAULT_ALLOWED_ACTIONS) != set(ACTION_ROUTES):
        _add_issue(issues, "workflow_route_constant_drift", "workflow default allowed actions must contain exactly the canonical action routes.")
    if tuple(ROUTE_ORDER) != TOOL_PRECHECK_ROUTES:
        _add_issue(issues, "tool_precheck_route_drift", "pre-tool route order must match canonical pre-tool routes.")
    if tuple(AUTH_STATES_BY_ORDER) != AUTHORIZATION_STATES:
        _add_issue(issues, "authorization_state_drift", "pre-tool authorization order must match canonical authorization states.")
    if set(sdk.TOOL_CATEGORIES) != set(TOOL_CATEGORIES):
        _add_issue(issues, "sdk_tool_category_drift", "SDK tool categories must match canonical IDs.")
    if set(sdk.AUTHORIZATION_STATES) != set(AUTHORIZATION_STATES):
        _add_issue(issues, "sdk_authorization_state_drift", "SDK authorization states must match canonical IDs.")
    if set(sdk.TOOL_PRECHECK_ROUTES) != set(TOOL_PRECHECK_ROUTES):
        _add_issue(issues, "sdk_tool_precheck_route_drift", "SDK pre-tool routes must match canonical IDs.")
    if set(sdk.EXECUTION_MODES) != set(RUNTIME_MODES):
        _add_issue(issues, "sdk_runtime_mode_drift", "SDK execution modes must match canonical runtime modes.")
    if set(sdk.RISK_DOMAINS) != set(RISK_DOMAINS):
        _add_issue(issues, "sdk_risk_domain_drift", "SDK risk domains must match canonical IDs.")

    schema_path = ROOT / "schemas" / "agent_tool_precheck.schema.json"
    schema_properties = json.loads(schema_path.read_text(encoding="utf-8"))["properties"]
    schema_checks = {
        "tool_category": (TOOL_CATEGORIES, schema_properties["tool_category"]["enum"]),
        "authorization_state": (AUTHORIZATION_STATES, schema_properties["authorization_state"]["enum"]),
        "risk_domain": (RISK_DOMAINS, schema_properties["risk_domain"]["enum"]),
        "recommended_route": (TOOL_PRECHECK_ROUTES, schema_properties["recommended_route"]["enum"]),
        "tool_evidence_type": (TOOL_EVIDENCE_TYPES, schema_properties["evidence_refs"]["items"]["properties"]["kind"]["enum"]),
        "trust_tier": (TRUST_TIERS, schema_properties["evidence_refs"]["items"]["properties"]["trust_tier"]["enum"]),
        "redaction_status": (REDACTION_STATUSES, schema_properties["evidence_refs"]["items"]["properties"]["redaction_status"]["enum"]),
    }
    for name, (canonical_values, schema_values) in schema_checks.items():
        if tuple(schema_values) != tuple(canonical_values):
            _add_issue(issues, "schema_enum_drift", f"agent_tool_precheck.schema.json {name} enum must match canonical IDs.")

    return {
        "valid": not issues,
        "issues": issues,
        "canonical_ids": {
            "adapter_families": list(ADAPTER_FAMILY_IDS),
            "bundles": list(BUNDLE_IDS),
            "action_routes": list(ACTION_ROUTES),
            "tool_precheck_routes": list(TOOL_PRECHECK_ROUTES),
            "tool_evidence_types": list(TOOL_EVIDENCE_TYPES),
            "runtime_modes": list(RUNTIME_MODES),
        },
        "aliases": {
            "adapter_families": dict(sorted(ADAPTER_FAMILY_ALIASES.items())),
            "bundles": dict(sorted(BUNDLE_ALIASES.items())),
            "routes": dict(sorted(ROUTE_ALIASES.items())),
            "tool_evidence_types": dict(sorted(TOOL_EVIDENCE_TYPE_ALIASES.items())),
            "runtime_modes": dict(sorted(RUNTIME_MODE_ALIASES.items())),
        },
    }
