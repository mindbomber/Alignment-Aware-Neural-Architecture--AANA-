#!/usr/bin/env python
"""Validate benchmark reporting language and public-claim boundaries."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.benchmark_reporting import load_manifest, validate_benchmark_reporting_manifest


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "examples" / "benchmark_reporting_manifest.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate that diagnostic probe results are never merged into public AANA claims.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Path to benchmark reporting manifest.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest_path = pathlib.Path(args.manifest)
        manifest = load_manifest(manifest_path)
        report = validate_benchmark_reporting_manifest(manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"benchmark reporting validation failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(f"{status} -- reports={report['report_count']} errors={report['errors']} warnings={report['warnings']} manifest={manifest_path}")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
