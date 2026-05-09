"""AANA product bundle registry."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from aana.canonical_ids import BUNDLE_ALIASES, BUNDLE_IDS, canonicalize_bundle_id


ROOT = pathlib.Path(__file__).resolve().parent


def aliases_for_bundle(bundle_id: str) -> list[str]:
    canonical_id = canonicalize_bundle_id(bundle_id)
    return sorted(alias for alias, target in BUNDLE_ALIASES.items() if target == canonical_id)


def load_bundle(bundle_id: str) -> dict[str, Any]:
    canonical_id = canonicalize_bundle_id(bundle_id)
    payload = json.loads((ROOT / canonical_id / "manifest.json").read_text(encoding="utf-8"))
    payload.setdefault("canonical_id", canonical_id)
    payload.setdefault("aliases", aliases_for_bundle(canonical_id))
    return payload


def load_bundles() -> dict[str, dict[str, Any]]:
    return {bundle_id: load_bundle(bundle_id) for bundle_id in BUNDLE_IDS}
