#!/usr/bin/env python
"""Validate the Hugging Face dataset registry for AANA adapter validation."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.hf_dataset_registry import load_registry, validate_hf_dataset_registry


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "examples" / "hf_dataset_validation_registry.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate HF dataset split usage for AANA calibration, held-out validation, and external reporting.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Path to HF dataset validation registry.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        registry_path = pathlib.Path(args.registry)
        registry = load_registry(registry_path)
        report = validate_hf_dataset_registry(registry)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"HF dataset registry validation failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        counts = report["split_use_counts"]
        status = "pass" if report["valid"] else "block"
        print(
            f"{status} -- datasets={report['dataset_count']} calibration={counts['calibration']} "
            f"heldout={counts['heldout_validation']} external={counts['external_reporting']} "
            f"errors={report['errors']} warnings={report['warnings']} registry={registry_path}"
        )
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
