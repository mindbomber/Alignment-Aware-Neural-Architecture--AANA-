"""CLI for creating the AANA MI release evidence bundle."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.mi_release_bundle import DEFAULT_MI_RELEASE_BUNDLE_DIR, create_mi_release_bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create the AANA MI release candidate evidence bundle.")
    parser.add_argument("--output-dir", default=str(DEFAULT_MI_RELEASE_BUNDLE_DIR), help="Bundle output directory.")
    parser.add_argument("--json", action="store_true", help="Print the release manifest JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = create_mi_release_bundle(pathlib.Path(args.output_dir))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"MI release bundle failed: {exc}", file=sys.stderr)
        return 1

    manifest = payload["manifest"]
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(
            f"{manifest['rc_status']} -- readiness={manifest['readiness_status']} "
            f"global_aix={manifest.get('global_aix', {}).get('score')} "
            f"unresolved={manifest['unresolved_blocker_count']} "
            f"bundle={payload['paths']['bundle_dir']}"
        )
    return 0 if manifest["rc_status"] == "pass" and manifest["readiness_status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
