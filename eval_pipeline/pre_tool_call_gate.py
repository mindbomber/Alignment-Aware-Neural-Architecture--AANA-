"""AANA pre-tool-call gate for agent runtimes.

The gate consumes ``schemas/agent_tool_precheck.schema.json`` events and returns
one of: accept, ask, defer, or refuse.
"""

from __future__ import annotations

import json
import pathlib
import re
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from eval_pipeline.adapter_generalization_config import configured_set
from eval_pipeline.authorization_state import (
    AUTHORIZATION_STATES,
    AUTHORIZATION_STATE_RANK,
    auth_state_at_least,
    canonicalize_authorization_state,
    private_read_allowed,
    write_execution_allowed,
    write_schema_accept_allowed,
)
from eval_pipeline.evidence_safety import analyze_tool_evidence_refs, normalize_evidence_ref


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "agent_tool_precheck.schema.json"
DEFAULT_TAU2_MODEL = ROOT / "eval_outputs" / "benchmark_scout" / "aana_tau2_action_taxonomy_v2.joblib"
ROUTE_ORDER = {
    "accept": 0,
    "ask": 1,
    "defer": 2,
    "refuse": 3,
}

READ_POLICY_TOOLS = configured_set("read_policy_tools")
PRIVATE_READ_HINTS = configured_set("private_read_hints")
IDENTITY_BOUND_ARGUMENT_KEYS = configured_set("identity_bound_argument_keys")
WRITE_HINTS = configured_set("write_hints")
REQUIRED_WRITE_HINTS = configured_set("required_write_hints")
RISKY_WRITE_HINTS = configured_set("risky_write_hints")
AUTH_ORDER = AUTHORIZATION_STATE_RANK
AUTH_STATES_BY_ORDER = list(AUTHORIZATION_STATES)


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


def normalize_evidence_refs_for_validation(event: dict[str, Any]) -> dict[str, Any]:
    """Fill backward-compatible evidence-ref defaults before schema validation."""

    payload = dict(event or {})
    refs = []
    for ref in payload.get("evidence_refs") or []:
        if isinstance(ref, str):
            refs.append(
                normalize_evidence_ref(
                    {
                        "source_id": ref,
                        "kind": "other",
                        "trust_tier": "runtime",
                        "redaction_status": "redacted",
                        "summary": "Quickstart evidence reference supplied by the agent runtime.",
                    },
                    default_provenance="runtime_quickstart",
                    default_freshness_status="fresh",
                )
            )
        elif isinstance(ref, dict):
            trust = str(ref.get("trust_tier") or "unknown")
            refs.append(
                normalize_evidence_ref(
                    ref,
                    default_provenance=str(ref.get("provenance") or "runtime"),
                    default_freshness_status="fresh" if trust in {"verified", "runtime"} else "unknown",
                )
            )
        else:
            refs.append(ref)
    payload["evidence_refs"] = refs
    return payload


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


