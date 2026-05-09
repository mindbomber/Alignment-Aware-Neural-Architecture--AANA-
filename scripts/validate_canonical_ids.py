#!/usr/bin/env python
"""Validate canonical IDs and backward-compatible alias maps."""

from __future__ import annotations

import argparse
import json

from aana.canonical_ids import validate_canonical_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    args = parser.parse_args(argv)

    report = validate_canonical_ids()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(
            f"{status} -- "
            f"adapter_families={len(report['canonical_ids']['adapter_families'])} "
            f"bundles={len(report['canonical_ids']['bundles'])} "
            f"routes={len(report['canonical_ids']['action_routes'])} "
            f"tool_evidence_types={len(report['canonical_ids']['tool_evidence_types'])} "
            f"runtime_modes={len(report['canonical_ids']['runtime_modes'])}"
        )
        for issue in report["issues"]:
            print(f"- {issue['code']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
