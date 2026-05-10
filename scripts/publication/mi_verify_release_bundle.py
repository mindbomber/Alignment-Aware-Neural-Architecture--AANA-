"""CLI for verifying an AANA MI release evidence bundle."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.mi_release_bundle import DEFAULT_MI_RELEASE_BUNDLE_DIR
from eval_pipeline.mi_release_bundle_verification import (
    DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH,
    verify_mi_release_bundle,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify an AANA MI release bundle manifest.")
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MI_RELEASE_BUNDLE_DIR / "release_manifest.json"),
        help="Path to release_manifest.json.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_RELEASE_BUNDLE_VERIFICATION_PATH),
        help="Path to write release_bundle_verification.json.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full verification JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        verification = verify_mi_release_bundle(pathlib.Path(args.manifest), output_path=pathlib.Path(args.output))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"MI release bundle verification failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(verification, indent=2, sort_keys=True))
    else:
        print(
            f"{verification['status']} -- artifacts={verification['artifact_count']} "
            f"issues={verification['issue_count']} output={args.output}"
        )
        for issue in verification.get("issues", []):
            print(f"- {issue.get('code')}: {issue.get('message')}")
    return 0 if verification["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