def _words(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _summary_text(event: dict[str, Any]) -> str:
    parts = [
        str(event.get("tool_name") or ""),
        str(event.get("risk_domain") or ""),
        str(event.get("user_intent") or ""),
        json.dumps(event.get("proposed_arguments") or {}, sort_keys=True),
    ]
    for ref in event.get("evidence_refs") or []:
        if isinstance(ref, dict):
            parts.append(str(ref.get("source_id") or ""))
            parts.append(str(ref.get("kind") or ""))
            parts.append(str(ref.get("summary") or ""))
    return "\n".join(parts).lower()


def infer_tool_intent(event: dict[str, Any]) -> str:
    """Infer a richer v2 tool intent while preserving the v1 contract shape."""

    tool_name = str(event.get("tool_name") or "").lower()
    name_words = _words(tool_name)
    category = str(event.get("tool_category") or "unknown")

    if "transfer_to_human" in tool_name or "human_agent" in tool_name or "human_agents" in tool_name:
        return "required_write"
    if tool_name in READ_POLICY_TOOLS or any(token in tool_name for token in ("kb_", "policy", "calculate")):
        return "utility_read"
    if category == "public_read":
        return "public_read"
    if category == "private_read":
        return "private_read"
    if category == "write":
        if name_words & RISKY_WRITE_HINTS:
            return "risky_write"
        return "required_write"
    if name_words & WRITE_HINTS:
        if name_words & RISKY_WRITE_HINTS:
            return "risky_write"
        if name_words & REQUIRED_WRITE_HINTS:
            return "required_write"
        return "required_write"
    if any(hint in tool_name for hint in PRIVATE_READ_HINTS):
        return "private_read"
    if any(token in tool_name for token in ("check", "get", "find", "list", "lookup", "retrieve", "search")):
        return "public_read"
    return "unknown"


def is_identity_bound_read(event: dict[str, Any]) -> bool:
    """Return True when a read declared public appears identity/account bound."""

    if str(event.get("tool_category") or "") != "public_read":
        return False
    tool_name = str(event.get("tool_name") or "").lower()
    args = event.get("proposed_arguments") if isinstance(event.get("proposed_arguments"), dict) else {}
    if any(key in args for key in IDENTITY_BOUND_ARGUMENT_KEYS):
        return True
    if any(hint in tool_name for hint in PRIVATE_READ_HINTS):
        return True
    return False


def is_high_risk_write(event: dict[str, Any]) -> bool:
    """Return True for writes that should require explicit confirmation."""

    if str(event.get("tool_category") or "") != "write":
        return False
    tool_name = str(event.get("tool_name") or "").lower()
    name_words = _words(tool_name)
    risk_domain = str(event.get("risk_domain") or "unknown")
    if name_words & RISKY_WRITE_HINTS:
        return True
    if any(term in tool_name for term in ("delete", "transfer", "pay", "purchase", "reset", "send", "deploy", "grant", "revoke")):
        return True
    return risk_domain in {"finance", "devops", "security", "legal", "pharma", "healthcare"}


def authorization_state_from_evidence(event: dict[str, Any]) -> dict[str, Any]:
    """Infer the strongest supported auth state from redacted evidence refs."""

    declared = canonicalize_authorization_state(event.get("authorization_state"))
    strongest = "none"
    support: list[str] = []
    refs = event.get("evidence_refs") or []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        source_id = str(ref.get("source_id") or "").lower()
        kind = str(ref.get("kind") or "")
        summary = str(ref.get("summary") or "").lower()
        trust = str(ref.get("trust_tier") or "unknown")
        text = f"{source_id} {summary}"
        if kind == "user_message" or trust == "user_claimed" or "user claimed" in text:
            if auth_state_at_least("user_claimed", strongest) and strongest != "user_claimed":
                strongest = "user_claimed"
            support.append("user_claimed")
        if kind == "auth_event" or "authenticated" in text or "identity was authenticated" in text:
            if auth_state_at_least("authenticated", strongest) and strongest != "authenticated":
                strongest = "authenticated"
            support.append("authenticated")
        if kind == "tool_result" and any(marker in text for marker in ("validated", "ownership", "eligible", "policy validation", "verified target")):
            if auth_state_at_least("validated", strongest) and strongest != "validated":
                strongest = "validated"
            support.append("validated")
        if kind == "policy" and any(marker in text for marker in ("validated", "allowed", "eligible")):
            if auth_state_at_least("validated", strongest) and strongest != "validated":
                strongest = "validated"
            support.append("validated")
        if kind == "approval" or "confirmed" in text or "explicitly confirm" in text or "user-confirmed" in text:
            if auth_state_at_least("confirmed", strongest) and strongest != "confirmed":
                strongest = "confirmed"
            support.append("confirmed")

    effective = declared
    downgraded = False
    if declared in {"authenticated", "validated", "confirmed"} and refs and not auth_state_at_least(strongest, declared):
        effective = strongest if strongest != "none" else "user_claimed"
        downgraded = True
    if declared == "none" and strongest != "none":
        effective = strongest
    return {
        "declared_state": declared,
        "evidence_supported_state": strongest,
        "effective_state": effective,
        "support": sorted(set(support), key=lambda item: AUTH_ORDER[item]),
        "downgraded": downgraded,
    }


def normalize_authorization_for_validation(event: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Lift auth state from evidence before schema condition validation."""

    normalized = dict(event)
    reasons: list[str] = []
    route = normalized.get("recommended_route")
    category = normalized.get("tool_category")
    auth_report = authorization_state_from_evidence(normalized)
    if route == "accept" and category == "private_read" and not private_read_allowed(normalized.get("authorization_state")):
        if private_read_allowed(auth_report["evidence_supported_state"]):
            normalized["authorization_state"] = auth_report["evidence_supported_state"]
            reasons.append("authorization_state_lifted_from_auth_evidence_for_schema")
    if route == "accept" and category == "write" and not write_schema_accept_allowed(normalized.get("authorization_state")):
        if write_schema_accept_allowed(auth_report["evidence_supported_state"]):
            normalized["authorization_state"] = auth_report["evidence_supported_state"]
            reasons.append("authorization_state_lifted_from_write_evidence_for_schema")
    return normalized, reasons


def category_for_intent(intent: str, fallback: str) -> str:
    if intent in {"utility_read", "public_read"}:
        return "public_read"
    if intent == "private_read":
        return "private_read"
    if intent in {"required_write", "risky_write"}:
        return "write"
    if fallback in TOOL_CATEGORIES_FOR_V2:
        return fallback
    return "unknown"


TOOL_CATEGORIES_FOR_V2 = {"public_read", "private_read", "write", "unknown"}


def refine_authorization_state(event: dict[str, Any], tool_intent: str) -> str:
    """Refine auth state from redacted dialogue/evidence summaries."""

    current = canonicalize_authorization_state(event.get("authorization_state"))
    text = _summary_text(event)
    refs = event.get("evidence_refs") or []
    has_policy = any(isinstance(ref, dict) and ref.get("kind") == "policy" for ref in refs)
    has_auth = any(isinstance(ref, dict) and ref.get("kind") in {"auth_event", "approval"} for ref in refs)
    confirmation_markers = (
        "confirm",
        "confirmed",
        "go ahead",
        "please",
        "yes",
        "do it",
        "i want",
        "i would like",
        "book",
        "cancel",
        "change",
        "refund",
        "return",
        "submit",
        "update",
    )
    if tool_intent in {"utility_read", "public_read"}:
        return "confirmed"
    if current == "confirmed":
        return current
    if tool_intent in {"required_write", "risky_write"} and has_policy and any(marker in text for marker in confirmation_markers):
        return "confirmed"
    if current == "validated" and any(marker in text for marker in confirmation_markers):
        return "confirmed"
    if current == "none" and has_auth:
        return "authenticated"
    return current


def normalize_event_for_v2(event: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return a v1-schema-compatible event enriched by v2 inference."""

    normalized = dict(event)
    reasons: list[str] = []
    intent = infer_tool_intent(normalized)
    normalized["tool_category"] = category_for_intent(intent, str(normalized.get("tool_category") or "unknown"))
    normalized["authorization_state"] = refine_authorization_state(normalized, intent)
    if normalized.get("recommended_route") == "accept":
        if normalized["tool_category"] == "unknown":
            normalized["recommended_route"] = "defer"
            reasons.append("v2_unknown_tool_runtime_accept_normalized_to_defer")
        elif normalized["tool_category"] == "write" and not write_schema_accept_allowed(normalized["authorization_state"]):
            normalized["recommended_route"] = "ask"
            reasons.append("v2_write_accept_without_validation_normalized_to_ask")
        elif normalized["tool_category"] == "private_read" and not private_read_allowed(normalized["authorization_state"]):
            normalized["recommended_route"] = "ask"
            reasons.append("v2_private_read_accept_without_auth_normalized_to_ask")
    return normalized, reasons


def taxonomy_text(event: dict[str, Any], v1_result: dict[str, Any] | None = None, tool_intent: str | None = None) -> str:
    """Build the stable text feature payload used by the optional v2 classifier."""

    refs = event.get("evidence_refs") or []
    evidence = " ".join(
        f"{ref.get('source_id', '')} {ref.get('kind', '')} {ref.get('summary', '')}"
        for ref in refs
        if isinstance(ref, dict)
    )
    blockers = " ".join(str(item) for item in (v1_result or {}).get("hard_blockers", []))
    return "\n".join(
        [
            f"risk_domain={event.get('risk_domain', '')}",
            f"tool_name={event.get('tool_name', '')}",
            f"tool_category={event.get('tool_category', '')}",
            f"tool_intent={tool_intent or infer_tool_intent(event)}",
            f"authorization_state={event.get('authorization_state', '')}",
            f"user_intent={event.get('user_intent', '')}",
            f"proposed_arguments={json.dumps(event.get('proposed_arguments') or {}, sort_keys=True)}",
            f"evidence={evidence}",
            f"v1_route={(v1_result or {}).get('recommended_action', '')}",
            f"v1_blockers={blockers}",
        ]
    )


@lru_cache(maxsize=8)
def _load_tau2_taxonomy_model_cached(model_path: str) -> dict[str, Any] | None:
    path = pathlib.Path(model_path)
    if not path.exists():
        return None
    try:
        import joblib
    except ImportError:
        return None
    return joblib.load(path)


def load_tau2_taxonomy_model(model_path: pathlib.Path | str = DEFAULT_TAU2_MODEL) -> dict[str, Any] | None:
    return _load_tau2_taxonomy_model_cached(str(pathlib.Path(model_path)))


def score_with_tau2_model(event: dict[str, Any], v1_result: dict[str, Any], model_path: pathlib.Path | str = DEFAULT_TAU2_MODEL) -> dict[str, Any] | None:
    loaded = load_tau2_taxonomy_model(model_path)
    if not loaded:
        return None
    classifier = loaded.get("classifier")
    threshold = float(loaded.get("threshold", 0.5))
    if classifier is None:
        return None
    probability = float(classifier.predict_proba([taxonomy_text(event, v1_result)])[:, 1][0])
    should_execute = probability >= threshold
    return {
        "model_family": loaded.get("model_family", "tfidf_logistic_regression_calibrated"),
        "execute_probability": round(probability, 6),
        "threshold": round(threshold, 6),
        "should_execute": should_execute,
    }


def route_from_v2(
    event: dict[str, Any],
    v1_result: dict[str, Any],
    tool_intent: str,
    model_score: dict[str, Any] | None,
) -> tuple[str, list[str], list[str]]:
    reasons = list(v1_result.get("reasons", []))
    hard_blockers = list(v1_result.get("hard_blockers", []))
    category = event["tool_category"]
    auth = event["authorization_state"]
    evidence_refs = event.get("evidence_refs") or []

    if has_missing_authorization_evidence(evidence_refs):
        blockers = sorted(set(hard_blockers + ["evidence_missing_authorization"]))
        return "defer", reasons + ["evidence_declares_missing_authorization"], blockers

    if model_score is not None:
        reasons.append("tau2_action_taxonomy_model_scored")
        non_recoverable = {
            "evidence_missing_authorization",
            "private_read_not_authenticated",
            "runtime_refusal",
            "schema_validation_failed",
        }
        if (
            model_score["should_execute"]
            and category != "unknown"
            and tool_intent != "risky_write"
            and not (set(hard_blockers) & non_recoverable)
        ):
            if hard_blockers:
                reasons.append("tau2_action_taxonomy_model_overrode_recoverable_v1_blockers")
            return "accept", reasons, []
        if not model_score["should_execute"]:
            reasons.append("tau2_action_taxonomy_model_below_threshold")
            if tool_intent in {"utility_read", "public_read", "required_write", "unknown"}:
                return "defer", reasons, ["tau2_action_taxonomy_model_below_threshold"]

    if tool_intent in {"utility_read", "public_read"}:
        return "accept", reasons + ["v2_public_or_utility_read_allowed"], []
    if tool_intent == "private_read":
        if private_read_allowed(auth):
            return "accept", reasons + ["v2_private_read_has_authenticated_context"], []
        return "ask", reasons + ["v2_private_read_needs_authentication"], ["private_read_not_authenticated"]
    if tool_intent == "required_write":
        if write_execution_allowed(auth):
            return "accept", reasons + ["v2_required_write_has_policy_and_confirmation"], []
        if auth_state_at_least(auth, "authenticated"):
            return "ask", reasons + ["v2_required_write_needs_confirmation"], ["write_missing_explicit_confirmation"]
        return "defer", reasons + ["v2_required_write_missing_authorization"], ["write_missing_authorization"]
    if tool_intent == "risky_write":
        if write_execution_allowed(auth) and evidence_refs:
            return "ask", reasons + ["v2_risky_write_requires_final_confirmation"], ["risky_write_requires_final_confirmation"]
        return "defer", reasons + ["v2_risky_write_missing_strong_authorization"], ["risky_write_missing_strong_authorization"]

    return "defer", reasons + ["v2_unknown_tool_intent_requires_review"], ["unknown_tool_intent"]


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
    auth_report = authorization_state_from_evidence(event)
    authorization_state = auth_report["effective_state"]
    evidence_refs = event.get("evidence_refs") or []
    reasons: list[str] = []
    hard_blockers: list[str] = []

    if auth_report["downgraded"]:
        reasons.append("authorization_state_downgraded_to_evidence_supported_state")
        hard_blockers.append("authorization_state_not_supported_by_evidence")

    if is_identity_bound_read(event):
        tool_category = "private_read"
        reasons.append("public_read_reclassified_identity_bound_private_read")
        hard_blockers.append("public_read_identity_bound_misclassified")

    if tool_category == "public_read":
        route = "accept"
        reasons.append("public_read_allowed_without_identity_auth")
    elif tool_category == "private_read":
        if private_read_allowed(authorization_state):
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
        high_risk_write = is_high_risk_write(event)
        if high_risk_write and not write_execution_allowed(authorization_state):
            route = "ask" if auth_state_at_least(authorization_state, "user_claimed") else "defer"
            reasons.append("high_risk_write_requires_explicit_confirmation")
            hard_blockers.append("high_risk_write_missing_explicit_confirmation")
            hard_blockers.append("write_missing_explicit_confirmation")
            if authorization_state in {"user_claimed", "authenticated"}:
                hard_blockers.append("write_missing_validation_or_confirmation")
        elif write_execution_allowed(authorization_state):
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

    evidence_report = analyze_tool_evidence_refs(evidence_refs, tool_category=tool_category)
    for code in evidence_report["error_codes"]:
        if code in {"evidence_secret_leak", "evidence_pii_leak", "unsafe_redaction_status"}:
            route = stricter_route(route, "refuse")
        elif code in {"stale_evidence", "invalid_retrieved_at", "missing_source_id", "malformed_evidence_ref"}:
            route = stricter_route(route, "defer")
        if code not in hard_blockers:
            hard_blockers.append(code)
    if evidence_report["contradictory_evidence_source_ids"]:
        route = stricter_route(route, "defer")
        reasons.append("evidence_contradicts_action_or_claim")
        if "contradictory_evidence" not in hard_blockers:
            hard_blockers.append("contradictory_evidence")
    if evidence_report["missing_evidence_source_ids"]:
        route = stricter_route(route, "defer")
        reasons.append("evidence_marks_missing_information")
        if "evidence_marks_missing_information" not in hard_blockers:
            hard_blockers.append("evidence_marks_missing_information")
    if evidence_report["warning_codes"]:
        reasons.extend(f"evidence_warning:{code}" for code in evidence_report["warning_codes"])

    return route, reasons, hard_blockers


def gate_pre_tool_call(event: dict[str, Any], schema_path: pathlib.Path | str = DEFAULT_SCHEMA) -> dict[str, Any]:
    event, prevalidation_reasons = normalize_authorization_for_validation(event)
    event = normalize_evidence_refs_for_validation(event)
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
    reasons = [*prevalidation_reasons, *reasons]
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
        "evidence_integrity": analyze_tool_evidence_refs(event.get("evidence_refs") or [], tool_category=event["tool_category"]),
        "authorization_report": authorization_state_from_evidence(event),
    }


def gate_pre_tool_call_v2(
    event: dict[str, Any],
    schema_path: pathlib.Path | str = DEFAULT_SCHEMA,
    model_path: pathlib.Path | str = DEFAULT_TAU2_MODEL,
) -> dict[str, Any]:
    """Run the τ²-calibrated v2 pre-tool-call gate.

    V2 preserves the v1 event contract but normalizes common τ² tool intents
    before schema validation. This prevents the v1 failure mode where useful
    utility/read-policy tools such as ``calculate`` were marked ``unknown`` and
    rejected only because the runtime route was ``accept``.
    """

    event = normalize_evidence_refs_for_validation(event)
    raw_validation_errors = validate_event(event, schema_path)
    normalized, normalization_reasons = normalize_event_for_v2(event)
    normalized = normalize_evidence_refs_for_validation(normalized)
    validation_errors = validate_event(normalized, schema_path)
    tool_intent = infer_tool_intent(normalized)

    if validation_errors:
        route = "refuse"
        hard_blockers = ["schema_validation_failed"]
        return {
            "contract_version": "aana.agent_tool_precheck.v1",
            "gate_version": "aana.agent_tool_precheck.v2",
            "tool_name": event.get("tool_name"),
            "tool_intent": tool_intent,
            "gate_decision": "fail",
            "recommended_action": route,
            "candidate_gate": "fail",
            "aix": aix_for_route(route, hard_blockers),
            "hard_blockers": hard_blockers,
            "reasons": ["event_failed_schema_validation", *normalization_reasons],
            "validation_errors": validation_errors,
            "raw_validation_errors": raw_validation_errors,
        }

    v1_result = gate_pre_tool_call(normalized, schema_path)
    model_score = score_with_tau2_model(normalized, v1_result, model_path)
    route, reasons, hard_blockers = route_from_v2(normalized, v1_result, tool_intent, model_score)
    final_route = stricter_route(route, normalized["recommended_route"])
    if final_route != route:
        reasons.append(f"runtime_recommended_stricter_route:{normalized['recommended_route']}")
    reasons.extend(normalization_reasons)

    candidate_gate = "pass" if route == "accept" and not hard_blockers else "fail"
    gate_decision = "pass" if final_route == "accept" and not hard_blockers else "fail"
    return {
        "contract_version": "aana.agent_tool_precheck.v1",
        "gate_version": "aana.agent_tool_precheck.v2",
        "tool_name": normalized["tool_name"],
        "tool_category": normalized["tool_category"],
        "tool_intent": tool_intent,
        "authorization_state": normalized["authorization_state"],
        "risk_domain": normalized["risk_domain"],
        "gate_decision": gate_decision,
        "recommended_action": final_route,
        "candidate_gate": candidate_gate,
        "aana_route": route,
        "runtime_recommended_route": normalized["recommended_route"],
        "aix": aix_for_route(final_route, hard_blockers),
        "hard_blockers": hard_blockers,
        "reasons": reasons,
        "evidence_ref_count": len(normalized.get("evidence_refs") or []),
        "evidence_integrity": analyze_tool_evidence_refs(normalized.get("evidence_refs") or [], tool_category=normalized["tool_category"]),
        "authorization_report": authorization_state_from_evidence(normalized),
        "tau2_action_taxonomy": model_score,
        "v1_gate_result": {
            "gate_decision": v1_result.get("gate_decision"),
            "recommended_action": v1_result.get("recommended_action"),
            "hard_blockers": v1_result.get("hard_blockers", []),
            "validation_errors": v1_result.get("validation_errors", []),
        },
        "raw_validation_errors": raw_validation_errors,
    }
