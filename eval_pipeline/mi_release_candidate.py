"""Full AANA MI release-candidate orchestration."""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline.mi_audit_integrity import write_mi_audit_integrity_manifest
from eval_pipeline.mi_benchmark import run_mi_benchmark, write_mi_benchmark_report, write_mi_benchmark_workflows
from eval_pipeline.mi_observability import write_mi_dashboard_from_benchmark
from eval_pipeline.release_blocker_remediation import write_research_citation_remediation
from eval_pipeline.release_readiness_report import write_release_readiness_report


MI_RELEASE_CANDIDATE_VERSION = "0.1"
ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MI_BENCHMARK_DIR = ROOT / "eval_outputs" / "mi_benchmark"
DEFAULT_MI_RELEASE_CANDIDATE_REPORT = (
    ROOT / "eval_outputs" / "mi_release_candidate" / "aana_mi_release_candidate_report.json"
)
DEFAULT_PILOT_HANDOFFS = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "pilot_handoffs.json"
DEFAULT_AUDIT_JSONL = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_audit.jsonl"
DEFAULT_AUDIT_MANIFEST = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_audit.jsonl.sha256.json"
DEFAULT_DASHBOARD = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_dashboard.json"
DEFAULT_READINESS = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "production_mi_readiness.json"
DEFAULT_RELEASE_REPORT = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "production_mi_release_report.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _status_from_issues(issues: list[Any]) -> str:
    return "pass" if not issues else "block"


def _check(name: str, status: str, details: str, *, issues: list[Any] | None = None, artifacts: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "details": details,
        "issue_count": len(issues or []),
        "issues": issues or [],
        "artifacts": artifacts or {},
    }


def _issue_dicts(issues: list[Any]) -> list[dict[str, Any]]:
    rows = []
    for issue in issues:
        if hasattr(issue, "to_dict"):
            rows.append(issue.to_dict())
        elif isinstance(issue, dict):
            rows.append(issue)
        else:
            rows.append({"message": str(issue)})
    return rows


def _benchmark_check(report: dict[str, Any]) -> dict[str, Any]:
    issues = []
    full = report.get("metrics", {}).get("full_global_aana_gate", {})
    if report.get("workflow_count", 0) <= 0:
        issues.append({"path": "$.workflow_count", "message": "Benchmark must include at least one workflow."})
    if full.get("false_negative") != 0:
        issues.append({"path": "$.metrics.full_global_aana_gate.false_negative", "message": "Full global gate missed an expected MI issue."})
    if full.get("false_positive") != 0:
        issues.append({"path": "$.metrics.full_global_aana_gate.false_positive", "message": "Full global gate produced a false refusal."})
    return _check(
        "benchmark",
        _status_from_issues(issues),
        f"{report.get('workflow_count', 0)} benchmark workflow(s) evaluated.",
        issues=issues,
    )


def _pilot_check(guarded_payload: dict[str, Any]) -> dict[str, Any]:
    result = guarded_payload.get("result", {})
    if isinstance(result.get("after"), dict):
        pilot = result.get("after", {}).get("pilot_result", {})
        readiness = result.get("after", {}).get("production_mi_readiness", {})
        remediation_status = result.get("status")
    else:
        pilot = result.get("pilot_result", {})
        readiness = result.get("production_mi_readiness", {})
        remediation_status = None
    issues = []
    if pilot.get("handoff_count", 0) <= 0:
        issues.append({"path": "$.pilot_result.handoff_count", "message": "Pilot must include checked handoffs."})
    if not isinstance(pilot.get("mi_batch"), dict):
        issues.append({"path": "$.pilot_result.mi_batch", "message": "Pilot must include MI batch output."})
    if readiness.get("release_status") not in {"ready", "blocked"}:
        issues.append({"path": "$.production_mi_readiness.release_status", "message": "Readiness status must be ready or blocked."})
    return _check(
        "pilot",
        _status_from_issues(issues),
        (
            f"{pilot.get('handoff_count', 0)} pilot handoff(s) checked; "
            f"readiness={readiness.get('release_status')}; remediation={remediation_status}."
        ),
        issues=issues,
        artifacts=guarded_payload.get("paths", {}),
    )


def _release_status_check(release_report_payload: dict[str, Any]) -> dict[str, Any]:
    report = release_report_payload.get("report", {})
    unresolved = report.get("unresolved_items") if isinstance(report.get("unresolved_items"), list) else []
    status = "pass" if report.get("status") == "pass" else "block"
    return _check(
        "release_readiness",
        status,
        f"release_readiness={report.get('status')} unresolved={len(unresolved)}.",
        issues=unresolved,
        artifacts={"release_readiness_report": release_report_payload.get("path")},
    )


def _validation_check(name: str, issues: list[Any], details: str) -> dict[str, Any]:
    return _check(name, _status_from_issues(issues), details, issues=_issue_dicts(issues))


