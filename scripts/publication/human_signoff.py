"""CLI for writing an AANA MI human signoff record."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.human_signoff import (
    DEFAULT_HUMAN_SIGNOFF_PATH,
    DEFAULT_RELEASE_MANIFEST_PATH,
    DEFAULT_RELEASE_VERIFICATION_PATH,
    SIGNOFF_DECISIONS,
    write_human_signoff_record,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write a structured AANA MI human signoff record.")
    parser.add_argument("--output", default=str(DEFAULT_HUMAN_SIGNOFF_PATH), help="Path to write human_signoff.json.")
    parser.add_argument("--reviewer-id", default="pending-domain-owner", help="Reviewer identifier.")
    parser.add_argument("--reviewer-name", default="Pending domain owner", help="Reviewer display name.")
    parser.add_argument("--reviewer-role", default="domain_owner", help="Reviewer role.")
    parser.add_argument("--decision", default="pending", choices=SIGNOFF_DECISIONS, help="Human signoff decision.")
    parser.add_argument("--manifest", default=str(DEFAULT_RELEASE_MANIFEST_PATH), help="Path to release_manifest.json.")
    parser.add_argument("--verification", default=str(DEFAULT_RELEASE_VERIFICATION_PATH), help="Path to release_bundle_verification.json.")
    parser.add_argument("--notes", default="Human/domain-owner approval has not been granted yet.", help="Signoff notes.")
    parser.add_argument("--json", action="store_true", help="Print the signoff record JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = write_human_signoff_record(
            pathlib.Path(args.output),
            reviewer={"id": args.reviewer_id, "name": args.reviewer_name, "role": args.reviewer_role},
            decision=args.decision,
            release_manifest_path=pathlib.Path(args.manifest),
            verification_path=pathlib.Path(args.verification),
            notes=args.notes,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Human signoff failed: {exc}", file=sys.stderr)
        return 1

    record = payload["record"]
    if args.json:
        print(json.dumps(record, indent=2, sort_keys=True))
    else:
        print(
            f"{record['decision']} -- reviewer={record['reviewer']['id']} "
            f"bundle_hash={record['evidence_bundle']['release_manifest_sha256']} "
            f"output={payload['path']}"
        )
    return 0 if payload["validation"]["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
