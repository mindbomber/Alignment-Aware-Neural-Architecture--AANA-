"""Propagated risk tracking for MI handoff networks."""

from __future__ import annotations

from typing import Any


PROPAGATED_RISK_VERSION = "0.1"
RISK_SEVERITY_WEIGHT = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "info": 0,
    "unknown": 1,
}


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("results"), list):
        return [item for item in value["results"] if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _message(item: dict[str, Any]) -> dict[str, Any]:
    message = item.get("message")
    return message if isinstance(message, dict) else {}


def _evidence(item: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = item.get("evidence_summary")
    if isinstance(evidence, list):
        return [entry for entry in evidence if isinstance(entry, dict)]
    raw = item.get("evidence")
    return [entry for entry in raw if isinstance(entry, dict)] if isinstance(raw, list) else []


def _handoff_id(item: dict[str, Any], index: int) -> str:
    return str(item.get("handoff_id") or item.get("handoff_aix", {}).get("handoff_id") or f"handoff-{index}")


def _sender(item: dict[str, Any]) -> str | None:
    sender = item.get("sender")
    return sender.get("id") if isinstance(sender, dict) else item.get("sender_id")


def _recipient(item: dict[str, Any]) -> str | None:
    recipient = item.get("recipient")
    return recipient.get("id") if isinstance(recipient, dict) else item.get("recipient_id")


def _risk(
    *,
    kind: str,
    handoff_id: str,
    sender_id: str | None,
    recipient_id: str | None,
    severity: str,
    description: str,
    source: str | None = None,
    premise_of: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "handoff_id": handoff_id,
        "sender_id": sender_id,
        "recipient_id": recipient_id,
        "severity": severity,
        "description": description,
        "source": source,
        "premise_of": premise_of,
    }


def _supported_claims(evidence: list[dict[str, Any]]) -> set[str]:
    supported = set()
    for item in evidence:
        for claim in item.get("supports", []) if isinstance(item.get("supports"), list) else []:
            supported.add(str(claim).strip().lower())
    return supported


def _claim_key(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("description") or value.get("text") or "").strip().lower()
    return str(value).strip().lower()


def _accepted(item: dict[str, Any]) -> bool:
    return item.get("gate_decision") == "pass" and item.get("recommended_action") == "accept"


def _track_item_risks(item: dict[str, Any], *, index: int) -> list[dict[str, Any]]:
    handoff_id = _handoff_id(item, index)
    sender_id = _sender(item)
    recipient_id = _recipient(item)
    message = _message(item)
    evidence = _evidence(item)
    risks = []

    for assumption in message.get("assumptions", []) if isinstance(message.get("assumptions"), list) else []:
        if not isinstance(assumption, dict):
            continue
        status = assumption.get("support_status", "unknown")
        if status in {"unknown", "unsupported", "contradicted"}:
            severity = "high" if status == "contradicted" else "medium"
            risks.append(
                _risk(
                    kind="hidden_assumption",
                    handoff_id=handoff_id,
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    severity=severity,
                    description=assumption.get("description") or assumption.get("id") or "Unsupported assumption.",
                    source=assumption.get("source_handoff_id") or assumption.get("evidence_source_id"),
                )
            )

    supported = _supported_claims(evidence)
    for claim in message.get("claims", []) if isinstance(message.get("claims"), list) else []:
        key = _claim_key(claim)
        if key and supported and key in supported:
            continue
        severity = "medium" if supported else "low"
        risks.append(
            _risk(
                kind="unsupported_claim",
                handoff_id=handoff_id,
                sender_id=sender_id,
                recipient_id=recipient_id,
                severity=severity,
                description=str(claim),
            )
        )

    for evidence_item in evidence:
        metadata = evidence_item.get("metadata") if isinstance(evidence_item.get("metadata"), dict) else {}
        stale = metadata.get("stale") is True or metadata.get("freshness_status") == "stale"
        if stale:
            risks.append(
                _risk(
                    kind="stale_evidence",
                    handoff_id=handoff_id,
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    severity="high",
                    description=f"Evidence source {evidence_item.get('source_id')} is stale.",
                    source=evidence_item.get("source_id"),
                )
            )

    violations = item.get("violations") if isinstance(item.get("violations"), list) else []
    if _accepted(item) and violations:
        for violation in violations:
            if not isinstance(violation, dict):
                continue
            risks.append(
                _risk(
                    kind="accepted_violation",
                    handoff_id=handoff_id,
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    severity=violation.get("severity", "unknown"),
                    description=violation.get("message") or violation.get("code") or "Accepted violation.",
                    source=violation.get("code") or violation.get("id"),
                )
            )

    for violation in violations:
        if not isinstance(violation, dict):
            continue
        code = str(violation.get("code") or violation.get("id") or "")
        message_text = str(violation.get("message") or "")
        if "stale" in code or "stale" in message_text.lower():
            risks.append(
                _risk(
                    kind="stale_evidence",
                    handoff_id=handoff_id,
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    severity=violation.get("severity", "high"),
                    description=message_text or code,
                    source=violation.get("evidence_source_id"),
                )
            )

    return risks


def _propagation_links(items: list[dict[str, Any]], risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risk_by_handoff = {}
    for risk in risks:
        risk_by_handoff.setdefault(risk["handoff_id"], []).append(risk)

    links = []
    for index, item in enumerate(items):
        handoff_id = _handoff_id(item, index)
        message = _message(item)
        for assumption in message.get("assumptions", []) if isinstance(message.get("assumptions"), list) else []:
            if not isinstance(assumption, dict):
                continue
            source_handoff_id = assumption.get("source_handoff_id")
            if not source_handoff_id or source_handoff_id not in risk_by_handoff:
                continue
            for upstream in risk_by_handoff[source_handoff_id]:
                links.append(
                    {
                        "kind": "uncertain_output_became_premise",
                        "source_handoff_id": source_handoff_id,
                        "downstream_handoff_id": handoff_id,
                        "upstream_risk_kind": upstream["kind"],
                        "premise": assumption.get("description") or assumption.get("id"),
                        "severity": "high" if upstream["severity"] in {"critical", "high"} else "medium",
                    }
                )
    return links


def track_propagated_risk(handoff_results: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    """Track assumptions, claims, stale evidence, and accepted violations across handoffs."""

    item_list = _items(handoff_results)
    risks = []
    for index, item in enumerate(item_list):
        risks.extend(_track_item_risks(item, index=index))
    propagation_links = _propagation_links(item_list, risks)

    severity_score = sum(RISK_SEVERITY_WEIGHT.get(risk.get("severity", "unknown"), 1) for risk in risks)
    severity_score += sum(RISK_SEVERITY_WEIGHT.get(link.get("severity", "medium"), 2) for link in propagation_links)
    risk_counts = {}
    for risk in risks:
        risk_counts[risk["kind"]] = risk_counts.get(risk["kind"], 0) + 1
    for link in propagation_links:
        risk_counts[link["kind"]] = risk_counts.get(link["kind"], 0) + 1

    return {
        "propagated_risk_version": PROPAGATED_RISK_VERSION,
        "handoff_count": len(item_list),
        "risk_count": len(risks),
        "propagation_count": len(propagation_links),
        "risk_counts": risk_counts,
        "severity_score": severity_score,
        "risks": risks,
        "propagation_links": propagation_links,
        "has_propagated_risk": bool(risks or propagation_links),
    }


__all__ = ["PROPAGATED_RISK_VERSION", "track_propagated_risk"]
