#!/usr/bin/env python
"""Fail when verifier report functions are defined outside verifier modules."""

import argparse
import ast
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SCAN_ROOTS = ("eval_pipeline", "scripts")
VERIFIER_MODULE_ROOT = ROOT / "eval_pipeline" / "adapter_runner" / "verifier_modules"


def is_relative_to(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def python_files(scan_roots):
    for scan_root in scan_roots:
        root = (ROOT / scan_root).resolve()
        if root.is_file() and root.suffix == ".py":
            yield root
            continue
        for path in root.rglob("*.py"):
            yield path.resolve()


def tool_report_definitions(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [
            {
                "path": path,
                "line": exc.lineno or 1,
                "name": "<syntax-error>",
                "error": str(exc),
            }
        ]

    definitions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.endswith("_tool_report"):
            definitions.append(
                {
                    "path": path,
                    "line": node.lineno,
                    "name": node.name,
                    "error": None,
                }
            )
    return definitions


def validate_verifier_boundaries(scan_roots=DEFAULT_SCAN_ROOTS):
    violations = []
    for path in python_files(scan_roots):
        for definition in tool_report_definitions(path):
            if definition["error"] or not is_relative_to(path, VERIFIER_MODULE_ROOT.resolve()):
                violations.append(definition)
    return violations


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Ensure *_tool_report() verifier functions live under eval_pipeline/adapter_runner/verifier_modules."
    )
    parser.add_argument(
        "scan_roots",
        nargs="*",
        default=list(DEFAULT_SCAN_ROOTS),
        help="Files or directories to scan. Defaults to eval_pipeline and scripts.",
    )
    args = parser.parse_args(argv)
    violations = validate_verifier_boundaries(args.scan_roots)
    if violations:
        print("Verifier boundary check failed. Move *_tool_report() functions into verifier_modules:", file=sys.stderr)
        for violation in violations:
            rel = violation["path"].relative_to(ROOT)
            suffix = f" ({violation['error']})" if violation["error"] else ""
            print(f"- {rel}:{violation['line']} {violation['name']}{suffix}", file=sys.stderr)
        return 1
    print("Verifier boundary check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
