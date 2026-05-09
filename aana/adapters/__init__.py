"""AANA technical adapter-family registry."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from aana.canonical_ids import ADAPTER_FAMILY_IDS, canonicalize_adapter_family_id


ROOT = pathlib.Path(__file__).resolve().parent
FAMILY_IDS = list(ADAPTER_FAMILY_IDS)


def load_adapter_family(family_id: str) -> dict[str, Any]:
    canonical_id = canonicalize_adapter_family_id(family_id)
    return json.loads((ROOT / canonical_id / "manifest.json").read_text(encoding="utf-8"))


def load_adapter_families() -> dict[str, dict[str, Any]]:
    return {family_id: load_adapter_family(family_id) for family_id in FAMILY_IDS}
