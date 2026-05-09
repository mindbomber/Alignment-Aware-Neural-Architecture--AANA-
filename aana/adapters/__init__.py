"""AANA technical adapter-family registry."""

from __future__ import annotations

import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parent
FAMILY_IDS = [
    "privacy_pii",
    "grounded_qa",
    "agent_tool_use",
    "governance_compliance",
    "security_devops",
    "domain_risk",
]


def load_adapter_family(family_id: str) -> dict[str, Any]:
    if family_id not in FAMILY_IDS:
        raise KeyError(f"Unknown AANA adapter family: {family_id}")
    return json.loads((ROOT / family_id / "manifest.json").read_text(encoding="utf-8"))


def load_adapter_families() -> dict[str, dict[str, Any]]:
    return {family_id: load_adapter_family(family_id) for family_id in FAMILY_IDS}
