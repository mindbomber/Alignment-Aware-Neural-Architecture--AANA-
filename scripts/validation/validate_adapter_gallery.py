#!/usr/bin/env python
"""Validate the checked-in AANA adapter gallery."""

from __future__ import annotations

import argparse
import json
import sys

from eval_pipeline.adapter_gallery_validation import load_gallery, validate_gallery


def parse_args():
    parser = argparse.ArgumentParser(description="Validate the AANA adapter gallery.")
    parser.add_argument("--gallery", default="examples/adapter_gallery.json", help="Path to adapter gallery JSON.")
    parser.add_argument("--run-examples", action="store_true", help="Run executable examples and compare expected gate behavior.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main():
    args = parse_args()
    gallery = load_gallery(args.gallery)
    report = validate_gallery(gallery, run_examples=args.run_examples)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"Adapter gallery is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
        if report["checked_examples"]:
            print("Checked examples:")
            for item in report["checked_examples"]:
                print(f"- {item['id']}: gate={item['gate_decision']} action={item['recommended_action']} aix={item.get('aix_decision')}")
        completeness = report.get("catalog_completeness", {})
        if completeness:
            print(
                f"Catalog completeness: {completeness.get('score')} "
                f"(weak entries: {completeness.get('weak_entry_count')})"
            )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Adapter gallery validation failed: {exc}", file=sys.stderr)
        sys.exit(2)
