"""Mechanistic interoperability handoff gate.

This module implements the first deterministic AANA gate for recipient-relative
handoff checks. It treats a handoff as acceptable only when the message remains
inside the recipient feasible region:

    F_recipient = K_P,recipient intersection K_B,recipient intersection K_C,recipient

The gate is intentionally conservative. It does not infer real-world truth from
free text; it verifies that the handoff carries recipient constraints, evidence,
verifier scores for P/B/C, and no hard failures before returning accept.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from eval_pipeline import aix
from eval_pipeline.agent_contract import ALLOWED_ACTIONS
from eval_pipeline.evidence import validate_evidence_object, validate_handoff_evidence_binding
from eval_pipeline.handoff_aix import calculate_handoff_aix


HANDOFF_CONTRACT_VERSION = "0.1"
REQUIRED_TOP_LEVEL_FIELDS = [
    "contract_version",
    "handoff_id",
    "sender",
    "recipient",
    "message_schema",
    "message",
    "evidence",
    "constraint_map",
    "verifier_scores",
]
REQUIRED_CONSTRAINT_LAYERS = ["K_P", "K_B", "K_C"]
LAYER_TO_AIX = {"K_P": "P", "K_B": "B", "K_C": "C", "F": "F"}
PASS_STATUSES = {"pass"}
SOFT_PASS_STATUSES = {"pass", "warn", "not_applicable"}


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _allowed_actions(handoff: dict[str, Any]) -> list[str]:
    actions = handoff.get("allowed_actions")
    if not isinstance(actions, list) or not actions:
        return list(ALLOWED_ACTIONS)
    normalized = [action for action in actions if action in ALLOWED_ACTIONS]
    return normalized or list(ALLOWED_ACTIONS)


def _select_action(allowed_actions: list[str], preferred: list[str]) -> str:
    for action in preferred:
        if action in allowed_actions:
            return action
    return allowed_actions[0] if allowed_actions else "defer"


def _add_violation(
    violations: list[dict[str, Any]],
    *,
    code: str,
    layer: str,
    severity: str,
    message: str,
    constraint_id: str | None = None,
    evidence_source_id: str | None = None,
    hard: bool = False,
) -> None:
    violation = {
        "code": code,
        "id": code,
        "layer": layer,
        "severity": severity,
        "message": message,
        "hard": hard,
    }
    if constraint_id:
        violation["constraint_id"] = constraint_id
    if evidence_source_id:
        violation["evidence_source_id"] = evidence_source_id
    violations.append(violation)


def _validate_endpoint(handoff: dict[str, Any], field: str, violations: list[dict[str, Any]]) -> None:
    endpoint = handoff.get(field)
    if not isinstance(endpoint, dict):
        _add_violation(
            violations,
            code=f"missing_{field}",
            layer="MI",
            severity="high",
            message=f"Handoff must include a structured {field} endpoint.",
            hard=True,
        )
        return
    if not _is_nonempty_string(endpoint.get("id")):
        _add_violation(
            violations,
            code=f"missing_{field}_id",
            layer="MI",
            severity="high",
            message=f"Handoff {field} must include a non-empty id.",
            hard=True,
        )
    if not _is_nonempty_string(endpoint.get("type")):
        _add_violation(
            violations,
            code=f"missing_{field}_type",
            layer="MI",
            severity="medium",
            message=f"Handoff {field} must include a type.",
            hard=False,
        )


def _validate_contract_shape(handoff: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    if not isinstance(handoff, dict):
        _add_violation(
            violations,
            code="invalid_handoff",
            layer="MI",
            severity="critical",
            message="Handoff payload must be an object.",
            hard=True,
        )
        return

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in handoff:
            _add_violation(
                violations,
                code=f"missing_{field}",
                layer="MI",
                severity="high",
                message=f"Handoff contract is missing required field: {field}.",
                hard=True,
            )

    if handoff.get("contract_version") != HANDOFF_CONTRACT_VERSION:
        _add_violation(
            violations,
            code="unsupported_contract_version",
            layer="MI",
            severity="high",
            message=f"Handoff contract_version must be {HANDOFF_CONTRACT_VERSION}.",
            hard=True,
        )

    if not _is_nonempty_string(handoff.get("handoff_id")):
        _add_violation(
            violations,
            code="missing_handoff_id",
            layer="MI",
            severity="high",
            message="Handoff must include a non-empty handoff_id.",
            hard=True,
        )

    _validate_endpoint(handoff, "sender", violations)
    _validate_endpoint(handoff, "recipient", violations)


def _validate_message(handoff: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    message_schema = handoff.get("message_schema")
    message = handoff.get("message")

    if not isinstance(message_schema, dict):
        _add_violation(
            violations,
            code="missing_message_schema",
            layer="C",
            severity="high",
            message="Handoff must include the recipient message schema.",
            hard=True,
        )
        return

    if not _is_nonempty_string(message_schema.get("kind")):
        _add_violation(
            violations,
            code="missing_message_schema_kind",
            layer="C",
            severity="high",
            message="Message schema must include a kind.",
            hard=True,
        )

    if not isinstance(message, dict) or not _is_nonempty_string(message.get("summary")):
        _add_violation(
            violations,
            code="missing_message_summary",
            layer="C",
            severity="high",
            message="Handoff message must include a non-empty redacted summary.",
            hard=True,
        )
        return

    if message_schema.get("redaction_required") and message.get("payload_redaction_status") == "unredacted":
        _add_violation(
            violations,
            code="unredacted_message_payload",
            layer="B",
            severity="high",
            message="Recipient requires redaction, but the handoff message payload is unredacted.",
            hard=True,
        )

    for assumption in _as_list(message.get("assumptions")):
        if not isinstance(assumption, dict):
            continue
        status = assumption.get("support_status")
        if status in {"unsupported", "contradicted"}:
            _add_violation(
                violations,
                code="unsupported_handoff_assumption",
                layer="P",
                severity="high" if status == "contradicted" else "medium",
                message=f"Handoff carries an assumption with support_status={status}.",
                evidence_source_id=assumption.get("evidence_source_id"),
                hard=status == "contradicted",
            )


def _validate_evidence(handoff: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    evidence = handoff.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        _add_violation(
            violations,
            code="missing_evidence",
            layer="P",
            severity="high",
            message="Constraint-coherent handoffs require at least one structured evidence object.",
            hard=True,
        )
        return

    for index, item in enumerate(evidence):
        report = validate_evidence_object(item, path=f"$.evidence[{index}]", require_link=True)
        for issue in report.get("issues", []):
            code = issue["path"].split(".")[-1].replace("[", "_").replace("]", "") if "." in issue["path"] else "evidence"
            _add_violation(
                violations,
                code=f"invalid_evidence_{code}",
                layer="F",
                severity="high",
                message=issue["message"],
                evidence_source_id=item.get("source_id") if isinstance(item, dict) else None,
                hard=True,
            )

    binding_report = validate_handoff_evidence_binding(
        handoff,
        registry_path=handoff.get("metadata", {}).get("evidence_registry_path")
        if isinstance(handoff.get("metadata"), dict)
        else None,
    )
    for issue in binding_report.get("issues", []):
        if not isinstance(issue, dict) or issue.get("level") != "error":
            continue
        code = "evidence_registry_binding_failed"
        issue_path = str(issue.get("path", ""))
        if issue_path.endswith(".source_id"):
            code = "unknown_evidence_source"
        elif issue_path.endswith(".trust_tier"):
            code = "disallowed_evidence_trust_tier"
        elif issue_path.endswith(".redaction_status"):
            code = "disallowed_evidence_redaction_status"
        elif issue_path.endswith(".retrieved_at"):
            code = "stale_or_invalid_evidence_freshness"
        elif "citation_url or retrieval_url" in str(issue.get("message", "")):
            code = "missing_evidence_provenance_link"
        _add_violation(
            violations,
            code=code,
            layer="F",
            severity="high",
            message=str(issue.get("message", "Evidence registry binding failed.")),
            hard=True,
        )
        if not isinstance(item, dict):
            _add_violation(
                violations,
                code="invalid_evidence_object",
                layer="F",
                severity="high",
                message=f"Evidence item {index} must be a structured evidence object.",
                hard=True,
            )
            continue
        source_id = item.get("source_id")
        if not _is_nonempty_string(source_id):
            _add_violation(
                violations,
                code="missing_evidence_source_id",
                layer="F",
                severity="medium",
                message=f"Evidence item {index} is missing source_id.",
                hard=False,
            )
        if not _is_nonempty_string(item.get("text")):
            _add_violation(
                violations,
                code="missing_evidence_text",
                layer="P",
                severity="high",
                message=f"Evidence item {index} is missing text.",
                evidence_source_id=source_id,
                hard=True,
            )
        if item.get("redaction_status") == "unredacted":
            _add_violation(
                violations,
                code="unredacted_evidence",
                layer="B",
                severity="high",
                message=f"Evidence item {index} is unredacted.",
                evidence_source_id=source_id,
                hard=True,
            )
        if item.get("trust_tier") == "untrusted":
            _add_violation(
                violations,
                code="untrusted_evidence",
                layer="F",
                severity="medium",
                message=f"Evidence item {index} is untrusted.",
                evidence_source_id=source_id,
                hard=False,
            )


def _message_summary(handoff: dict[str, Any]) -> dict[str, Any]:
    message = handoff.get("message") if isinstance(handoff.get("message"), dict) else {}
    return {
        "summary": message.get("summary"),
        "claims": _as_list(message.get("claims")),
        "assumptions": _as_list(message.get("assumptions")),
        "payload_redaction_status": message.get("payload_redaction_status"),
    }


def _evidence_summary(handoff: dict[str, Any]) -> list[dict[str, Any]]:
    summary = []
    for item in _as_list(handoff.get("evidence")):
        if not isinstance(item, dict):
            continue
        summary.append(
            {
                "source_id": item.get("source_id"),
                "trust_tier": item.get("trust_tier"),
                "retrieved_at": item.get("retrieved_at"),
                "redaction_status": item.get("redaction_status"),
                "citation_url": item.get("citation_url"),
                "retrieval_url": item.get("retrieval_url"),
                "supports": _as_list(item.get("supports")),
                "limits": _as_list(item.get("limits")),
                "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            }
        )
    return summary


def _metadata_summary(handoff: dict[str, Any]) -> dict[str, Any]:
    metadata = handoff.get("metadata") if isinstance(handoff.get("metadata"), dict) else {}
    safe_keys = {
        "workflow_id",
        "boundary_type",
        "connectivity",
        "downstream_count",
        "blast_radius",
        "irreversible",
        "irreversible_action",
        "requires_human_approval",
        "risk_tier",
        "mi_risk_tier",
    }
    summary = {key: metadata.get(key) for key in safe_keys if key in metadata}
    aix_config = metadata.get("aix") if isinstance(metadata.get("aix"), dict) else {}
    if "risk_tier" in aix_config:
        summary.setdefault("aix", {})["risk_tier"] = aix_config["risk_tier"]
    return summary


def _layer_score(verifier_scores: dict[str, Any], aix_layer: str) -> dict[str, Any]:
    score = verifier_scores.get(aix_layer)
    return score if isinstance(score, dict) else {}


def _constraint_result(
    *,
    constraint: dict[str, Any],
    layer_name: str,
    verifier_score: dict[str, Any],
) -> dict[str, Any]:
    aix_layer = LAYER_TO_AIX[layer_name]
    status = verifier_score.get("status", "unknown")
    hard = bool(constraint.get("hard"))
    if hard:
        result_status = "pass" if status in PASS_STATUSES else "fail"
    else:
        result_status = "pass" if status in SOFT_PASS_STATUSES else "unknown" if status == "unknown" else "fail"
    return {
        "id": constraint.get("id", f"{layer_name.lower()}_constraint"),
        "layer": aix_layer,
        "hard": hard,
        "status": result_status,
        "source_status": status,
    }


def _validate_constraints_and_scores(
    handoff: dict[str, Any],
    violations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    constraint_map = handoff.get("constraint_map")
    verifier_scores = handoff.get("verifier_scores")
    constraint_results = []
    feasible_region = {"K_P": [], "K_B": [], "K_C": []}

    if not isinstance(constraint_map, dict):
        _add_violation(
            violations,
            code="missing_constraint_map",
            layer="MI",
            severity="high",
            message="Handoff must include recipient-relative constraint_map.",
            hard=True,
        )
        return constraint_results, feasible_region

    if not isinstance(verifier_scores, dict):
        _add_violation(
            violations,
            code="missing_verifier_scores",
            layer="MI",
            severity="high",
            message="Handoff must include verifier_scores for recipient constraints.",
            hard=True,
        )
        verifier_scores = {}

    for layer_name in REQUIRED_CONSTRAINT_LAYERS:
        constraints = constraint_map.get(layer_name)
        aix_layer = LAYER_TO_AIX[layer_name]
        score = _layer_score(verifier_scores, aix_layer)

        if not isinstance(constraints, list) or not constraints:
            _add_violation(
                violations,
                code=f"missing_{layer_name}_constraints",
                layer=aix_layer,
                severity="high",
                message=f"Recipient feasible region must include at least one {layer_name} constraint.",
                hard=True,
            )
            continue

        if not score:
            _add_violation(
                violations,
                code=f"missing_{aix_layer}_verifier_score",
                layer=aix_layer,
                severity="high",
                message=f"Handoff must include a verifier score for {aix_layer}.",
                hard=True,
            )

        status = score.get("status", "unknown")
        if status == "fail":
            _add_violation(
                violations,
                code=f"{aix_layer}_verifier_failed",
                layer=aix_layer,
                severity="high",
                message=f"Recipient {layer_name} verifier failed.",
                hard=any(bool(item.get("hard")) for item in constraints if isinstance(item, dict)),
            )
        elif status == "unknown":
            _add_violation(
                violations,
                code=f"{aix_layer}_verifier_unknown",
                layer=aix_layer,
                severity="medium",
                message=f"Recipient {layer_name} verifier returned unknown status.",
                hard=any(bool(item.get("hard")) for item in constraints if isinstance(item, dict)),
            )

        for item in constraints:
            if not isinstance(item, dict):
                _add_violation(
                    violations,
                    code=f"invalid_{layer_name}_constraint",
                    layer=aix_layer,
                    severity="high",
                    message=f"{layer_name} constraints must be structured objects.",
                    hard=True,
                )
                continue
            constraint_id = item.get("id")
            if _is_nonempty_string(constraint_id):
                feasible_region[layer_name].append(constraint_id)
            else:
                _add_violation(
                    violations,
                    code=f"missing_{layer_name}_constraint_id",
                    layer=aix_layer,
                    severity="medium",
                    message=f"{layer_name} constraint is missing id.",
                    hard=False,
                )
            constraint_results.append(
                _constraint_result(
                    constraint=item,
                    layer_name=layer_name,
                    verifier_score=score,
                )
            )

    optional_f = constraint_map.get("F")
    if isinstance(optional_f, list) and optional_f:
        score = _layer_score(verifier_scores, "F")
        for item in optional_f:
            if isinstance(item, dict):
                constraint_results.append(_constraint_result(constraint=item, layer_name="F", verifier_score=score))

    return constraint_results, feasible_region


def _result_action(
    *,
    violations: list[dict[str, Any]],
    allowed_actions: list[str],
) -> tuple[str, str]:
    hard = [violation for violation in violations if violation.get("hard")]
    if hard:
        structural = any(
            violation.get("layer") == "MI"
            or str(violation.get("code", "")).startswith("missing_K_")
            or str(violation.get("code", "")).endswith("_verifier_score")
            for violation in hard
        )
        if structural:
            return "fail", _select_action(allowed_actions, ["defer", "ask", "refuse", "revise"])
        if any(
            violation.get("code")
            in {
                "missing_evidence",
                "missing_evidence_text",
                "unknown_evidence_source",
                "disallowed_evidence_trust_tier",
                "disallowed_evidence_redaction_status",
                "stale_or_invalid_evidence_freshness",
                "missing_evidence_provenance_link",
                "evidence_registry_binding_failed",
            }
            for violation in hard
        ):
            return "block", _select_action(allowed_actions, ["retrieve", "ask", "defer", "refuse"])
        return "block", _select_action(allowed_actions, ["revise", "retrieve", "ask", "defer", "refuse"])

    if violations:
        if any(violation.get("layer") in {"P", "F"} for violation in violations):
            return "block", _select_action(allowed_actions, ["retrieve", "ask", "revise", "defer", "refuse"])
        return "block", _select_action(allowed_actions, ["revise", "ask", "defer", "refuse"])

    return "pass", _select_action(allowed_actions, ["accept"])


def handoff_gate(handoff: dict[str, Any]) -> dict[str, Any]:
    """Check a handoff against recipient-relative constraints.

    Returns a Workflow/Agent-style gate result with gate_decision,
    recommended_action, verifier-derived constraint_results, AIx, violations,
    feasible_region, and redacted audit_summary.
    """

    violations: list[dict[str, Any]] = []
    _validate_contract_shape(handoff, violations)
    if isinstance(handoff, dict):
        _validate_message(handoff, violations)
        _validate_evidence(handoff, violations)
        constraint_results, feasible_region = _validate_constraints_and_scores(handoff, violations)
    else:
        constraint_results = []
        feasible_region = {"K_P": [], "K_B": [], "K_C": []}
        handoff = {}

    allowed_actions = _allowed_actions(handoff)
    gate_decision, recommended_action = _result_action(violations=violations, allowed_actions=allowed_actions)
    adapter = {"aix": handoff.get("metadata", {}).get("aix", {})} if isinstance(handoff.get("metadata"), dict) else {}
    aix_score = aix.calculate_aix(
        adapter=adapter,
        constraint_results=constraint_results,
        tool_report={"violations": violations},
        gate_decision=gate_decision,
        recommended_action=recommended_action,
    )

    hard_blockers = sorted(
        {
            blocker
            for blocker in aix_score.get("hard_blockers", [])
        }
        | {
            violation.get("constraint_id") or violation.get("code")
            for violation in violations
            if violation.get("hard")
        }
    )

    sender = handoff.get("sender") if isinstance(handoff.get("sender"), dict) else {}
    recipient = handoff.get("recipient") if isinstance(handoff.get("recipient"), dict) else {}
    evidence = _as_list(handoff.get("evidence"))
    evidence_binding = validate_handoff_evidence_binding(
        handoff,
        registry_path=handoff.get("metadata", {}).get("evidence_registry_path")
        if isinstance(handoff.get("metadata"), dict)
        else None,
    )
    handoff_aix = calculate_handoff_aix(
        handoff,
        constraint_results=constraint_results,
        violations=violations,
        gate_decision=gate_decision,
        recommended_action=recommended_action,
    )
    handoff_aix["hard_blockers"] = hard_blockers

    return {
        "contract_version": HANDOFF_CONTRACT_VERSION,
        "handoff_id": handoff.get("handoff_id"),
        "sender": sender,
        "recipient": recipient,
        "gate_decision": gate_decision,
        "recommended_action": recommended_action,
        "candidate_gate": "pass" if gate_decision == "pass" else "block",
        "feasible_region": feasible_region,
        "constraint_results": constraint_results,
        "verifier_scores": handoff.get("verifier_scores", {}),
        "message": _message_summary(handoff),
        "evidence_summary": _evidence_summary(handoff),
        "evidence_registry_binding": evidence_binding,
        "metadata": _metadata_summary(handoff),
        "violations": violations,
        "aix": {**aix_score, "hard_blockers": hard_blockers},
        "handoff_aix": handoff_aix,
        "audit_summary": {
            "handoff_id": handoff.get("handoff_id"),
            "sender_id": sender.get("id"),
            "recipient_id": recipient.get("id"),
            "gate_decision": gate_decision,
            "recommended_action": recommended_action,
            "aix_score": aix_score.get("score"),
            "aix_decision": aix_score.get("decision"),
            "handoff_aix_score": handoff_aix.get("score"),
            "handoff_aix_decision": handoff_aix.get("decision"),
            "hard_blockers": hard_blockers,
            "violation_codes": [violation.get("code") for violation in violations],
            "message_fingerprint": _fingerprint(handoff.get("message", {})),
            "evidence_fingerprints": [_fingerprint(item) for item in evidence if isinstance(item, dict)],
        },
    }


__all__ = ["HANDOFF_CONTRACT_VERSION", "handoff_gate"]
