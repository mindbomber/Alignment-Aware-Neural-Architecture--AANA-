"""Redacted human-review queue packets for MI defer routes."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline.mi_audit import RAW_CONTENT_FIELDS
from eval_pipeline.privacy_review import validate_redacted_artifact


HUMAN_REVIEW_QUEUE_VERSION = "0.1"
HUMAN_REVIEW_PACKET_TYPE = "mi_human_review_packet"
DEFAULT_HUMAN_REVIEW_QUEUE_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "eval_outputs" / "human_review" / "mi_review_queue.jsonl"
)
HUMAN_DECISIONS = ("approve", "reject", "request_revision", "request_retrieval", "ask_clarification", "defer")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _endpoint(value: Any) -> dict[str, Any]:
    endpoint = value if isinstance(value, dict) else {}
    return {
        "id": endpoint.get("id"),
        "type": endpoint.get("type"),
        "adapter_id": endpoint.get("adapter_id"),
        "trust_tier": endpoint.get("trust_tier"),
    }


def _aix_summary(value: Any) -> dict[str, Any]:
    aix = value if isinstance(value, dict) else {}
    return {
        "score": aix.get("score"),
        "decision": aix.get("decision"),
        "components": aix.get("components") if isinstance(aix.get("components"), dict) else {},
        "beta": aix.get("beta"),
        "thresholds": aix.get("thresholds") if isinstance(aix.get("thresholds"), dict) else {},
        "hard_blockers": list(aix.get("hard_blockers", [])) if isinstance(aix.get("hard_blockers"), list) else [],
    }


def _propagated_risk_summary(value: Any) -> dict[str, Any]:
    risk = value if isinstance(value, dict) else {}
    return {
        "risk_count": risk.get("risk_count", 0),
        "propagation_count": risk.get("propagation_count", 0),
        "has_propagated_risk": bool(risk.get("has_propagated_risk")),
        "severity_score": risk.get("severity_score"),
        "risk_counts": risk.get("risk_counts") if isinstance(risk.get("risk_counts"), dict) else {},
    }


def _violation_codes(value: Any) -> list[str]:
    codes = []
    for violation in value if isinstance(value, list) else []:
        if isinstance(violation, dict):
            code = violation.get("code") or violation.get("id")
            if code is not None:
                codes.append(str(code))
    return codes


def _hard_blockers(result: dict[str, Any]) -> list[str]:
    blockers = set()
    for key in ("hard_blockers", "blockers"):
        for blocker in result.get(key, []) if isinstance(result.get(key), list) else []:
            blockers.add(str(blocker))
    for key in ("aix", "handoff_aix", "global_aix", "workflow_aix"):
        block = result.get(key)
        if not isinstance(block, dict):
            continue
        for blocker in block.get("hard_blockers", []) if isinstance(block.get("hard_blockers"), list) else []:
            blockers.add(str(blocker))
    return sorted(blockers)


def _should_queue(result: dict[str, Any], *, include_non_defer: bool) -> bool:
    if include_non_defer:
        return True
    if result.get("recommended_action") == "defer":
        return True
    readiness = result.get("production_mi_readiness")
    if isinstance(readiness, dict) and readiness.get("recommended_action") == "defer":
        return True
    return False


def human_review_packet(
    result: dict[str, Any],
    *,
    workflow_id: str | None = None,
    requested_human_decision: str = "defer",
    created_at: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build a redacted human-review packet for a deferred MI route."""

    if requested_human_decision not in HUMAN_DECISIONS:
        raise ValueError(f"requested_human_decision must be one of: {', '.join(HUMAN_DECISIONS)}")
    result = result if isinstance(result, dict) else {}
    audit_summary = result.get("audit_summary") if isinstance(result.get("audit_summary"), dict) else {}
    global_aix = result.get("global_aix") or result.get("workflow_aix")
    aix_block = global_aix if isinstance(global_aix, dict) else result.get("aix")
    propagated_risk = result.get("propagated_risk")
    packet = {
        "human_review_queue_version": HUMAN_REVIEW_QUEUE_VERSION,
        "packet_type": HUMAN_REVIEW_PACKET_TYPE,
        "created_at": created_at or _utc_now(),
        "workflow_id": workflow_id or result.get("workflow_id") or audit_summary.get("workflow_id"),
        "handoff_id": result.get("handoff_id") or audit_summary.get("handoff_id"),
        "sender": _endpoint(result.get("sender")),
        "recipient": _endpoint(result.get("recipient")),
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "requested_human_decision": requested_human_decision,
        "reason": reason or "MI route deferred to human review.",
        "blockers": list(result.get("blockers", [])) if isinstance(result.get("blockers"), list) else [],
        "hard_blockers": _hard_blockers(result),
        "violation_codes": _violation_codes(result.get("violations")),
        "aix": _aix_summary(aix_block),
        "handoff_aix": _aix_summary(result.get("handoff_aix")),
        "propagated_risk": _propagated_risk_summary(propagated_risk),
        "fingerprints": {
            "message": audit_summary.get("message_fingerprint"),
            "evidence": list(audit_summary.get("evidence_fingerprints", []))
            if isinstance(audit_summary.get("evidence_fingerprints"), list)
            else [],
            "source_result": _fingerprint(
                {
                    "handoff_id": result.get("handoff_id"),
                    "gate_decision": result.get("gate_decision"),
                    "recommended_action": result.get("recommended_action"),
                    "aix": _aix_summary(aix_block),
                    "hard_blockers": _hard_blockers(result),
                    "violation_codes": _violation_codes(result.get("violations")),
                }
            ),
        },
    }
    packet["packet_fingerprint"] = _fingerprint(packet)
    return packet


