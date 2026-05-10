"""CI-safe AANA MI release command."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.mi_release import DEFAULT_MI_RELEASE_REPORT, run_mi_release
from eval_pipeline.mi_release_bundle import DEFAULT_MI_RELEASE_BUNDLE_DIR
from eval_pipeline.mi_release_candidate import DEFAULT_MI_BENCHMARK_DIR, DEFAULT_MI_RELEASE_CANDIDATE_REPORT


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the full CI-safe AANA MI release flow.")
    parser.add_argument("--output", default=str(DEFAULT_MI_RELEASE_REPORT), help="Path to write the combined MI release report.")
    parser.add_argument("--rc-report", default=str(DEFAULT_MI_RELEASE_CANDIDATE_REPORT), help="Path to write the RC report.")
    parser.add_argument("--benchmark-dir", default=str(DEFAULT_MI_BENCHMARK_DIR), help="Directory for benchmark artifacts.")
    parser.add_argument("--bundle-dir", default=str(DEFAULT_MI_RELEASE_BUNDLE_DIR), help="Directory for release bundle artifacts.")
    parser.add_argument("--allow-direct-execution", action="store_true", help="Request direct execution if production readiness passes.")
    parser.add_argument("--json", action="store_true", help="Print the combined release report JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run_mi_release(
            output_path=pathlib.Path(args.output),
            rc_report_path=pathlib.Path(args.rc_report),
            benchmark_dir=pathlib.Path(args.benchmark_dir),
            bundle_dir=pathlib.Path(args.bundle_dir),
            allow_direct_execution=args.allow_direct_execution,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"MI release failed: {exc}", file=sys.stderr)
        return 1

    report = payload["report"]
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"{report['status']} -- stages={report['stage_count']} "
            f"blocking={report['blocking_stage_count']} skipped={report['skipped_stage_count']} "
            f"report={payload['path']}"
        )
        for stage in report["stages"]:
            print(f"- {stage['name']}: {stage['status']} ({stage['details']})")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
