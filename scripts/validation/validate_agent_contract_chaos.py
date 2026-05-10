#!/usr/bin/env python
"""Run AANA Agent Action Contract and FastAPI chaos validation."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.agent_contract_chaos import validate_agent_contract_chaos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    parser.add_argument("--output", default=None, help="Optional JSON report path.")
    args = parser.parse_args(argv)

    report = validate_agent_contract_chaos(write_report_path=args.output)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "pass" if report["valid"] else "block"
        print(f"{status} -- cases={report['case_count']} audit_records={report['audit_record_count']} errors={report['errors']}")
        for result in report["case_results"]:
            print(
                f"- {result['id']}: sdk={result['python_sdk_route']} "
                f"fastapi={result['fastapi_status']}/{result['fastapi_route'] or result['fastapi_error']}"
            )
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['case']} [{issue['surface']}]: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
