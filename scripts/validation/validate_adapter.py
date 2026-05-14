#!/usr/bin/env python
"""Validate an AANA domain adapter JSON file."""

from __future__ import annotations

import argparse
import json
import sys

from eval_pipeline.adapter_validation import load_adapter, validate_adapter


def parse_args():
    parser = argparse.ArgumentParser(description="Validate an AANA domain adapter JSON file.")
    parser.add_argument("--adapter", required=True, help="Path to adapter JSON.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main():
    args = parse_args()
    adapter = load_adapter(args.adapter)
    report = validate_adapter(adapter)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"Adapter is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
        print("Next steps:")
        for step in report["next_steps"]:
            print(f"- {step}")

    return 0 if report["valid"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Adapter validation failed: {exc}", file=sys.stderr)
        sys.exit(2)
