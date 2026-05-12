"""Canonical public IDs and backward-compatible aliases for AANA surfaces."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from aana import registry as _registry
from eval_pipeline.route_semantics import route_allows_execution as _route_allows_execution


ROOT = pathlib.Path(__file__).resolve().parents[1]

def _load_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_dirs(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path.parent for path in root.glob("*/manifest.json") if path.is_file())


def _adapter_family_ids_from_manifests() -> tuple[str, ...]:
    ids = []
    for directory in _manifest_dirs(ROOT / "aana" / "adapters"):
        payload = _load_json(directory / "manifest.json")
        ids.append(str(payload.get("family_id") or directory.name))
    return tuple(ids)


def _bundle_ids_and_aliases_from_manifests() -> tuple[tuple[str, ...], dict[str, str]]:
    ids: list[str] = []
    aliases: dict[str, str] = {}
    for directory in _manifest_dirs(ROOT / "aana" / "bundles"):
        payload = _load_json(directory / "manifest.json")
        bundle_id = str(payload.get("bundle_id") or directory.name)
        canonical_id = str(payload.get("canonical_id") or bundle_id)
        ids.append(canonical_id)
        for alias in payload.get("aliases", []):
            if isinstance(alias, str) and alias.strip():
                aliases[alias.strip()] = canonical_id
    return tuple(ids), aliases


ADAPTER_FAMILY_IDS = _registry.adapter_family_ids()
ADAPTER_FAMILY_ALIASES = dict(_registry.ADAPTER_FAMILY_ALIASES)
BUNDLE_IDS = _registry.bundle_ids()
BUNDLE_ALIASES = dict(_registry.registry().bundle_aliases)
ACTION_ROUTES = _registry.ACTION_ROUTES
ROUTE_TABLE = _registry.ROUTE_TABLE
ROUTE_ALIASES = dict(_registry.ROUTE_ALIASES)
TOOL_PRECHECK_ROUTES = _registry.TOOL_PRECHECK_ROUTES
TOOL_CATEGORIES = _registry.TOOL_CATEGORIES
AUTHORIZATION_STATES = _registry.AUTHORIZATION_STATES
AUTHORIZATION_STATE_TABLE = _registry.AUTHORIZATION_STATE_TABLE
RISK_DOMAINS = _registry.RISK_DOMAINS
TOOL_EVIDENCE_TYPES = _registry.TOOL_EVIDENCE_TYPES
TOOL_EVIDENCE_TYPE_ALIASES = dict(_registry.TOOL_EVIDENCE_TYPE_ALIASES)
TRUST_TIERS = _registry.TRUST_TIERS
REDACTION_STATUSES = _registry.REDACTION_STATUSES
RUNTIME_MODES = _registry.RUNTIME_MODES
RUNTIME_MODE_ALIASES = dict(_registry.RUNTIME_MODE_ALIASES)


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


def route_allows_execution(route: str) -> bool:
    try:
        route = canonicalize_route(route)
    except KeyError:
        return False
    return _route_allows_execution(route)


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
    bundle_manifests = {
        str(payload.get("bundle_id") or path.parent.name): payload
        for path in sorted((ROOT / "aana" / "bundles").glob("*/manifest.json"))
        for payload in [_load_json(path)]
    }
    for surface, canonical_ids, aliases in (
        ("adapter_family", ADAPTER_FAMILY_IDS, ADAPTER_FAMILY_ALIASES),
        ("bundle", BUNDLE_IDS, BUNDLE_ALIASES),
        ("route", ACTION_ROUTES, ROUTE_ALIASES),
        ("tool_evidence_type", TOOL_EVIDENCE_TYPES, TOOL_EVIDENCE_TYPE_ALIASES),
        ("runtime_mode", RUNTIME_MODES, RUNTIME_MODE_ALIASES),
    ):
        _validate_surface(issues, surface=surface, canonical_ids=canonical_ids, aliases=aliases)
    if tuple(ROUTE_TABLE) != ACTION_ROUTES:
        _add_issue(issues, "route_table_order_drift", "ROUTE_TABLE order must match canonical action routes.")
    for route in ACTION_ROUTES:
        entry = ROUTE_TABLE.get(route)
        if not isinstance(entry, dict):
            _add_issue(issues, "route_table_missing_route", f"ROUTE_TABLE missing route {route!r}.")
            continue
        if bool(entry.get("execution_allowed")) is not (route == "accept"):
            _add_issue(issues, "route_execution_rule_drift", "Only the accept route may allow execution.")
        if not entry.get("description") or not entry.get("next_step"):
            _add_issue(issues, "route_table_incomplete", f"ROUTE_TABLE route {route!r} must include description and next_step.")

    from aana import sdk
    from aana.adapters import FAMILY_IDS
    from aana.bundles import BUNDLE_ALIASES as CODE_BUNDLE_ALIASES
    from aana.bundles import BUNDLE_IDS as CODE_BUNDLE_IDS
    from eval_pipeline import adapter_gallery
    from eval_pipeline import agent_contract, workflow_contract
    from eval_pipeline import civic_family, enterprise_family
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
    if tuple(AUTHORIZATION_STATE_TABLE) != AUTHORIZATION_STATES:
        _add_issue(issues, "authorization_state_table_order_drift", "authorization-state table order must match canonical authorization states.")
    for expected_rank, state in enumerate(AUTHORIZATION_STATES):
        if AUTHORIZATION_STATE_TABLE[state].get("rank") != expected_rank:
            _add_issue(issues, "authorization_state_rank_drift", "authorization-state ranks must match canonical order.")
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
    expected_sdk_aliases = {
        "enterprise": dict(bundle_manifests["enterprise"].get("sdk_adapter_aliases", {})),
        "enterprise_ops_pilot": dict(bundle_manifests["enterprise_ops_pilot"].get("sdk_adapter_aliases", {})),
        "support": dict(bundle_manifests["enterprise"].get("sdk_adapter_aliases", {})),
        "personal_productivity": dict(bundle_manifests["personal_productivity"].get("sdk_adapter_aliases", {})),
        "government_civic": dict(bundle_manifests["government_civic"].get("sdk_adapter_aliases", {})),
    }
    if sdk.FAMILY_ADAPTER_ALIASES != expected_sdk_aliases:
        _add_issue(issues, "sdk_alias_manifest_drift", "SDK adapter aliases must be derived from bundle manifest sdk_adapter_aliases.")
    expected_bundle_packs = {
        bundle_id: set(payload.get("core_adapter_ids", []))
        for bundle_id, payload in bundle_manifests.items()
    }
    if adapter_gallery.BUNDLE_PACKS != expected_bundle_packs:
        _add_issue(issues, "gallery_pack_manifest_drift", "Adapter gallery pack membership must be derived from bundle manifest core_adapter_ids.")
    if tuple(enterprise_family.ENTERPRISE_CORE_ADAPTERS) != tuple(bundle_manifests["enterprise"].get("core_adapter_ids", [])):
        _add_issue(issues, "enterprise_core_manifest_drift", "Enterprise family core adapters must come from the enterprise bundle manifest.")
    if set(enterprise_family.ENTERPRISE_EVIDENCE_CONNECTORS.values()) != set(bundle_manifests["enterprise"].get("required_evidence_connectors", [])):
        _add_issue(issues, "enterprise_connector_manifest_drift", "Enterprise evidence connectors must come from the enterprise bundle manifest.")
    if tuple(civic_family.CIVIC_CORE_ADAPTERS) != tuple(bundle_manifests["government_civic"].get("core_adapter_ids", [])):
        _add_issue(issues, "civic_core_manifest_drift", "Civic family core adapters must come from the government_civic bundle manifest.")
    if set(civic_family.CIVIC_EVIDENCE_CONNECTORS.values()) != set(bundle_manifests["government_civic"].get("required_evidence_connectors", [])):
        _add_issue(issues, "civic_connector_manifest_drift", "Civic evidence connectors must come from the government_civic bundle manifest.")

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
            "route_table": ROUTE_TABLE,
            "tool_precheck_routes": list(TOOL_PRECHECK_ROUTES),
            "authorization_states": list(AUTHORIZATION_STATES),
            "authorization_state_table": AUTHORIZATION_STATE_TABLE,
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
