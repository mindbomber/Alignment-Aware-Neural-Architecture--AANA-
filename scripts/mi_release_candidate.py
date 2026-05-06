"""CLI for the full AANA MI release-candidate run."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.mi_release_candidate import (
    DEFAULT_MI_BENCHMARK_DIR,
    DEFAULT_MI_RELEASE_CANDIDATE_REPORT,
    run_mi_release_candidate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the full AANA MI release-candidate check.")
    parser.add_argument("--output", default=str(DEFAULT_MI_RELEASE_CANDIDATE_REPORT), help="Path to write RC report JSON.")
    parser.add_argument("--benchmark-dir", default=str(DEFAULT_MI_BENCHMARK_DIR), help="Directory for benchmark artifacts.")
    parser.add_argument("--allow-direct-execution", action="store_true", help="Request direct execution if production readiness passes.")
    parser.add_argument("--json", action="store_true", help="Print the full RC report JSON.")
    parser.add_argument("--no-fail-on-block", action="store_true", help="Return 0 even when RC status is block.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run_mi_release_candidate(
            report_path=args.output,
            benchmark_dir=pathlib.Path(args.benchmark_dir),
            allow_direct_execution=args.allow_direct_execution,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"MI release candidate failed: {exc}", file=sys.stderr)
        return 1

    report = payload["report"]
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"{report['status']} -- checks={report['check_count']} "
            f"blocking={report['blocking_check_count']} report={payload['path']}"
        )
        for item in report.get("unresolved_items", []):
            print(f"- {item.get('check')}: {item.get('details')}")
    if report["status"] == "block" and not args.no_fail_on_block:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
