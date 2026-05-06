"""Production readiness gate for high-risk MI actions."""

from __future__ import annotations

import json
import pathlib
from typing import Any


PRODUCTION_MI_READINESS_VERSION = "0.1"
DEFAULT_CHECKLIST_PATH = pathlib.Path(__file__).resolve().parents[1] / "docs" / "production-mi-release-checklist.md"


def _batch(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("mi_batch"), dict):
        return payload["mi_batch"]
    return payload


def _results(batch: dict[str, Any]) -> list[dict[str, Any]]:
    items = batch.get("results")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _global_aix(batch: dict[str, Any]) -> dict[str, Any]:
    block = batch.get("global_aix") or batch.get("workflow_aix")
    return block if isinstance(block, dict) else {}


def _propagated_risk(batch: dict[str, Any]) -> dict[str, Any]:
    block = batch.get("propagated_risk")
    return block if isinstance(block, dict) else {}


def _hard_blockers(batch: dict[str, Any], results: list[dict[str, Any]]) -> list[str]:
    blockers = set()
    for block in (_global_aix(batch),):
        for blocker in block.get("hard_blockers", []) if isinstance(block.get("hard_blockers"), list) else []:
            blockers.add(str(blocker))
    for result in results:
        for key in ("aix", "handoff_aix"):
            block = result.get(key)
            if not isinstance(block, dict):
                continue
            for blocker in block.get("hard_blockers", []) if isinstance(block.get("hard_blockers"), list) else []:
                blockers.add(str(blocker))
    return sorted(blockers)


def _missing_evidence(results: list[dict[str, Any]]) -> list[str]:
    missing = []
    for index, result in enumerate(results):
        handoff_id = str(result.get("handoff_id") or result.get("handoff_aix", {}).get("handoff_id") or f"handoff-{index}")
        evidence = result.get("evidence_summary")
        if evidence is None:
            evidence = result.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            missing.append(handoff_id)
            continue
        violations = result.get("violations") if isinstance(result.get("violations"), list) else []
        if any(str(violation.get("code") or "").startswith("missing_evidence") for violation in violations if isinstance(violation, dict)):
            missing.append(handoff_id)
    return sorted(set(missing))


def _below_global_threshold(global_aix: dict[str, Any]) -> dict[str, Any]:
    score = global_aix.get("score")
    thresholds = global_aix.get("thresholds") if isinstance(global_aix.get("thresholds"), dict) else {}
    accept_threshold = thresholds.get("accept", 0.85)
    if not isinstance(score, (int, float)):
        return {"below": True, "score": score, "accept_threshold": accept_threshold}
    return {
        "below": float(score) < float(accept_threshold),
        "score": round(float(score), 4),
        "accept_threshold": float(accept_threshold),
    }


def _unresolved_propagation(propagated_risk: dict[str, Any]) -> bool:
    return bool(
        propagated_risk.get("has_propagated_risk")
        or propagated_risk.get("risk_count", 0)
        or propagated_risk.get("propagation_count", 0)
    )


def _check_item(item_id: str, label: str, passed: bool, details: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "status": "pass" if passed else "block",
        "details": details,
    }


