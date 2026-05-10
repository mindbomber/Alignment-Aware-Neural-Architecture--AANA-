#!/usr/bin/env python
"""Validate reviewed evidence artifact labels and claim eligibility."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.evidence_artifact_policy import DEFAULT_MANIFEST, load_manifest, validate_evidence_artifact_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(ROOT / DEFAULT_MANIFEST), help="Evidence artifact manifest path.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    parser.add_argument(
        "--no-require-existing-artifacts",
        action="store_true",
        help="Validate schema only without requiring tracked artifact coverage.",
    )
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
        report = validate_evidence_artifact_manifest(
            manifest,
            root=ROOT,
            require_existing_artifacts=not args.no_require_existing_artifacts,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"evidence artifact validation failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(
            f"{status} -- entries={report['artifact_entries']} "
            f"covered_files={report['covered_files']}/{report['tracked_files']} "
            f"errors={report['errors']} warnings={report['warnings']}"
        )
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
