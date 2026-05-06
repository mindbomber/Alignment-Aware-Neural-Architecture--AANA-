"""CLI for writing the AANA MI live connector readiness plan."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.live_connector_readiness import (
    DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH,
    write_live_connector_readiness_plan,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write the local-RC live connector readiness plan.")
    parser.add_argument("--output", default=str(DEFAULT_LIVE_CONNECTOR_READINESS_PLAN_PATH), help="Path to write live_connector_readiness_plan.json.")
    parser.add_argument("--json", action="store_true", help="Print the readiness plan JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = write_live_connector_readiness_plan(pathlib.Path(args.output))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Live connector readiness plan failed: {exc}", file=sys.stderr)
        return 1

    plan = payload["plan"]
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        summary = plan["summary"]
        print(
            f"{'pass' if payload['validation']['valid'] else 'block'} -- "
            f"connectors={summary['connector_count']} "
            f"out_of_scope={summary['out_of_scope_count']} "
            f"live_enabled={summary['live_execution_enabled_count']} "
            f"output={payload['path']}"
        )
    return 0 if payload["validation"]["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
