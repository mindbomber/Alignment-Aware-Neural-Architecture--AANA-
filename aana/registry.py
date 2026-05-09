"""Unified registry for AANA public platform surfaces.

This module is the dependency-light source for adapter families, product
bundles, HF dataset registry entries, evidence connector IDs, routes, and
backward-compatible aliases. Higher-level tools can keep their old import paths,
but should read through this registry instead of maintaining local constants.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from eval_pipeline.authorization_state import AUTHORIZATION_STATES, AUTHORIZATION_STATE_TABLE
from eval_pipeline.route_semantics import ACTION_ROUTES, ROUTE_TABLE, route_allows_execution


ROOT = pathlib.Path(__file__).resolve().parents[1]
ADAPTERS_ROOT = ROOT / "aana" / "adapters"
BUNDLES_ROOT = ROOT / "aana" / "bundles"
HF_DATASET_REGISTRY_PATH = ROOT / "examples" / "hf_dataset_validation_registry.json"

ADAPTER_FAMILY_ALIASES: dict[str, str] = {}
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
TOOL_PRECHECK_ROUTES = (
    "accept",
    "ask",
    "defer",
    "refuse",
)
TOOL_CATEGORIES = (
    "public_read",
    "private_read",
    "write",
    "unknown",
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


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _manifest_dirs(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path.parent for path in root.glob("*/manifest.json") if path.is_file())


def _adapter_families(root: pathlib.Path) -> dict[str, dict[str, Any]]:
    families: dict[str, dict[str, Any]] = {}
    for directory in _manifest_dirs(root / "aana" / "adapters"):
        payload = _load_json(directory / "manifest.json")
        family_id = str(payload.get("family_id") or directory.name)
        families[family_id] = payload
    return dict(sorted(families.items()))


def _bundles(root: pathlib.Path) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    bundles: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    for directory in _manifest_dirs(root / "aana" / "bundles"):
        payload = _load_json(directory / "manifest.json")
        bundle_id = str(payload.get("bundle_id") or directory.name)
        canonical_id = str(payload.get("canonical_id") or bundle_id)
        enriched = dict(payload)
        enriched.setdefault("canonical_id", canonical_id)
        for alias in payload.get("aliases", []):
            if isinstance(alias, str) and alias.strip():
                aliases[alias.strip()] = canonical_id
        bundles[canonical_id] = enriched
    for bundle_id, payload in bundles.items():
        payload.setdefault("aliases", sorted(alias for alias, target in aliases.items() if target == bundle_id))
    return dict(sorted(bundles.items())), dict(sorted(aliases.items()))


def _hf_dataset_registry(root: pathlib.Path) -> dict[str, Any]:
    path = root / "examples" / "hf_dataset_validation_registry.json"
    return _load_json(path) if path.exists() else {}


def _evidence_connectors() -> dict[str, Any]:
    from eval_pipeline import evidence_integrations

    return {
        "core": list(evidence_integrations.CORE_CONNECTOR_CONTRACT_IDS),
        "personal_productivity": list(evidence_integrations.PERSONAL_CONNECTOR_CONTRACT_IDS),
        "government_civic": list(evidence_integrations.CIVIC_CONNECTOR_CONTRACT_IDS),
        "support": list(evidence_integrations.SUPPORT_CONNECTOR_CONTRACT_IDS),
        "stubs": sorted(evidence_integrations.integration_stub_map()),
    }


@dataclass(frozen=True)
class AANARegistry:
    root: pathlib.Path
    adapter_families: dict[str, dict[str, Any]]
    bundles: dict[str, dict[str, Any]]
    bundle_aliases: dict[str, str]
    hf_datasets: dict[str, Any]
    evidence_connectors: dict[str, Any]
    routes: tuple[str, ...]
    route_table: dict[str, dict[str, Any]]
    aliases: dict[str, dict[str, str]]

    @property
    def adapter_family_ids(self) -> tuple[str, ...]:
        return tuple(self.adapter_families)

    @property
    def bundle_ids(self) -> tuple[str, ...]:
        return tuple(self.bundles)

    def canonicalize_bundle_id(self, bundle_id: str) -> str:
        if bundle_id in self.bundles:
            return bundle_id
        try:
            return self.bundle_aliases[bundle_id]
        except KeyError as exc:
            raise KeyError(f"Unknown AANA product bundle ID: {bundle_id}") from exc

    def canonicalize_adapter_family_id(self, family_id: str) -> str:
        if family_id in self.adapter_families:
            return family_id
        try:
            return ADAPTER_FAMILY_ALIASES[family_id]
        except KeyError as exc:
            raise KeyError(f"Unknown AANA adapter family ID: {family_id}") from exc

    def load_adapter_family(self, family_id: str) -> dict[str, Any]:
        return dict(self.adapter_families[self.canonicalize_adapter_family_id(family_id)])

    def load_bundle(self, bundle_id: str) -> dict[str, Any]:
        canonical_id = self.canonicalize_bundle_id(bundle_id)
        payload = dict(self.bundles[canonical_id])
        payload.setdefault("canonical_id", canonical_id)
        payload.setdefault("aliases", self.aliases_for_bundle(canonical_id))
        return payload

    def aliases_for_bundle(self, bundle_id: str) -> list[str]:
        canonical_id = self.canonicalize_bundle_id(bundle_id)
        return sorted(alias for alias, target in self.bundle_aliases.items() if target == canonical_id)

    def bundle_adapter_aliases(self, bundle_id: str) -> dict[str, str]:
        aliases = self.load_bundle(bundle_id).get("sdk_adapter_aliases", {})
        return dict(aliases) if isinstance(aliases, dict) else {}

    def bundle_ids_for_adapter(self, adapter_id: str) -> list[str]:
        bundle_ids = []
        for bundle_id, payload in self.bundles.items():
            if adapter_id in payload.get("core_adapter_ids", []):
                bundle_ids.append(bundle_id)
        return sorted(bundle_ids)

    def dataset_entries(self) -> list[dict[str, Any]]:
        datasets = self.hf_datasets.get("datasets", []) if isinstance(self.hf_datasets, dict) else []
        return list(datasets) if isinstance(datasets, list) else []


@lru_cache(maxsize=1)
def load_registry(root: str | pathlib.Path | None = None) -> AANARegistry:
    root_path = pathlib.Path(root or ROOT)
    adapter_families = _adapter_families(root_path)
    bundles, bundle_aliases = _bundles(root_path)
    return AANARegistry(
        root=root_path,
        adapter_families=adapter_families,
        bundles=bundles,
        bundle_aliases=bundle_aliases,
        hf_datasets=_hf_dataset_registry(root_path),
        evidence_connectors=_evidence_connectors(),
        routes=ACTION_ROUTES,
        route_table=ROUTE_TABLE,
        aliases={
            "adapter_families": dict(ADAPTER_FAMILY_ALIASES),
            "bundles": bundle_aliases,
            "routes": dict(ROUTE_ALIASES),
            "tool_evidence_types": dict(TOOL_EVIDENCE_TYPE_ALIASES),
            "runtime_modes": dict(RUNTIME_MODE_ALIASES),
        },
    )


def registry() -> AANARegistry:
    return load_registry()


def adapter_family_ids() -> tuple[str, ...]:
    return registry().adapter_family_ids


def bundle_ids() -> tuple[str, ...]:
    return registry().bundle_ids


def load_adapter_family(family_id: str) -> dict[str, Any]:
    return registry().load_adapter_family(family_id)


def load_adapter_families() -> dict[str, dict[str, Any]]:
    return {family_id: registry().load_adapter_family(family_id) for family_id in registry().adapter_family_ids}


def load_bundle(bundle_id: str) -> dict[str, Any]:
    return registry().load_bundle(bundle_id)


def load_bundles() -> dict[str, dict[str, Any]]:
    return {bundle_id: registry().load_bundle(bundle_id) for bundle_id in registry().bundle_ids}


def canonicalize_bundle_id(bundle_id: str) -> str:
    return registry().canonicalize_bundle_id(bundle_id)


def canonicalize_adapter_family_id(family_id: str) -> str:
    return registry().canonicalize_adapter_family_id(family_id)


def aliases_for_bundle(bundle_id: str) -> list[str]:
    return registry().aliases_for_bundle(bundle_id)


def bundle_adapter_aliases(bundle_id: str) -> dict[str, str]:
    return registry().bundle_adapter_aliases(bundle_id)


def bundle_ids_for_adapter(adapter_id: str) -> list[str]:
    return registry().bundle_ids_for_adapter(adapter_id)


__all__ = [
    "ACTION_ROUTES",
    "ADAPTER_FAMILY_ALIASES",
    "AANARegistry",
    "AUTHORIZATION_STATES",
    "AUTHORIZATION_STATE_TABLE",
    "REDACTION_STATUSES",
    "RISK_DOMAINS",
    "ROUTE_ALIASES",
    "ROUTE_TABLE",
    "RUNTIME_MODES",
    "RUNTIME_MODE_ALIASES",
    "TOOL_CATEGORIES",
    "TOOL_EVIDENCE_TYPES",
    "TOOL_EVIDENCE_TYPE_ALIASES",
    "TOOL_PRECHECK_ROUTES",
    "TRUST_TIERS",
    "adapter_family_ids",
    "aliases_for_bundle",
    "bundle_adapter_aliases",
    "bundle_ids",
    "bundle_ids_for_adapter",
    "canonicalize_adapter_family_id",
    "canonicalize_bundle_id",
    "load_adapter_families",
    "load_adapter_family",
    "load_bundle",
    "load_bundles",
    "load_registry",
    "registry",
    "route_allows_execution",
]
