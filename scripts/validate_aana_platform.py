#!/usr/bin/env python
"""Compatibility wrapper for the AANA platform validator."""

from __future__ import annotations

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aana import validate_platform as _impl

PlatformGate = _impl.PlatformGate
platform_gates = _impl.platform_gates
run_gate = _impl.run_gate
subprocess = _impl.subprocess


def validate_platform(
    *,
    require_existing_artifacts: bool = True,
    include_agent_integrations: bool = True,
    fail_fast: bool = False,
    timeout: int = 240,
) -> dict[str, _impl.Any]:
    checks = []
    for gate in platform_gates(
        require_existing_artifacts=require_existing_artifacts,
        include_agent_integrations=include_agent_integrations,
    ):
        result = run_gate(gate, timeout=timeout)
        checks.append(result)
        if fail_fast and not result["valid"]:
            break
    return {
        "valid": all(check["valid"] for check in checks),
        "passed": sum(1 for check in checks if check["valid"]),
        "total": len(checks),
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _impl.argparse.ArgumentParser(description=_impl.__doc__)
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed gate.")
    parser.add_argument("--timeout", type=int, default=240, help="Per-gate timeout in seconds.")
    parser.add_argument(
        "--no-require-existing-artifacts",
        action="store_true",
        help="Do not pass --require-existing-artifacts to gates that support it.",
    )
    parser.add_argument(
        "--skip-agent-integrations",
        action="store_true",
        help="Skip the slower live integration smoke gate.",
    )
    args = parser.parse_args(argv)

    report = validate_platform(
        require_existing_artifacts=not args.no_require_existing_artifacts,
        include_agent_integrations=not args.skip_agent_integrations,
        fail_fast=args.fail_fast,
        timeout=args.timeout,
    )
    if args.json:
        print(_impl.json.dumps(report, indent=2, sort_keys=True))
    else:
        _impl._print_text_summary(report)
    return 0 if report["valid"] else 1


__all__ = ["PlatformGate", "main", "platform_gates", "run_gate", "validate_platform", "subprocess"]


if __name__ == "__main__":
    raise SystemExit(main())
