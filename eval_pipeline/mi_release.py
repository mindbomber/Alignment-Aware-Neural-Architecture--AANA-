"""CI-safe one-command AANA MI release orchestration."""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from eval_pipeline.mi_release_bundle import DEFAULT_ARTIFACTS, DEFAULT_MI_RELEASE_BUNDLE_DIR, create_mi_release_bundle
from eval_pipeline.mi_release_bundle_verification import verify_mi_release_bundle
from eval_pipeline.mi_release_candidate import (
    DEFAULT_MI_BENCHMARK_DIR,
    DEFAULT_MI_RELEASE_CANDIDATE_REPORT,
    run_mi_release_candidate,
)


MI_RELEASE_COMMAND_VERSION = "0.1"
DEFAULT_MI_RELEASE_REPORT = DEFAULT_MI_RELEASE_BUNDLE_DIR / "aana_mi_release_report.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stage(name: str, status: str, details: str, *, artifacts: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "details": details,
        "artifacts": artifacts or {},
    }


def run_mi_release(
    *,
    output_path: str | pathlib.Path = DEFAULT_MI_RELEASE_REPORT,
    rc_report_path: str | pathlib.Path = DEFAULT_MI_RELEASE_CANDIDATE_REPORT,
    benchmark_dir: str | pathlib.Path = DEFAULT_MI_BENCHMARK_DIR,
    bundle_dir: str | pathlib.Path = DEFAULT_MI_RELEASE_BUNDLE_DIR,
    allow_direct_execution: bool = False,
) -> dict[str, Any]:
    """Run release candidate, bundle generation, and bundle verification."""

    stages = []
    rc_payload = run_mi_release_candidate(
        report_path=rc_report_path,
        benchmark_dir=benchmark_dir,
        allow_direct_execution=allow_direct_execution,
    )
    rc_report = rc_payload["report"]
    stages.append(
        _stage(
            "release_candidate",
            rc_report["status"],
            f"checks={rc_report['check_count']} blocking={rc_report['blocking_check_count']}",
            artifacts={"release_candidate_report": rc_payload["path"]},
        )
    )

    bundle_payload: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    if rc_report["status"] == "pass":
        rc_artifacts = rc_report.get("artifacts", {})
        bundle_artifact_paths = {key: pathlib.Path(value) for key, value in DEFAULT_ARTIFACTS.items()}
        bundle_artifact_paths.update(
            {
                "release_candidate_report": pathlib.Path(rc_payload["path"]),
                "readiness_report": pathlib.Path(rc_artifacts["release_readiness_report"]),
                "production_readiness": pathlib.Path(rc_artifacts["readiness"]),
                "audit_jsonl": pathlib.Path(rc_artifacts["audit_jsonl"]),
                "audit_manifest": pathlib.Path(rc_artifacts["audit_manifest"]),
                "dashboard": pathlib.Path(rc_artifacts["dashboard"]),
                "benchmark_report": pathlib.Path(rc_artifacts["benchmark_report"]),
                "pilot_handoffs": pathlib.Path(rc_artifacts["pilot_handoffs"]),
            }
        )
        bundle_payload = create_mi_release_bundle(bundle_dir, artifact_paths=bundle_artifact_paths)
        manifest = bundle_payload["manifest"]
        bundle_status = "pass" if manifest.get("rc_status") == "pass" and manifest.get("readiness_status") == "ready" else "block"
        stages.append(
            _stage(
                "release_bundle",
                bundle_status,
                (
                    f"rc_status={manifest.get('rc_status')} readiness={manifest.get('readiness_status')} "
                    f"global_aix={manifest.get('global_aix', {}).get('score')} "
                    f"unresolved={manifest.get('unresolved_blocker_count')}"
                ),
                artifacts=bundle_payload["paths"],
            )
        )
        verification_output = pathlib.Path(bundle_payload["paths"]["bundle_dir"]) / "release_bundle_verification.json"
        verification = verify_mi_release_bundle(bundle_payload["paths"]["release_manifest"], output_path=verification_output)
        stages.append(
            _stage(
                "release_bundle_verification",
                verification["status"],
                f"artifacts={verification['artifact_count']} issues={verification['issue_count']}",
                artifacts={"release_bundle_verification": str(verification_output)},
            )
        )
    else:
        stages.append(
            _stage(
                "release_bundle",
                "skipped",
                "Skipped because release candidate did not pass.",
            )
        )
        stages.append(
            _stage(
                "release_bundle_verification",
                "skipped",
                "Skipped because release bundle was not generated.",
            )
        )

    blocking = [stage for stage in stages if stage["status"] == "block"]
    skipped = [stage for stage in stages if stage["status"] == "skipped"]
    report = {
        "mi_release_command_version": MI_RELEASE_COMMAND_VERSION,
        "created_at": _utc_now(),
        "status": "pass" if not blocking and not skipped else "block",
        "allow_direct_execution": bool(allow_direct_execution),
        "stage_count": len(stages),
        "blocking_stage_count": len(blocking),
        "skipped_stage_count": len(skipped),
        "stages": stages,
        "release_candidate": {
            "status": rc_report.get("status"),
            "blocking_check_count": rc_report.get("blocking_check_count"),
            "unresolved_items": rc_report.get("unresolved_items", []),
        },
        "release_bundle": bundle_payload["manifest"] if bundle_payload else None,
        "release_bundle_verification": verification,
    }
    output = pathlib.Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report": report, "path": str(output), "bytes": output.stat().st_size}


__all__ = [
    "DEFAULT_MI_RELEASE_REPORT",
    "MI_RELEASE_COMMAND_VERSION",
    "run_mi_release",
]
