#!/usr/bin/env python
"""Validate cross-domain adapter-family external HF held-out coverage."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.cross_domain_adapter_family_validation import load_manifest, validate_cross_domain_adapter_family_validation
from eval_pipeline.hf_dataset_registry import load_registry


DEFAULT_MANIFEST = ROOT / "examples" / "cross_domain_adapter_family_validation.json"
DEFAULT_REGISTRY = ROOT / "examples" / "hf_dataset_validation_registry.json"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--require-existing-artifacts", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    registry = load_registry(args.registry)
    report = validate_cross_domain_adapter_family_validation(
        manifest,
        registry,
        root=ROOT,
        require_existing_artifacts=args.require_existing_artifacts,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(
            f"{status} -- families={report['family_count']} "
            f"passed={report['passed_family_count']}/{report['required_family_count']} "
            f"errors={report['errors']} warnings={report['warnings']} manifest={pathlib.Path(args.manifest).resolve()}"
        )
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

