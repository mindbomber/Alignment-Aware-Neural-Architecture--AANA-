#!/usr/bin/env python
"""Validate held-out evidence for AANA adapter improvements."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.adapter_heldout_validation import load_manifest, validate_adapter_heldout_manifest

DEFAULT_MANIFEST = ROOT / "examples" / "adapter_heldout_validation.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Require held-out validation after every AANA adapter improvement.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Path to adapter held-out validation manifest.")
    parser.add_argument("--require-existing-artifacts", action="store_true", help="Require referenced task/result artifacts to exist locally.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest_path = pathlib.Path(args.manifest)
        manifest = load_manifest(manifest_path)
        report = validate_adapter_heldout_manifest(
            manifest,
            root=ROOT,
            require_existing_artifacts=args.require_existing_artifacts,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"adapter held-out validation failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(f"{status} -- records={report['record_count']} errors={report['errors']} warnings={report['warnings']} manifest={manifest_path}")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
