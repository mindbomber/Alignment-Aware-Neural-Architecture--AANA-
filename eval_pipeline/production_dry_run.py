"""End-to-end production dry run for AANA MI release artifacts."""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline.human_signoff import DEFAULT_HUMAN_SIGNOFF_PATH
from eval_pipeline.live_connector_readiness import (
    DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH,
    write_live_connector_readiness_plan,
)
from eval_pipeline.mi_release import DEFAULT_MI_RELEASE_REPORT, run_mi_release
from eval_pipeline.mi_release_bundle import DEFAULT_MI_RELEASE_BUNDLE_DIR
from eval_pipeline.mi_release_candidate import DEFAULT_MI_BENCHMARK_DIR, DEFAULT_MI_RELEASE_CANDIDATE_REPORT
from eval_pipeline.production_deployment_manifest import (
    DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH,
    validate_production_deployment_manifest,
    write_production_deployment_manifest,
)


PRODUCTION_DRY_RUN_VERSION = "0.1"
PRODUCTION_DRY_RUN_REPORT_TYPE = "aana_mi_production_dry_run_report"
DEFAULT_PRODUCTION_DRY_RUN_REPORT_PATH = DEFAULT_MI_RELEASE_BUNDLE_DIR / "production_dry_run_report.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stage(name: str, status: str, details: str, *, artifacts: dict[str, str] | None = None) -> dict[str, Any]:
    return {"name": name, "status": status, "details": details, "artifacts": artifacts or {}}


def _deployment_manifest_paths(bundle_dir: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    return bundle_dir / "release_manifest.json", bundle_dir / "release_bundle_verification.json"


def run_production_dry_run(
    *,
    output_path: str | pathlib.Path = DEFAULT_PRODUCTION_DRY_RUN_REPORT_PATH,
    release_report_path: str | pathlib.Path = DEFAULT_MI_RELEASE_REPORT,
    rc_report_path: str | pathlib.Path = DEFAULT_MI_RELEASE_CANDIDATE_REPORT,
    benchmark_dir: str | pathlib.Path = DEFAULT_MI_BENCHMARK_DIR,
    bundle_dir: str | pathlib.Path = DEFAULT_MI_RELEASE_BUNDLE_DIR,
    deployment_manifest_path: str | pathlib.Path = DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH,
    human_signoff_path: str | pathlib.Path = DEFAULT_HUMAN_SIGNOFF_PATH,
    live_connector_plan_path: str | pathlib.Path = DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH,
) -> dict[str, Any]:
    """Run local release and deployment gates without live external actions."""

    bundle_path = pathlib.Path(bundle_dir)
    live_plan_payload = write_live_connector_readiness_plan(live_connector_plan_path)
    release_payload = run_mi_release(
        output_path=release_report_path,
        rc_report_path=rc_report_path,
        benchmark_dir=benchmark_dir,
        bundle_dir=bundle_path,
        allow_direct_execution=False,
    )
    release_manifest_path, verification_path = _deployment_manifest_paths(bundle_path)
    deployment_payload = write_production_deployment_manifest(
        deployment_manifest_path,
        release_manifest_path=release_manifest_path,
        verification_path=verification_path,
        human_signoff_path=human_signoff_path,
        live_connector_plan_path=live_connector_plan_path,
    )
    deployment_manifest = deployment_payload["manifest"]
    deployment_validation = validate_production_deployment_manifest(deployment_manifest)
    release_report = release_payload["report"]

    stages = [
        _stage(
            "live_connector_readiness_plan",
            "pass" if live_plan_payload["validation"]["valid"] else "block",
            (
                f"connectors={live_plan_payload['plan']['summary']['connector_count']} "
                f"live_enabled={live_plan_payload['plan']['summary']['live_execution_enabled_count']}"
            ),
            artifacts={"live_connector_readiness_plan": live_plan_payload["path"]},
        ),
        _stage(
            "local_mi_release",
            release_report["status"],
            f"stages={release_report['stage_count']} blocking={release_report['blocking_stage_count']} skipped={release_report['skipped_stage_count']}",
            artifacts={"mi_release_report": release_payload["path"]},
        ),
        _stage(
            "deployment_manifest",
            "pass" if deployment_validation["valid"] else "block",
            f"deployment_status={deployment_manifest['deployment_status']} blockers={len(deployment_manifest['blockers'])}",
            artifacts={"production_deployment_manifest": deployment_payload["path"]},
        ),
        _stage(
            "live_external_actions",
            "pass",
            "No live external actions were attempted; allow_direct_execution=false.",
        ),
    ]
    unresolved_items = []
    unresolved_items.extend(release_report.get("release_candidate", {}).get("unresolved_items", []))
    unresolved_items.extend(
        {
            "code": blocker,
            "source": "production_deployment_manifest",
            "required_action": "resolve before live deployment",
        }
        for blocker in deployment_manifest.get("blockers", [])
    )
    unresolved_items.extend(
        {
            "code": "deployment_manifest_validation_issue",
            "source": issue.get("path", "$"),
            "required_action": issue.get("message", "Fix deployment manifest validation issue."),
        }
        for issue in deployment_validation.get("issues", [])
    )

    blocking_stages = [stage for stage in stages if stage["status"] == "block"]
    dry_run_status = "pass" if not blocking_stages and not unresolved_items else "block"
    report = {
        "production_dry_run_version": PRODUCTION_DRY_RUN_VERSION,
        "report_type": PRODUCTION_DRY_RUN_REPORT_TYPE,
        "created_at": _utc_now(),
        "status": dry_run_status,
        "dry_run": True,
        "live_external_actions_attempted": False,
        "allow_direct_execution": False,
        "stage_count": len(stages),
        "blocking_stage_count": len(blocking_stages),
        "unresolved_item_count": len(unresolved_items),
        "unresolved_items": unresolved_items,
        "stages": stages,
        "release_report": {
            "path": release_payload["path"],
            "status": release_report["status"],
            "blocking_stage_count": release_report["blocking_stage_count"],
            "skipped_stage_count": release_report["skipped_stage_count"],
        },
        "deployment_manifest": {
            "path": deployment_payload["path"],
            "valid": deployment_validation["valid"],
            "deployment_status": deployment_manifest["deployment_status"],
            "deployment_authorized": deployment_manifest["deployment_authorized"],
            "blockers": deployment_manifest["blockers"],
        },
        "gate_confirmation": {
            "release_gates": release_report["status"],
            "deployment_gate": deployment_manifest["deployment_status"],
            "unresolved_items_explicit": bool(unresolved_items) == (dry_run_status == "block"),
            "external_actions_blocked": True,
        },
    }
    output = pathlib.Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report": report, "path": str(output), "bytes": output.stat().st_size}


__all__ = [
    "DEFAULT_PRODUCTION_DRY_RUN_REPORT_PATH",
    "PRODUCTION_DRY_RUN_REPORT_TYPE",
    "PRODUCTION_DRY_RUN_VERSION",
    "run_production_dry_run",
]
