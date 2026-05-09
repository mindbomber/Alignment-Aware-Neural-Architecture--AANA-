"""AANA product bundle registry."""

from __future__ import annotations

import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parent
BUNDLE_IDS = ["enterprise", "personal_productivity", "government_civic"]


def load_bundle(bundle_id: str) -> dict[str, Any]:
    if bundle_id not in BUNDLE_IDS:
        raise KeyError(f"Unknown AANA product bundle: {bundle_id}")
    return json.loads((ROOT / bundle_id / "manifest.json").read_text(encoding="utf-8"))


def load_bundles() -> dict[str, dict[str, Any]]:
    return {bundle_id: load_bundle(bundle_id) for bundle_id in BUNDLE_IDS}
