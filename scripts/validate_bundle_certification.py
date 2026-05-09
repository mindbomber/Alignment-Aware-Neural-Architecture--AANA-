#!/usr/bin/env python
"""Validate all AANA product bundle certification gates."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import bundle_certification


def validate_all_bundles() -> dict:
    reports = [
        bundle_certification.certify_bundle_report(bundle_id)
        for bundle_id in bundle_certification.certification_targets()
    ]
    failures = [report for report in reports if not report.get("valid")]
    return {
        "valid": not failures,
        "bundle_count": len(reports),
        "passed": len(reports) - len(failures),
        "failed": len(failures),
        "required_bundles": list(bundle_certification.certification_targets()),
        "reports": reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    args = parser.parse_args(argv)

    report = validate_all_bundles()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(f"{status} -- bundles={report['passed']}/{report['bundle_count']}")
        for item in report["reports"]:
            summary = item.get("summary", {})
            item_status = "pass" if item.get("valid") else "block"
            print(
                f"- {item_status}: {item.get('bundle_id')} "
                f"{summary.get('score_percent')}/100 {summary.get('readiness_level')}"
            )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
