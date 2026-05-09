"""Backward-compatible product bundle registry facade."""

from __future__ import annotations

from typing import Any

from aana import registry as _registry


BUNDLE_IDS = _registry.bundle_ids()
BUNDLE_ALIASES = dict(_registry.registry().bundle_aliases)
canonicalize_bundle_id = _registry.canonicalize_bundle_id


def aliases_for_bundle(bundle_id: str) -> list[str]:
    return _registry.aliases_for_bundle(bundle_id)


def load_bundle(bundle_id: str) -> dict[str, Any]:
    return _registry.load_bundle(bundle_id)


def load_bundles() -> dict[str, dict[str, Any]]:
    return _registry.load_bundles()


def bundle_adapter_aliases(bundle_id: str) -> dict[str, str]:
    return _registry.bundle_adapter_aliases(bundle_id)


def bundle_ids_for_adapter(adapter_id: str) -> list[str]:
    return _registry.bundle_ids_for_adapter(adapter_id)
