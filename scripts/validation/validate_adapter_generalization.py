#!/usr/bin/env python
"""Validate adapter generalization governance gates."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.adapter_generalization_gate import load_manifest, validate_adapter_generalization_gate

DEFAULT_MANIFEST = ROOT / "examples" / "adapter_generalization_manifest.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--require-existing-artifacts", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        report = validate_adapter_generalization_gate(
            manifest,
            root=ROOT,
            require_existing_artifacts=args.require_existing_artifacts,
        )
    except Exception as exc:
        print(f"adapter generalization validation failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(f"{status} -- errors={report['errors']} warnings={report['warnings']} manifest={args.manifest}")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
