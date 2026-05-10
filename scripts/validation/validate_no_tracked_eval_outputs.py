#!/usr/bin/env python
"""Fail if generated eval_outputs files are tracked by Git."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]


def tracked_eval_outputs(root: pathlib.Path = ROOT) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "eval_outputs"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def validate_no_tracked_eval_outputs(root: pathlib.Path = ROOT) -> dict[str, Any]:
    tracked = tracked_eval_outputs(root)
    return {
        "valid": not tracked,
        "tracked_eval_outputs_count": len(tracked),
        "tracked_eval_outputs": tracked,
        "message": (
            "eval_outputs/ is generated and gitignored. Move intentional evidence snapshots "
            "to docs/evidence/peer_review/ or another reviewed artifact directory before committing."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    args = parser.parse_args(argv)

    report = validate_no_tracked_eval_outputs()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(f"{status} -- tracked_eval_outputs={report['tracked_eval_outputs_count']}")
        for path in report["tracked_eval_outputs"][:50]:
            print(f"- {path}")
        if len(report["tracked_eval_outputs"]) > 50:
            print(f"- ... {len(report['tracked_eval_outputs']) - 50} more")
        if not report["valid"]:
            print(report["message"])
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
