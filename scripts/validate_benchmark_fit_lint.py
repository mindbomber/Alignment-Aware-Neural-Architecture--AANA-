#!/usr/bin/env python
"""Validate that general AANA paths do not contain known benchmark answers."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.benchmark_fit_lint import load_manifest, validate_benchmark_fit_manifest


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "examples" / "benchmark_fit_lint_manifest.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fail when known benchmark-answer literals appear in general AANA paths.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Path to benchmark-fit lint manifest.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest_path = pathlib.Path(args.manifest)
        manifest = load_manifest(manifest_path)
        report = validate_benchmark_fit_manifest(manifest, root=ROOT)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"benchmark-fit lint failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(
            f"{status} -- scanned={report['scanned_file_count']} findings={report['finding_count']} "
            f"errors={report['errors']} warnings={report['warnings']} manifest={manifest_path}"
        )
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
