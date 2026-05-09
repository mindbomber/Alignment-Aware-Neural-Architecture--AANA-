"""AANA product bundle registry."""

from __future__ import annotations

import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parent
CANONICAL_BUNDLE_IDS = ["enterprise", "personal_productivity", "government_civic"]
BUNDLE_ALIASES = {
    "enterprise": "enterprise",
    "personal_productivity": "personal_productivity",
    "government_civic": "government_civic",
    "civic_government": "government_civic",
}
BUNDLE_IDS = CANONICAL_BUNDLE_IDS


def canonicalize_bundle_id(bundle_id: str) -> str:
    try:
        return BUNDLE_ALIASES[bundle_id]
    except KeyError as exc:
        raise KeyError(f"Unknown AANA product bundle: {bundle_id}") from exc


def aliases_for_bundle(bundle_id: str) -> list[str]:
    canonical_id = canonicalize_bundle_id(bundle_id)
    return sorted(alias for alias, target in BUNDLE_ALIASES.items() if target == canonical_id and alias != canonical_id)


def load_bundle(bundle_id: str) -> dict[str, Any]:
    canonical_id = canonicalize_bundle_id(bundle_id)
    payload = json.loads((ROOT / canonical_id / "manifest.json").read_text(encoding="utf-8"))
    payload.setdefault("canonical_id", canonical_id)
    payload.setdefault("aliases", aliases_for_bundle(canonical_id))
    return payload


def load_bundles() -> dict[str, dict[str, Any]]:
    return {bundle_id: load_bundle(bundle_id) for bundle_id in BUNDLE_IDS}
