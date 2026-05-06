"""Machine-checkable release readiness report for production MI."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from eval_pipeline.human_review_queue import load_human_review_queue_jsonl, validate_human_review_packets
from eval_pipeline.mi_audit import load_mi_audit_jsonl, validate_mi_audit_records
from eval_pipeline.mi_observability import MI_OBSERVABILITY_DASHBOARD_VERSION
from eval_pipeline.production_readiness import DEFAULT_CHECKLIST_PATH, production_mi_readiness_gate


RELEASE_READINESS_REPORT_VERSION = "0.1"
ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_REPORT_PATH = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "production_mi_release_report.json"
DEFAULT_RELEASE_ARTIFACT_PATHS = {
    "audit_jsonl": ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_audit.jsonl",
    "pilot_result": ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "pilot_result.json",
    "dashboard": ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_dashboard.json",
    "human_review_queue": ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_human_review_queue.jsonl",
}

_REQUIRED_GATE_ROUTE_BY_BLOCKER = {
    "mi-checks-present": "defer",
    "evidence-present": "retrieve",
    "no-hard-blockers": "refuse",
    "global-aix-threshold": "revise_or_defer",
    "propagation-resolved": "revise_or_ask",
}


def _load_json(path: str | pathlib.Path) -> dict[str, Any]:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _slug(value: str) -> str:
    return "-".join("".join(character.lower() if character.isalnum() else "-" for character in value).split("-")).strip("-")


def parse_release_checklist_markdown(path: str | pathlib.Path = DEFAULT_CHECKLIST_PATH) -> dict[str, Any]:
    """Parse the production release checklist into required checks and signoff rows."""

    checklist_path = pathlib.Path(path)
    text = checklist_path.read_text(encoding="utf-8")
    section = None
    required_checks = []
    blocking_conditions = []
    release_signoff = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if line.startswith("## "):
            section = line.removeprefix("## ").strip()
            continue
        if section == "Required Gate" and line.startswith("- "):
            label = line[2:].strip()
            required_checks.append({"id": _slug(label), "label": label, "line": line_number})
        elif section == "Blocking Conditions" and line.startswith("|") and "---" not in line and "Condition" not in line:
            cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
            if len(cells) == 2 and cells[0]:
                blocking_conditions.append(
                    {
                        "condition": cells[0],
                        "required_route": cells[1],
                        "line": line_number,
                    }
                )
        elif section == "Release Signoff" and line.startswith("- "):
            label = line[2:].strip()
            release_signoff.append({"id": _slug(label), "label": label, "line": line_number})

    return {
        "path": str(checklist_path),
        "required_checks": required_checks,
        "blocking_conditions": blocking_conditions,
        "release_signoff": release_signoff,
    }


def _artifact_item(item_id: str, label: str, passed: bool, details: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "status": "pass" if passed else "block",
        "details": details,
    }


def _audit_item(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return _artifact_item("audit-jsonl-attached", "Attach the redacted MI audit JSONL for the run.", False, "Missing audit JSONL.")
    try:
        records = load_mi_audit_jsonl(path)
        report = validate_mi_audit_records(records)
    except ValueError as exc:
        return _artifact_item("audit-jsonl-attached", "Attach the redacted MI audit JSONL for the run.", False, str(exc))
    return _artifact_item(
        "audit-jsonl-attached",
        "Attach the redacted MI audit JSONL for the run.",
        bool(report.get("valid") and report.get("record_count", 0) > 0),
        f"{report.get('record_count', 0)} redacted audit record(s) validated.",
    )


def _pilot_result_item(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return _artifact_item(
            "redacted-result-attached",
            "Attach the workflow or pilot result with raw private content excluded from release notes.",
            False,
            "Missing pilot result JSON.",
        )
    try:
        result = _load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return _artifact_item("redacted-result-attached", "Attach the workflow or pilot result.", False, str(exc))
    return _artifact_item(
        "redacted-result-attached",
        "Attach the workflow or pilot result with raw private content excluded from release notes.",
        bool(result.get("mi_batch")),
        "Pilot result contains MI batch metadata." if result.get("mi_batch") else "Pilot result is missing MI batch metadata.",
    )


def _dashboard_item(path: pathlib.Path, readiness: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return _artifact_item(
            "dashboard-propagation-clear",
            "Confirm the dashboard shows no unresolved propagated-risk signal for this workflow.",
            False,
            "Missing dashboard JSON.",
        )
    try:
        dashboard = _load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return _artifact_item("dashboard-propagation-clear", "Confirm dashboard propagated-risk state.", False, str(exc))
    dashboard_version_ok = dashboard.get("mi_observability_dashboard_version") == MI_OBSERVABILITY_DASHBOARD_VERSION
    propagated_risk = readiness.get("propagated_risk") if isinstance(readiness.get("propagated_risk"), dict) else {}
    risk_clear = not (
        propagated_risk.get("has_propagated_risk")
        or propagated_risk.get("risk_count", 0)
        or propagated_risk.get("propagation_count", 0)
    )
    return _artifact_item(
        "dashboard-propagation-clear",
        "Confirm the dashboard shows no unresolved propagated-risk signal for this workflow.",
        bool(dashboard_version_ok and risk_clear),
        "No unresolved propagated-risk signal." if risk_clear else "Readiness still reports unresolved propagated risk.",
    )


def _risk_tier_item(readiness: dict[str, Any]) -> dict[str, Any]:
    global_aix = readiness.get("global_aix") if isinstance(readiness.get("global_aix"), dict) else {}
    risk_tier = global_aix.get("risk_tier")
    return _artifact_item(
        "risk-tier-confirmed",
        "Confirm the selected risk tier matches connectivity, irreversibility, privacy, security, and downstream blast radius.",
        isinstance(risk_tier, str) and bool(risk_tier.strip()),
        f"Risk tier: {risk_tier}" if risk_tier else "Missing global AIx risk tier.",
    )


def _human_review_item(path: pathlib.Path, readiness: dict[str, Any]) -> dict[str, Any]:
    release_blocked = readiness.get("release_status") == "blocked"
    if not release_blocked:
        return _artifact_item(
            "human-review-channel-present",
            "Confirm any human-review queue or incident channel exists before enabling direct execution.",
            True,
            "Release is ready; human review channel is not required for this run.",
        )
    if not path.exists():
        return _artifact_item(
            "human-review-channel-present",
            "Confirm any human-review queue or incident channel exists before enabling direct execution.",
            False,
            "Blocked release has no human-review queue artifact.",
        )
    try:
        packets = load_human_review_queue_jsonl(path)
        report = validate_human_review_packets(packets)
    except ValueError as exc:
        return _artifact_item("human-review-channel-present", "Confirm human-review queue exists.", False, str(exc))
    return _artifact_item(
        "human-review-channel-present",
        "Confirm any human-review queue or incident channel exists before enabling direct execution.",
        bool(report.get("valid") and report.get("packet_count", 0) > 0),
        f"{report.get('packet_count', 0)} redacted human-review packet(s) validated.",
    )


def _signoff_items(readiness: dict[str, Any], artifact_paths: dict[str, pathlib.Path]) -> list[dict[str, Any]]:
    return [
        _audit_item(artifact_paths["audit_jsonl"]),
        _pilot_result_item(artifact_paths["pilot_result"]),
        _dashboard_item(artifact_paths["dashboard"], readiness),
        _risk_tier_item(readiness),
        _human_review_item(artifact_paths["human_review_queue"], readiness),
    ]


def _unresolved_items(items: list[dict[str, Any]], *, category: str) -> list[dict[str, Any]]:
    unresolved = []
    for item in items:
        if item.get("status") != "block":
            continue
        unresolved.append(
            {
                "category": category,
                "id": item.get("id"),
                "label": item.get("label"),
                "details": item.get("details"),
                "required_route": _REQUIRED_GATE_ROUTE_BY_BLOCKER.get(str(item.get("id"))),
            }
        )
    return unresolved


def release_readiness_report(
    mi_result: dict[str, Any] | None = None,
    *,
    readiness: dict[str, Any] | None = None,
    artifact_paths: dict[str, str | pathlib.Path] | None = None,
    checklist_path: str | pathlib.Path = DEFAULT_CHECKLIST_PATH,
    high_risk_action: bool = True,
) -> dict[str, Any]:
    """Build a machine-checkable release report from the MI checklist and readiness state."""

    if readiness is None:
        readiness = production_mi_readiness_gate(mi_result or {}, high_risk_action=high_risk_action)
    paths = {key: pathlib.Path(value) for key, value in DEFAULT_RELEASE_ARTIFACT_PATHS.items()}
    for key, value in (artifact_paths or {}).items():
        if key in paths:
            paths[key] = pathlib.Path(value)

    checklist = parse_release_checklist_markdown(checklist_path)
    required_gate_items = [
        {
            "id": item.get("id"),
            "label": item.get("label"),
            "status": item.get("status"),
            "details": item.get("details"),
            "required_route": _REQUIRED_GATE_ROUTE_BY_BLOCKER.get(str(item.get("id"))),
        }
        for item in readiness.get("checklist", [])
        if isinstance(item, dict)
    ]
    signoff_items = _signoff_items(readiness, paths)
    unresolved = [
        *_unresolved_items(required_gate_items, category="required_gate"),
        *_unresolved_items(signoff_items, category="release_signoff"),
    ]
    status = "pass" if readiness.get("release_status") == "ready" and not unresolved else "block"
    return {
        "release_readiness_report_version": RELEASE_READINESS_REPORT_VERSION,
        "status": status,
        "release_status": readiness.get("release_status"),
        "can_execute_directly": bool(readiness.get("can_execute_directly")) and status == "pass",
        "recommended_action": readiness.get("recommended_action"),
        "checklist_source": {
            "path": checklist["path"],
            "required_check_count": len(checklist["required_checks"]),
            "blocking_condition_count": len(checklist["blocking_conditions"]),
            "release_signoff_count": len(checklist["release_signoff"]),
        },
        "blocking_conditions": checklist["blocking_conditions"],
        "required_gate_items": required_gate_items,
        "release_signoff_items": signoff_items,
        "unresolved_items": unresolved,
        "counts": {
            "required_gate_block_count": sum(1 for item in required_gate_items if item.get("status") == "block"),
            "release_signoff_block_count": sum(1 for item in signoff_items if item.get("status") == "block"),
            "unresolved_count": len(unresolved),
        },
    }


def write_release_readiness_report(
    path: str | pathlib.Path = DEFAULT_RELEASE_REPORT_PATH,
    mi_result: dict[str, Any] | None = None,
    *,
    readiness: dict[str, Any] | None = None,
    artifact_paths: dict[str, str | pathlib.Path] | None = None,
    checklist_path: str | pathlib.Path = DEFAULT_CHECKLIST_PATH,
    high_risk_action: bool = True,
) -> dict[str, Any]:
    """Write the machine-checkable release readiness report."""

    report = release_readiness_report(
        mi_result,
        readiness=readiness,
        artifact_paths=artifact_paths,
        checklist_path=checklist_path,
        high_risk_action=high_risk_action,
    )
    output_path = pathlib.Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report": report, "path": str(output_path), "bytes": output_path.stat().st_size}


__all__ = [
    "DEFAULT_RELEASE_ARTIFACT_PATHS",
    "DEFAULT_RELEASE_REPORT_PATH",
    "RELEASE_READINESS_REPORT_VERSION",
    "parse_release_checklist_markdown",
    "release_readiness_report",
    "write_release_readiness_report",
]
