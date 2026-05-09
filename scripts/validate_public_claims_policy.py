#!/usr/bin/env python
"""Validate AANA public-claims policy boundaries."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.benchmark_reporting import load_manifest, validate_benchmark_reporting_manifest


DEFAULT_MANIFEST = ROOT / "examples" / "benchmark_reporting_manifest.json"
REQUIRED_POLICY_DOC = ROOT / "docs" / "public-claims-policy.md"
REQUIRED_CLAIM = "AANA makes agents more auditable, safer, more grounded, and more controllable."
FORBIDDEN_RAW_ENGINE_CLAIM = "raw agent-performance engine"


def validate_public_claims_policy(manifest_path: str | pathlib.Path = DEFAULT_MANIFEST) -> dict:
    manifest_path = pathlib.Path(manifest_path)
    manifest = load_manifest(manifest_path)
    reporting = validate_benchmark_reporting_manifest(manifest)
    issues = list(reporting.get("issues", []))

    if not REQUIRED_POLICY_DOC.exists():
        issues.append({"level": "error", "path": str(REQUIRED_POLICY_DOC), "message": "Public claims policy doc is missing."})
        policy_text = ""
    else:
        policy_text = REQUIRED_POLICY_DOC.read_text(encoding="utf-8")
    if REQUIRED_CLAIM not in policy_text:
        issues.append({"level": "error", "path": str(REQUIRED_POLICY_DOC), "message": "Public claims policy must include the standard AANA claim."})
    prohibited_context = "Do not claim" in policy_text or "must not be described" in policy_text
    if FORBIDDEN_RAW_ENGINE_CLAIM in policy_text and not prohibited_context:
        issues.append({"level": "error", "path": str(REQUIRED_POLICY_DOC), "message": "Raw agent-performance wording must only appear as a prohibited claim boundary."})

    errors = sum(1 for issue in issues if issue.get("level") == "error")
    warnings = sum(1 for issue in issues if issue.get("level") == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "manifest": str(manifest_path),
        "policy_doc": str(REQUIRED_POLICY_DOC),
        "report_count": reporting.get("report_count", 0),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Benchmark/public-claims reporting manifest.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    args = parser.parse_args(argv)

    try:
        report = validate_public_claims_policy(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"public claims policy validation failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(f"{status} -- reports={report['report_count']} errors={report['errors']} warnings={report['warnings']}")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