def human_review_packets(
    workflow_result: dict[str, Any] | list[dict[str, Any]],
    *,
    requested_human_decision: str = "defer",
    include_non_defer: bool = False,
) -> list[dict[str, Any]]:
    """Build redacted review packets for deferred handoffs in a workflow result."""

    if isinstance(workflow_result, dict) and isinstance(workflow_result.get("results"), list):
        results = [item for item in workflow_result["results"] if isinstance(item, dict)]
        workflow_aix = workflow_result.get("workflow_aix") if isinstance(workflow_result.get("workflow_aix"), dict) else {}
        propagated_risk = workflow_result.get("propagated_risk") if isinstance(workflow_result.get("propagated_risk"), dict) else {}
        workflow_id = workflow_aix.get("workflow_id") if isinstance(workflow_aix, dict) else None
        enriched = []
        for item in results:
            copy = dict(item)
            copy.setdefault("workflow_aix", workflow_aix)
            copy.setdefault("global_aix", workflow_result.get("global_aix", workflow_aix))
            copy.setdefault("propagated_risk", propagated_risk)
            enriched.append(copy)
        results = enriched
    elif isinstance(workflow_result, list):
        results = [item for item in workflow_result if isinstance(item, dict)]
        workflow_id = None
    elif isinstance(workflow_result, dict):
        results = [workflow_result]
        workflow_id = workflow_result.get("workflow_id")
    else:
        results = []
        workflow_id = None

    return [
        human_review_packet(
            item,
            workflow_id=workflow_id,
            requested_human_decision=requested_human_decision,
        )
        for item in results
        if _should_queue(item, include_non_defer=include_non_defer)
    ]


def append_human_review_queue_jsonl(
    path: str | pathlib.Path,
    packets: dict[str, Any] | list[dict[str, Any]],
) -> str:
    """Append redacted human-review packets to a JSONL queue."""

    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = packets if isinstance(packets, list) else [packets]
    with output_path.open("a", encoding="utf-8") as handle:
        for packet in rows:
            handle.write(json.dumps(packet, sort_keys=True, ensure_ascii=False) + "\n")
    return str(output_path)


