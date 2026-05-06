"""CLI for the machine-checkable production MI release readiness report."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from eval_pipeline.release_readiness_report import (
    DEFAULT_RELEASE_ARTIFACT_PATHS,
    DEFAULT_RELEASE_REPORT_PATH,
    write_release_readiness_report,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_READINESS = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "production_mi_readiness.json"
DEFAULT_CHECKLIST = ROOT / "docs" / "production-mi-release-checklist.md"


def _load_json(path: str | pathlib.Path) -> dict:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write a machine-checkable production MI release readiness report.")
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS), help="Path to production_mi_readiness.json.")
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST), help="Path to production-mi-release-checklist.md.")
    parser.add_argument("--output", default=str(DEFAULT_RELEASE_REPORT_PATH), help="Path to write the release report JSON.")
    parser.add_argument("--audit-jsonl", default=str(DEFAULT_RELEASE_ARTIFACT_PATHS["audit_jsonl"]), help="Path to MI audit JSONL.")
    parser.add_argument("--pilot-result", default=str(DEFAULT_RELEASE_ARTIFACT_PATHS["pilot_result"]), help="Path to pilot result JSON.")
    parser.add_argument("--dashboard", default=str(DEFAULT_RELEASE_ARTIFACT_PATHS["dashboard"]), help="Path to dashboard JSON.")
    parser.add_argument(
        "--human-review-queue",
        default=str(DEFAULT_RELEASE_ARTIFACT_PATHS["human_review_queue"]),
        help="Path to human-review queue JSONL.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full report JSON.")
    parser.add_argument("--no-fail-on-block", action="store_true", help="Return 0 even when report status is block.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        readiness = _load_json(args.readiness)
        payload = write_release_readiness_report(
            args.output,
            readiness=readiness,
            checklist_path=args.checklist,
            artifact_paths={
                "audit_jsonl": args.audit_jsonl,
                "pilot_result": args.pilot_result,
                "dashboard": args.dashboard,
                "human_review_queue": args.human_review_queue,
            },
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"release readiness report failed: {exc}", file=sys.stderr)
        return 1

    report = payload["report"]
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"{report['status']} -- release_status={report.get('release_status')} "
            f"unresolved={report.get('counts', {}).get('unresolved_count', 0)} "
            f"report={payload['path']}"
        )
        for item in report.get("unresolved_items", []):
            print(f"- {item.get('category')}::{item.get('id')}: {item.get('details')}")
    if report["status"] == "block" and not args.no_fail_on_block:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
