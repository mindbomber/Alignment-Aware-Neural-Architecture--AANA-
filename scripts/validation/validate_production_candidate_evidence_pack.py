#!/usr/bin/env python
"""Validate the AANA production-candidate evidence pack."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.production_candidate_evidence_pack import load_manifest, validate_production_candidate_evidence_pack


DEFAULT_MANIFEST = ROOT / "examples" / "production_candidate_evidence_pack.json"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--require-existing-artifacts", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    report = validate_production_candidate_evidence_pack(
        manifest,
        root=ROOT,
        require_existing_artifacts=args.require_existing_artifacts,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(
            f"{status} -- sections={report['required_section_count']} "
            f"artifacts={report['required_artifact_count']} "
            f"errors={report['errors']} warnings={report['warnings']} manifest={pathlib.Path(args.manifest).resolve()}"
        )
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
