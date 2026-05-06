"""Per-message AIx scoring for mechanistic interoperability handoffs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from eval_pipeline import aix


HANDOFF_AIX_VERSION = "0.1"
AIX_LAYERS = ("P", "B", "C", "F")


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _endpoint_id(handoff: dict[str, Any], field: str) -> str | None:
    endpoint = handoff.get(field)
    if not isinstance(endpoint, dict):
        return None
    value = endpoint.get("id")
    return value if isinstance(value, str) else None


def _verifier_components(verifier_scores: dict[str, Any]) -> dict[str, float | None]:
    components: dict[str, float | None] = {}
    for layer in AIX_LAYERS:
        score_block = verifier_scores.get(layer) if isinstance(verifier_scores, dict) else None
        score = score_block.get("score") if isinstance(score_block, dict) else None
        components[layer] = round(float(score), 4) if isinstance(score, (int, float)) else None
    return components


def _verifier_statuses(verifier_scores: dict[str, Any]) -> dict[str, str | None]:
    statuses: dict[str, str | None] = {}
    for layer in AIX_LAYERS:
        score_block = verifier_scores.get(layer) if isinstance(verifier_scores, dict) else None
        status = score_block.get("status") if isinstance(score_block, dict) else None
        statuses[layer] = status if isinstance(status, str) else None
    return statuses


def _canonical_components(canonical_aix: dict[str, Any], verifier_components: dict[str, float | None]) -> dict[str, float | None]:
    components = dict(verifier_components)
    for layer, score in canonical_aix.get("components", {}).items():
        if layer in components and isinstance(score, (int, float)):
            components[layer] = round(float(score), 4)
    return components


def calculate_handoff_aix(
    handoff: dict[str, Any],
    *,
    constraint_results: list[dict[str, Any]] | None = None,
    violations: list[dict[str, Any]] | None = None,
    gate_decision: str | None = None,
    recommended_action: str | None = None,
) -> dict[str, Any]:
    """Calculate AIx for one exchanged handoff message.

    The returned block is intentionally handoff-scoped. It keeps sender,
    recipient, message fingerprint, P/B/C/F verifier scores, canonical AIx
    routing fields, and hard blockers together.
    """

    handoff = handoff if isinstance(handoff, dict) else {}
    metadata = handoff.get("metadata") if isinstance(handoff.get("metadata"), dict) else {}
    adapter = {"aix": metadata.get("aix", {}) if isinstance(metadata.get("aix", {}), dict) else {}}
    verifier_scores = handoff.get("verifier_scores") if isinstance(handoff.get("verifier_scores"), dict) else {}
    canonical = aix.calculate_aix(
        adapter=adapter,
        constraint_results=constraint_results or [],
        tool_report={"violations": violations or []},
        gate_decision=gate_decision,
        recommended_action=recommended_action,
    )
    verifier_components = _verifier_components(verifier_scores)

    return {
        "handoff_aix_version": HANDOFF_AIX_VERSION,
        "aix_version": canonical.get("aix_version"),
        "handoff_id": handoff.get("handoff_id"),
        "sender_id": _endpoint_id(handoff, "sender"),
        "recipient_id": _endpoint_id(handoff, "recipient"),
        "message_fingerprint": _fingerprint(handoff.get("message", {})),
        "score": canonical.get("score"),
        "components": _canonical_components(canonical, verifier_components),
        "verifier_components": verifier_components,
        "verifier_statuses": _verifier_statuses(verifier_scores),
        "base_score": canonical.get("base_score"),
        "penalty": canonical.get("penalty"),
        "beta": canonical.get("beta"),
        "thresholds": canonical.get("thresholds", {}),
        "decision": canonical.get("decision"),
        "hard_blockers": canonical.get("hard_blockers", []),
        "notes": canonical.get("notes", []),
    }


__all__ = ["HANDOFF_AIX_VERSION", "calculate_handoff_aix"]