def load_human_review_queue_jsonl(path: str | pathlib.Path) -> list[dict[str, Any]]:
    packets = []
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                packet = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid human-review queue packet at line {line_number}: {exc}") from exc
            if not isinstance(packet, dict):
                raise ValueError(f"Human-review queue packet at line {line_number} must be an object.")
            packets.append(packet)
    return packets


def validate_human_review_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Validate that a human-review packet contains only redacted decision metadata."""

    issues = []
    if not isinstance(packet, dict):
        return {"valid": False, "issues": [{"path": "$", "message": "Human-review packet must be an object."}]}
    if packet.get("human_review_queue_version") != HUMAN_REVIEW_QUEUE_VERSION:
        issues.append({"path": "$.human_review_queue_version", "message": f"Must be {HUMAN_REVIEW_QUEUE_VERSION}."})
    if packet.get("packet_type") != HUMAN_REVIEW_PACKET_TYPE:
        issues.append({"path": "$.packet_type", "message": f"Must be {HUMAN_REVIEW_PACKET_TYPE}."})
    if packet.get("requested_human_decision") not in HUMAN_DECISIONS:
        issues.append({"path": "$.requested_human_decision", "message": "Requested human decision is not supported."})
    for field in ("sender", "recipient", "aix", "handoff_aix", "propagated_risk", "fingerprints"):
        if not isinstance(packet.get(field), dict):
            issues.append({"path": f"$.{field}", "message": f"{field} must be an object."})
    for field in ("blockers", "hard_blockers", "violation_codes"):
        if not isinstance(packet.get(field), list):
            issues.append({"path": f"$.{field}", "message": f"{field} must be an array."})
    for raw_field in RAW_CONTENT_FIELDS:
        if raw_field in packet:
            issues.append({"path": f"$.{raw_field}", "message": "Raw MI content field is not allowed in review packets."})
    privacy_report = validate_redacted_artifact(packet, artifact="human_review_packet")
    issues.extend(
        {"path": issue.get("path", "$"), "message": issue.get("message", "Privacy review failed.")}
        for issue in privacy_report.get("issues", [])
    )
    return {"valid": not issues, "issues": issues}


def validate_human_review_packets(packets: list[dict[str, Any]]) -> dict[str, Any]:
    issues = []
    for index, packet in enumerate(packets if isinstance(packets, list) else []):
        report = validate_human_review_packet(packet)
        for issue in report["issues"]:
            issues.append({"path": f"$[{index}]{issue['path'][1:]}", "message": issue["message"]})
    if not isinstance(packets, list):
        issues.append({"path": "$", "message": "Human-review packets must be a list."})
    return {"valid": not issues, "issues": issues, "packet_count": len(packets) if isinstance(packets, list) else 0}


def enqueue_defer_reviews(
    workflow_result: dict[str, Any] | list[dict[str, Any]],
    path: str | pathlib.Path = DEFAULT_HUMAN_REVIEW_QUEUE_PATH,
    *,
    requested_human_decision: str = "defer",
    include_non_defer: bool = False,
) -> dict[str, Any]:
    """Create and append redacted review packets for deferred routes."""

    packets = human_review_packets(
        workflow_result,
        requested_human_decision=requested_human_decision,
        include_non_defer=include_non_defer,
    )
    if packets:
        append_human_review_queue_jsonl(path, packets)
    return {"path": str(pathlib.Path(path)), "packet_count": len(packets), "packets": packets}


__all__ = [
    "DEFAULT_HUMAN_REVIEW_QUEUE_PATH",
    "HUMAN_DECISIONS",
    "HUMAN_REVIEW_PACKET_TYPE",
    "HUMAN_REVIEW_QUEUE_VERSION",
    "append_human_review_queue_jsonl",
    "enqueue_defer_reviews",
    "human_review_packet",
    "human_review_packets",
    "load_human_review_queue_jsonl",
    "validate_human_review_packet",
    "validate_human_review_packets",
]
