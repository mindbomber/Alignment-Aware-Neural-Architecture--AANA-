"""CLI for the final AANA MI production go/no-go gate."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.human_signoff import DEFAULT_HUMAN_SIGNOFF_PATH
from eval_pipeline.mi_release_bundle_verification import DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH
from eval_pipeline.post_release_monitoring import DEFAULT_POST_RELEASE_MONITORING_POLICY_PATH
from eval_pipeline.production_deployment_manifest import DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH
from eval_pipeline.production_dry_run import DEFAULT_PRODUCTION_DRY_RUN_REPORT_PATH
from eval_pipeline.production_go_no_go import (
    DEFAULT_PRODUCTION_GO_NO_GO_REPORT_PATH,
    DEFAULT_RELEASE_MANIFEST_PATH,
    write_production_go_no_go_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the final AANA MI production go/no-go gate.")
    parser.add_argument("--output", default=str(DEFAULT_PRODUCTION_GO_NO_GO_REPORT_PATH), help="Path to write production_go_no_go_report.json.")
    parser.add_argument("--release-manifest", default=str(DEFAULT_RELEASE_MANIFEST_PATH), help="Path to release_manifest.json.")
    parser.add_argument("--bundle-verification", default=str(DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH), help="Path to release_bundle_verification.json.")
    parser.add_argument("--human-signoff", default=str(DEFAULT_HUMAN_SIGNOFF_PATH), help="Path to human_signoff.json.")
    parser.add_argument("--deployment-manifest", default=str(DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH), help="Path to production_deployment_manifest.json.")
    parser.add_argument("--monitoring-policy", default=str(DEFAULT_POST_RELEASE_MONITORING_POLICY_PATH), help="Path to post_release_monitoring_policy.json.")
    parser.add_argument("--dry-run-report", default=str(DEFAULT_PRODUCTION_DRY_RUN_REPORT_PATH), help="Path to production_dry_run_report.json.")
    parser.add_argument("--json", action="store_true", help="Print the go/no-go report JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = write_production_go_no_go_report(
            pathlib.Path(args.output),
            release_manifest_path=pathlib.Path(args.release_manifest),
            bundle_verification_path=pathlib.Path(args.bundle_verification),
            human_signoff_path=pathlib.Path(args.human_signoff),
            deployment_manifest_path=pathlib.Path(args.deployment_manifest),
            monitoring_policy_path=pathlib.Path(args.monitoring_policy),
            dry_run_report_path=pathlib.Path(args.dry_run_report),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Production go/no-go gate failed: {exc}", file=sys.stderr)
        return 1

    report = payload["report"]
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"{report['status']} -- blockers={report['blocker_count']} "
            f"signoff={report['summary']['human_signoff_decision']} "
            f"deployment={report['summary']['deployment_status']} "
            f"dry_run={report['summary']['dry_run_status']} "
            f"output={payload['path']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