def production_mi_readiness_gate(mi_result: dict[str, Any], *, high_risk_action: bool = True) -> dict[str, Any]:
    """Return the production execution decision for a high-risk MI workflow.

    Direct execution is blocked when MI checks are missing, evidence is missing,
    hard blockers exist, global AIx is below the active accept threshold, or
    propagated assumptions/claims remain unresolved.
    """

    batch = _batch(mi_result) if isinstance(mi_result, dict) else {}
    results = _results(batch)
    global_aix = _global_aix(batch)
    propagated_risk = _propagated_risk(batch)
    missing_evidence = _missing_evidence(results)
    hard_blockers = _hard_blockers(batch, results)
    threshold = _below_global_threshold(global_aix)
    unresolved_propagation = _unresolved_propagation(propagated_risk)
    mi_checks_present = bool(results and global_aix)

    checklist = [
        _check_item(
            "mi-checks-present",
            "MI boundary checks were run before execution.",
            mi_checks_present,
            f"{len(results)} handoff result(s) available.",
        ),
        _check_item(
            "evidence-present",
            "Every consequential handoff carries evidence metadata.",
            not missing_evidence,
            "Missing evidence for: " + ", ".join(missing_evidence) if missing_evidence else "All handoffs include evidence.",
        ),
        _check_item(
            "no-hard-blockers",
            "No hard blockers exist in local or global AIx.",
            not hard_blockers,
            "Hard blockers: " + ", ".join(hard_blockers) if hard_blockers else "No hard blockers found.",
        ),
        _check_item(
            "global-aix-threshold",
            "Global AIx meets the active accept threshold.",
            not threshold["below"],
            f"score={threshold['score']} accept_threshold={threshold['accept_threshold']}",
        ),
        _check_item(
            "propagation-resolved",
            "Propagated assumptions and unsupported premises are resolved.",
            not unresolved_propagation,
            (
                f"risk_count={propagated_risk.get('risk_count', 0)} "
                f"propagation_count={propagated_risk.get('propagation_count', 0)}"
            ),
        ),
    ]

    blockers = [item["id"] for item in checklist if item["status"] == "block"]
    if not high_risk_action:
        blockers = [blocker for blocker in blockers if blocker != "mi-checks-present"]
    can_execute = high_risk_action and not blockers

    recommended_action = "accept" if can_execute else "defer"
    if "evidence-present" in blockers:
        recommended_action = "retrieve"
    if "propagation-resolved" in blockers:
        recommended_action = "revise"
    if "no-hard-blockers" in blockers:
        recommended_action = "refuse"

    return {
        "production_mi_readiness_version": PRODUCTION_MI_READINESS_VERSION,
        "gate": "production_mi_readiness",
        "high_risk_action": high_risk_action,
        "can_execute_directly": can_execute,
        "release_status": "ready" if can_execute else "blocked",
        "recommended_action": recommended_action,
        "blockers": blockers,
        "checklist": checklist,
        "global_aix": {
            "score": threshold["score"],
            "accept_threshold": threshold["accept_threshold"],
            "decision": global_aix.get("decision"),
            "recommended_action": global_aix.get("recommended_action"),
            "risk_tier": global_aix.get("risk_tier"),
        },
        "hard_blockers": hard_blockers,
        "missing_evidence_handoff_ids": missing_evidence,
        "propagated_risk": {
            "risk_count": propagated_risk.get("risk_count", 0),
            "propagation_count": propagated_risk.get("propagation_count", 0),
            "has_propagated_risk": bool(propagated_risk.get("has_propagated_risk")),
        },
    }


def production_mi_release_checklist_markdown() -> str:
    """Return the production MI release checklist as Markdown."""

    return """# Production MI Release Checklist

Status: milestone 15 production readiness gate.

Purpose: high-risk AANA actions must pass MI checks before direct execution. This checklist applies before sending, publishing, deploying, booking, purchasing, exporting, deleting, changing permissions, releasing code, or handing a consequential result to an external connector.

## Required Gate

Run `production_mi_readiness_gate(...)` on the result from `mi_boundary_batch(...)` or a pilot result that contains `mi_batch`.

Direct execution is allowed only when all release checks pass:

- MI boundary checks are present for the high-risk workflow.
- Every consequential handoff carries evidence metadata.
- No local or global AIx hard blockers exist.
- Global AIx is greater than or equal to the active accept threshold.
- Propagated assumptions, unsupported claims, stale evidence, and downstream premise links are resolved.

## Blocking Conditions

| Condition | Required route |
| --- | --- |
| MI checks missing | `defer` until the workflow is checked |
| evidence missing | `retrieve` evidence, then re-run MI |
| hard blockers exist | `refuse` or route to an approved human-review process |
| global AIx below threshold | `revise` or `defer`, then re-run MI |
| propagated assumptions unresolved | `revise` upstream output or `ask` for clarification, then re-run MI |

## Release Signoff

- Attach the redacted MI audit JSONL for the run.
- Attach the workflow or pilot result with raw private content excluded from release notes.
- Confirm the dashboard shows no unresolved propagated-risk signal for this workflow.
- Confirm the selected risk tier matches connectivity, irreversibility, privacy, security, and downstream blast radius.
- Confirm any human-review queue or incident channel exists before enabling direct execution.
"""


def write_production_mi_release_checklist(path: str | pathlib.Path = DEFAULT_CHECKLIST_PATH) -> dict[str, Any]:
    """Write the production MI release checklist artifact."""

    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(production_mi_release_checklist_markdown(), encoding="utf-8")
    return {"path": str(output_path), "bytes": output_path.stat().st_size}


def write_production_mi_readiness_result(
    mi_result: dict[str, Any],
    path: str | pathlib.Path,
    *,
    high_risk_action: bool = True,
) -> dict[str, Any]:
    """Write a JSON production readiness decision for a checked MI workflow."""

    result = production_mi_readiness_gate(mi_result, high_risk_action=high_risk_action)
    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"result": result, "path": str(output_path), "bytes": output_path.stat().st_size}


__all__ = [
    "PRODUCTION_MI_READINESS_VERSION",
    "production_mi_readiness_gate",
    "production_mi_release_checklist_markdown",
    "write_production_mi_readiness_result",
    "write_production_mi_release_checklist",
]