def run_mi_release_candidate(
    *,
    report_path: str | pathlib.Path = DEFAULT_MI_RELEASE_CANDIDATE_REPORT,
    benchmark_dir: str | pathlib.Path = DEFAULT_MI_BENCHMARK_DIR,
    allow_direct_execution: bool = False,
) -> dict[str, Any]:
    """Run all MI release-candidate checks and write one report."""

    from scripts.validation.validate_mi_contracts import (
        validate_audit_integrity_manifest,
        validate_audit_jsonl,
        validate_dashboard,
        validate_mi_contracts,
        validate_pilot_handoffs,
        validate_production_readiness,
        validate_release_readiness_report,
        validate_schema,
    )

    benchmark_path = pathlib.Path(benchmark_dir)
    benchmark_workflows_path = benchmark_path / "mi_benchmark_workflows.json"
    benchmark_report_path = benchmark_path / "mi_benchmark_report.json"
    benchmark_dashboard_path = benchmark_path / "mi_observability_dashboard.json"

    write_mi_benchmark_workflows(benchmark_workflows_path)
    write_mi_benchmark_report(benchmark_report_path)
    write_mi_dashboard_from_benchmark(benchmark_report_path, benchmark_dashboard_path)
    benchmark_report = run_mi_benchmark()

    guarded_payload = write_research_citation_remediation(allow_direct_execution=allow_direct_execution)
    write_mi_audit_integrity_manifest(DEFAULT_AUDIT_JSONL, DEFAULT_AUDIT_MANIFEST)
    release_payload = write_release_readiness_report(
        readiness=guarded_payload["result"]["after"]["production_mi_readiness"],
        artifact_paths=guarded_payload["paths"],
    )

    schema, schema_issues = validate_schema()
    checks = [
        _validation_check("schema", schema_issues, "Interoperability schema validation."),
        _benchmark_check(benchmark_report),
        _pilot_check(guarded_payload),
        _validation_check("audit", validate_audit_jsonl(DEFAULT_AUDIT_JSONL), "Redacted MI audit JSONL validation."),
        _validation_check(
            "audit_integrity",
            validate_audit_integrity_manifest(DEFAULT_AUDIT_JSONL, DEFAULT_AUDIT_MANIFEST),
            "MI audit SHA-256 integrity validation.",
        ),
        _validation_check("readiness", validate_production_readiness(DEFAULT_READINESS), "Production MI readiness validation."),
        _validation_check("dashboard", validate_dashboard(DEFAULT_DASHBOARD), "MI observability dashboard validation."),
        _release_status_check(release_payload),
        _validation_check(
            "release_report_contract",
            validate_release_readiness_report(DEFAULT_RELEASE_REPORT),
            "Release readiness report contract validation.",
        ),
    ]
    if schema is not None:
        checks.insert(
            1,
            _validation_check(
                "pilot_handoff_contracts",
                validate_pilot_handoffs(schema, DEFAULT_PILOT_HANDOFFS),
                "Pilot handoffs validate against interoperability schema.",
            ),
        )
    contract_report = validate_mi_contracts()
    checks.append(
        _check(
            "contract_validation",
            "pass" if contract_report.get("valid") else "block",
            "End-to-end MI contract validation.",
            issues=contract_report.get("issues", []),
            artifacts=contract_report.get("artifacts", {}),
        )
    )

    blocking_checks = [check for check in checks if check["status"] == "block"]
    report = {
        "mi_release_candidate_version": MI_RELEASE_CANDIDATE_VERSION,
        "created_at": _utc_now(),
        "status": "pass" if not blocking_checks else "block",
        "release_candidate": "aana_mi",
        "allow_direct_execution": bool(allow_direct_execution),
        "check_count": len(checks),
        "blocking_check_count": len(blocking_checks),
        "checks": checks,
        "artifacts": {
            "benchmark_workflows": str(benchmark_workflows_path),
            "benchmark_report": str(benchmark_report_path),
            "benchmark_dashboard": str(benchmark_dashboard_path),
            "pilot_handoffs": str(DEFAULT_PILOT_HANDOFFS),
            "audit_jsonl": str(DEFAULT_AUDIT_JSONL),
            "audit_manifest": str(DEFAULT_AUDIT_MANIFEST),
            "dashboard": str(DEFAULT_DASHBOARD),
            "readiness": str(DEFAULT_READINESS),
            "release_readiness_report": str(DEFAULT_RELEASE_REPORT),
            "release_candidate_report": str(pathlib.Path(report_path)),
        },
        "unresolved_items": [
            {
                "check": check["name"],
                "issue_count": check["issue_count"],
                "details": check["details"],
                "issues": check["issues"],
            }
            for check in blocking_checks
        ],
    }
    output_path = pathlib.Path(report_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report": report, "path": str(output_path), "bytes": output_path.stat().st_size}


__all__ = [
    "DEFAULT_MI_BENCHMARK_DIR",
    "DEFAULT_MI_RELEASE_CANDIDATE_REPORT",
    "MI_RELEASE_CANDIDATE_VERSION",
    "run_mi_release_candidate",
]
