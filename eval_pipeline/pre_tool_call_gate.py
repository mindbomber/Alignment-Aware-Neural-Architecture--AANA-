"""AANA pre-tool-call gate for agent runtimes.

The gate consumes ``schemas/agent_tool_precheck.schema.json`` events and returns
one of: accept, ask, defer, or refuse.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from jsonschema import Draft202012Validator


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "agent_tool_precheck.schema.json"
ROUTE_ORDER = {
    "accept": 0,
    "ask": 1,
    "defer": 2,
    "refuse": 3,
}
AUTH_ORDER = {
    "none": 0,
    "user_claimed": 1,
    "authenticated": 2,
    "validated": 3,
    "confirmed": 4,
}


def load_schema(schema_path: pathlib.Path | str = DEFAULT_SCHEMA) -> dict[str, Any]:
    path = pathlib.Path(schema_path)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_event(event: dict[str, Any], schema_path: pathlib.Path | str = DEFAULT_SCHEMA) -> list[dict[str, Any]]:
    schema = load_schema(schema_path)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(event), key=lambda item: list(item.path)):
        errors.append(
            {
                "path": ".".join(str(part) for part in error.path),
                "message": error.message,
            }
        )
    return errors


def stricter_route(left: str, right: str) -> str:
    return left if ROUTE_ORDER[left] >= ROUTE_ORDER[right] else right


def aix_for_route(route: str, hard_blockers: list[str]) -> dict[str, Any]:
    scores = {
        "accept": 0.95,
        "ask": 0.72,
        "defer": 0.45,
        "refuse": 0.15,
    }
    return {
        "aix_version": "0.1",
        "score": scores[route],
        "components": {
            "P": scores[route],
            "F": 1.0 if route == "accept" else 0.75,
            "C": scores[route],
        },
        "decision": route,
        "hard_blockers": hard_blockers,
    }


def has_missing_authorization_evidence(evidence_refs: list[dict[str, Any]]) -> bool:
    for ref in evidence_refs:
        source_id = str(ref.get("source_id") or "")
        kind = str(ref.get("kind") or "")
        summary = str(ref.get("summary") or "").lower()
        if source_id.startswith("counterfactual.missing_authorization"):
            return True
        if kind == "system_state" and "missing authorization" in summary:
            return True
        if kind == "system_state" and "removes verified authorization" in summary:
            return True
    return False


def route_from_event(event: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    tool_category = event["tool_category"]
    authorization_state = event["authorization_state"]
    evidence_refs = event.get("evidence_refs") or []
    reasons: list[str] = []
    hard_blockers: list[str] = []

    if tool_category == "public_read":
        route = "accept"
        reasons.append("public_read_allowed_without_identity_auth")
    elif tool_category == "private_read":
        if AUTH_ORDER[authorization_state] >= AUTH_ORDER["authenticated"]:
            route = "accept"
            reasons.append("private_read_has_authenticated_context")
        elif authorization_state == "user_claimed":
            route = "ask"
            reasons.append("private_read_needs_verified_authentication")
            hard_blockers.append("private_read_not_authenticated")
        else:
            route = "defer"
            reasons.append("private_read_missing_authorization_context")
            hard_blockers.append("private_read_not_authenticated")
    elif tool_category == "write":
        if AUTH_ORDER[authorization_state] >= AUTH_ORDER["confirmed"]:
            route = "accept"
            reasons.append("write_has_explicit_confirmation")
        elif authorization_state == "validated":
            route = "ask"
            reasons.append("write_validated_but_needs_explicit_confirmation")
            hard_blockers.append("write_missing_explicit_confirmation")
        elif authorization_state in {"authenticated", "user_claimed"}:
            route = "ask"
            reasons.append("write_needs_validation_and_confirmation")
            hard_blockers.append("write_missing_validation_or_confirmation")
        else:
            route = "defer"
            reasons.append("write_missing_authorization_context")
            hard_blockers.append("write_missing_authorization")
    else:
        route = "defer"
        reasons.append("unknown_tool_category_requires_review")
        hard_blockers.append("unknown_tool_category")

    if has_missing_authorization_evidence(evidence_refs):
        route = stricter_route(route, "defer")
        reasons.append("evidence_declares_missing_authorization")
        hard_blockers.append("evidence_missing_authorization")

    if tool_category in {"private_read", "write", "unknown"} and not evidence_refs:
        route = stricter_route(route, "defer")
        reasons.append("missing_evidence_refs_for_consequential_tool")
        hard_blockers.append("missing_evidence_refs")

    return route, reasons, hard_blockers


def gate_pre_tool_call(event: dict[str, Any], schema_path: pathlib.Path | str = DEFAULT_SCHEMA) -> dict[str, Any]:
    validation_errors = validate_event(event, schema_path)
    if validation_errors:
        route = "refuse"
        hard_blockers = ["schema_validation_failed"]
        return {
            "contract_version": "aana.agent_tool_precheck.v1",
            "tool_name": event.get("tool_name"),
            "gate_decision": "fail",
            "recommended_action": route,
            "candidate_gate": "fail",
            "aix": aix_for_route(route, hard_blockers),
            "hard_blockers": hard_blockers,
            "reasons": ["event_failed_schema_validation"],
            "validation_errors": validation_errors,
        }

    aana_route, reasons, hard_blockers = route_from_event(event)
    runtime_route = event["recommended_route"]
    final_route = stricter_route(aana_route, runtime_route)
    if final_route != aana_route:
        reasons.append(f"runtime_recommended_stricter_route:{runtime_route}")
    if runtime_route == "refuse" and "runtime_refusal" not in hard_blockers:
        hard_blockers.append("runtime_refusal")

    candidate_gate = "pass" if aana_route == "accept" and not hard_blockers else "fail"
    gate_decision = "pass" if final_route == "accept" and not hard_blockers else "fail"
    return {
        "contract_version": "aana.agent_tool_precheck.v1",
        "tool_name": event["tool_name"],
        "tool_category": event["tool_category"],
        "authorization_state": event["authorization_state"],
        "risk_domain": event["risk_domain"],
        "gate_decision": gate_decision,
        "recommended_action": final_route,
        "candidate_gate": candidate_gate,
        "aana_route": aana_route,
        "runtime_recommended_route": runtime_route,
        "aix": aix_for_route(final_route, hard_blockers),
        "hard_blockers": hard_blockers,
        "reasons": reasons,
        "evidence_ref_count": len(event.get("evidence_refs") or []),
    }
