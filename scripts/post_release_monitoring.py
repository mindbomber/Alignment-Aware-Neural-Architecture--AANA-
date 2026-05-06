"""CLI for writing the AANA MI post-release monitoring policy."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.post_release_monitoring import (
    DEFAULT_POST_RELEASE_MONITORING_POLICY_PATH,
    write_post_release_monitoring_policy,
)
from eval_pipeline.production_deployment_manifest import DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write the AANA MI post-release monitoring and alert policy.")
    parser.add_argument("--output", default=str(DEFAULT_POST_RELEASE_MONITORING_POLICY_PATH), help="Path to write post_release_monitoring_policy.json.")
    parser.add_argument("--deployment-manifest", default=str(DEFAULT_PRODUCTION_DEPLOYMENT_MANIFEST_PATH), help="Path to production_deployment_manifest.json.")
    parser.add_argument("--json", action="store_true", help="Print the monitoring policy JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = write_post_release_monitoring_policy(
            pathlib.Path(args.output),
            deployment_manifest_path=pathlib.Path(args.deployment_manifest),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Post-release monitoring policy failed: {exc}", file=sys.stderr)
        return 1

    policy = payload["policy"]
    if args.json:
        print(json.dumps(policy, indent=2, sort_keys=True))
    else:
        print(
            f"{'pass' if payload['validation']['valid'] else 'block'} -- "
            f"metrics={len(policy['metrics'])} alerts={len(policy['alerts'])} "
            f"deployment={policy['release_context']['deployment_status']} "
            f"output={payload['path']}"
        )
    return 0 if payload["validation"]["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
