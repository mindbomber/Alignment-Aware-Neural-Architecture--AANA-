"""CLI for writing an AANA MI production deployment manifest."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.human_signoff import DEFAULT_HUMAN_SIGNOFF_PATH
from eval_pipeline.live_connector_readiness import DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH
from eval_pipeline.mi_release_bundle_verification import DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH
from eval_pipeline.production_deployment_manifest import (
    DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH,
    DEFAULT_RELEASE_MANIFEST_PATH,
    write_production_deployment_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write the production deployment manifest for a verified AANA MI bundle.")
    parser.add_argument("--output", default=str(DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH), help="Path to write production_deployment_manifest.json.")
    parser.add_argument("--manifest", default=str(DEFAULT_RELEASE_MANIFEST_PATH), help="Path to release_manifest.json.")
    parser.add_argument("--verification", default=str(DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH), help="Path to release_bundle_verification.json.")
    parser.add_argument("--human-signoff", default=str(DEFAULT_HUMAN_SIGNOFF_PATH), help="Path to human_signoff.json.")
    parser.add_argument("--live-connector-plan", default=str(DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH), help="Path to live_connector_readiness_plan.json.")
    parser.add_argument("--rollback-owner-id", default="pending-release-owner", help="Rollback owner identifier.")
    parser.add_argument("--rollback-owner-name", default="Pending release owner", help="Rollback owner display name.")
    parser.add_argument("--rollback-owner-role", default="release_manager", help="Rollback owner role.")
    parser.add_argument("--json", action="store_true", help="Print the deployment manifest JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = write_production_deployment_manifest(
            pathlib.Path(args.output),
            release_manifest_path=pathlib.Path(args.manifest),
            verification_path=pathlib.Path(args.verification),
            human_signoff_path=pathlib.Path(args.human_signoff),
            live_connector_plan_path=pathlib.Path(args.live_connector_plan),
            rollback_owner={
                "id": args.rollback_owner_id,
                "name": args.rollback_owner_name,
                "role": args.rollback_owner_role,
            },
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Production deployment manifest failed: {exc}", file=sys.stderr)
        return 1

    manifest = payload["manifest"]
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(
            f"{manifest['deployment_status']} -- "
            f"verification={manifest['verified_mi_release_bundle']['verification_status']} "
            f"blockers={len(manifest['blockers'])} "
            f"output={payload['path']}"
        )
    return 0 if payload["validation"]["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
