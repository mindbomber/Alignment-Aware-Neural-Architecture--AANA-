#!/usr/bin/env python
"""Validate split-safe HF calibration plans for AANA adapter families."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.hf_calibration import load_plan, load_registry, validate_hf_calibration_plan


DEFAULT_PLAN = ROOT / "examples" / "hf_calibration_plan.json"
DEFAULT_REGISTRY = ROOT / "examples" / "hf_dataset_validation_registry.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="Path to HF calibration plan.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Path to HF dataset registry.")
    parser.add_argument("--json", action="store_true", help="Print the full validation report as JSON.")
    args = parser.parse_args(argv)

    try:
        plan_path = pathlib.Path(args.plan)
        plan = load_plan(plan_path)
        registry = load_registry(args.registry)
        report = validate_hf_calibration_plan(plan, registry)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"HF calibration validation failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(
            f"{status} -- families={report['family_count']}/{report['required_family_count']} "
            f"measured={report['measured_family_count']} errors={report['errors']} "
            f"warnings={report['warnings']} plan={plan_path.resolve()}"
        )
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
