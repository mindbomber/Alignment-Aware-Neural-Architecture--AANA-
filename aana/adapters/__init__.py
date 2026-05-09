"""Backward-compatible adapter-family registry facade."""

from __future__ import annotations

from typing import Any

from aana import registry as _registry


FAMILY_IDS = list(_registry.adapter_family_ids())


def load_adapter_family(family_id: str) -> dict[str, Any]:
    return _registry.load_adapter_family(family_id)


def load_adapter_families() -> dict[str, dict[str, Any]]:
    return _registry.load_adapter_families()
