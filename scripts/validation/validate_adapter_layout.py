#!/usr/bin/env python
"""Validate the AANA adapter-family and product-bundle layout."""

from __future__ import annotations

import argparse
import json

from aana.adapter_layout import validate_adapter_layout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    args = parser.parse_args(argv)
    report = validate_adapter_layout()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(f"{status} -- adapter_families={len(report['adapter_families'])} bundles={len(report['bundles'])}")
        for issue in report["issues"]:
            print(f"- {issue['code']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
