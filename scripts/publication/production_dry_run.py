"""CLI for the AANA MI end-to-end production dry run."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.human_signoff import DEFAULT_HUMAN_SIGNOFF_PATH
from eval_pipeline.live_connector_readiness import DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH
from eval_pipeline.mi_release import DEFAULT_MI_RELEASE_REPORT
from eval_pipeline.mi_release_bundle import DEFAULT_MI_RELEASE_BUNDLE_DIR
from eval_pipeline.mi_release_candidate import DEFAULT_MI_BENCHMARK_DIR, DEFAULT_MI_RELEASE_CANDIDATE_REPORT
from eval_pipeline.production_deployment_manifest import DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH
from eval_pipeline.production_dry_run import DEFAULT_PRODUCTION_DRY_RUN_REPORT_PATH, run_production_dry_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the AANA MI production dry run without live external actions.")
    parser.add_argument("--output", default=str(DEFAULT_PRODUCTION_DRY_RUN_REPORT_PATH), help="Path to write production_dry_run_report.json.")
    parser.add_argument("--release-report", default=str(DEFAULT_MI_RELEASE_REPORT), help="Path to write/read the combined MI release report.")
    parser.add_argument("--rc-report", default=str(DEFAULT_MI_RELEASE_CANDIDATE_REPORT), help="Path to write the RC report.")
    parser.add_argument("--benchmark-dir", default=str(DEFAULT_MI_BENCHMARK_DIR), help="Directory for benchmark artifacts.")
    parser.add_argument("--bundle-dir", default=str(DEFAULT_MI_RELEASE_BUNDLE_DIR), help="Directory for release bundle artifacts.")
    parser.add_argument("--deployment-manifest", default=str(DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH), help="Path to write production_deployment_manifest.json.")
    parser.add_argument("--human-signoff", default=str(DEFAULT_HUMAN_SIGNOFF_PATH), help="Path to human_signoff.json.")
    parser.add_argument("--live-connector-plan", default=str(DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH), help="Path to live_connector_readiness_plan.json.")
    parser.add_argument("--json", action="store_true", help="Print the dry-run report JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run_production_dry_run(
            output_path=pathlib.Path(args.output),
            release_report_path=pathlib.Path(args.release_report),
            rc_report_path=pathlib.Path(args.rc_report),
            benchmark_dir=pathlib.Path(args.benchmark_dir),
            bundle_dir=pathlib.Path(args.bundle_dir),
            deployment_manifest_path=pathlib.Path(args.deployment_manifest),
            human_signoff_path=pathlib.Path(args.human_signoff),
            live_connector_plan_path=pathlib.Path(args.live_connector_plan),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Production dry run failed: {exc}", file=sys.stderr)
        return 1

    report = payload["report"]
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"{report['status']} -- stages={report['stage_count']} "
            f"blocking={report['blocking_stage_count']} unresolved={report['unresolved_item_count']} "
            f"live_actions={report['live_external_actions_attempted']} report={payload['path']}"
        )
        for stage in report["stages"]:
            print(f"- {stage['name']}: {stage['status']} ({stage['details']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
