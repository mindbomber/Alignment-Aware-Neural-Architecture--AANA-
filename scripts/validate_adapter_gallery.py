#!/usr/bin/env python
"""Validate the checked-in AANA adapter gallery."""

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_adapter
import validate_adapter


REQUIRED_ENTRY_FIELDS = [
    "id",
    "title",
    "status",
    "adapter_path",
    "workflow",
    "best_for",
    "prompt",
    "bad_candidate",
    "expected",
    "copy_command",
    "caveats",
]
EXPECTED_FIELDS = [
    "candidate_gate",
    "gate_decision",
    "recommended_action",
    "failing_constraints",
    "aix_decision",
    "candidate_aix_decision",
]


def add_issue(issues, level, path, message):
    issues.append({"level": level, "path": path, "message": message})


def has_text(value):
    return isinstance(value, str) and bool(value.strip())


def nonempty_list(value):
    return isinstance(value, list) and bool(value)


def load_gallery(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        gallery = json.load(handle)
    if not isinstance(gallery, dict):
        raise ValueError("Gallery file must contain a JSON object.")
    return gallery


def validate_entry_shape(entry, index, issues):
    base = f"adapters[{index}]"
    if not isinstance(entry, dict):
        add_issue(issues, "error", base, "Adapter gallery entry must be an object.")
        return

    for field in REQUIRED_ENTRY_FIELDS:
        if field not in entry:
            add_issue(issues, "error", f"{base}.{field}", "Required field is missing.")

    for field in ["id", "title", "status", "adapter_path", "workflow", "prompt", "bad_candidate", "copy_command"]:
        if field in entry and not has_text(entry.get(field)):
            add_issue(issues, "error", f"{base}.{field}", "Field must be a non-empty string.")

    for field in ["best_for", "caveats"]:
        if field in entry and not nonempty_list(entry.get(field)):
            add_issue(issues, "error", f"{base}.{field}", "Field must be a non-empty list.")

    expected = entry.get("expected", {})
    if not isinstance(expected, dict):
        add_issue(issues, "error", f"{base}.expected", "Expected result must be an object.")
        return

    for field in EXPECTED_FIELDS:
        if field not in expected:
            add_issue(issues, "error", f"{base}.expected.{field}", "Required expected field is missing.")

    for field in ["candidate_gate", "gate_decision", "recommended_action", "aix_decision", "candidate_aix_decision"]:
        if field in expected and not has_text(expected.get(field)):
            add_issue(issues, "error", f"{base}.expected.{field}", "Expected field must be a non-empty string.")

    if "failing_constraints" in expected and not nonempty_list(expected.get("failing_constraints")):
        add_issue(issues, "error", f"{base}.expected.failing_constraints", "Expected failing constraints must be a non-empty list.")


def validate_gallery(gallery, run_examples=False):
    issues = []

    if not has_text(gallery.get("version")):
        add_issue(issues, "error", "version", "Gallery version must be a non-empty string.")
    if not has_text(gallery.get("description")):
        add_issue(issues, "error", "description", "Gallery description must be a non-empty string.")

    entries = gallery.get("adapters", [])
    if not nonempty_list(entries):
        add_issue(issues, "error", "adapters", "Gallery must contain at least one adapter entry.")
        entries = []

    seen_ids = set()
    checked = []
    for index, entry in enumerate(entries if isinstance(entries, list) else []):
        validate_entry_shape(entry, index, issues)
        if not isinstance(entry, dict):
            continue

        entry_id = entry.get("id")
        if entry_id in seen_ids:
            add_issue(issues, "error", f"adapters[{index}].id", f"Duplicate gallery id: {entry_id}.")
        seen_ids.add(entry_id)

        adapter_path = ROOT / str(entry.get("adapter_path", ""))
        if not adapter_path.exists():
            add_issue(issues, "error", f"adapters[{index}].adapter_path", f"Adapter file does not exist: {entry.get('adapter_path')}.")
            continue

        try:
            adapter = validate_adapter.load_adapter(adapter_path)
            adapter_report = validate_adapter.validate_adapter(adapter)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            add_issue(issues, "error", f"adapters[{index}].adapter_path", f"Adapter could not be loaded: {exc}.")
            continue

        if not adapter_report["valid"]:
            add_issue(issues, "error", f"adapters[{index}].adapter_path", "Referenced adapter does not pass adapter validation.")

        if run_examples and entry.get("status") == "executable":
            result = run_adapter.run_adapter(adapter, entry.get("prompt", ""), entry.get("bad_candidate", ""))
            expected = entry.get("expected", {})
            for key in ["candidate_gate", "gate_decision", "recommended_action"]:
                if result.get(key) != expected.get(key):
                    add_issue(
                        issues,
                        "error",
                        f"adapters[{index}].expected.{key}",
                        f"Expected {expected.get(key)!r}, got {result.get(key)!r}.",
                    )

            aix_decision = result.get("aix", {}).get("decision")
            if aix_decision != expected.get("aix_decision"):
                add_issue(
                    issues,
                    "error",
                    f"adapters[{index}].expected.aix_decision",
                    f"Expected {expected.get('aix_decision')!r}, got {aix_decision!r}.",
                )

            candidate_aix_decision = result.get("candidate_aix", {}).get("decision")
            if candidate_aix_decision != expected.get("candidate_aix_decision"):
                add_issue(
                    issues,
                    "error",
                    f"adapters[{index}].expected.candidate_aix_decision",
                    f"Expected {expected.get('candidate_aix_decision')!r}, got {candidate_aix_decision!r}.",
                )

            failed_constraints = {
                item.get("id")
                for item in result.get("constraint_results", [])
                if item.get("status") == "fail"
            }
            if failed_constraints:
                add_issue(
                    issues,
                    "error",
                    f"adapters[{index}].expected",
                    f"Final gated result still has failing constraints: {sorted(failed_constraints)}.",
                )

            candidate_failures = set()
            for violation in result.get("candidate_tool_report", {}).get("violations", []):
                candidate_failures.update(
                    run_adapter.violation_constraint_ids(adapter, violation.get("code"))
                )
            expected_failures = set(expected.get("failing_constraints", []))
            missing_failures = expected_failures - candidate_failures
            if missing_failures:
                add_issue(
                    issues,
                    "error",
                    f"adapters[{index}].expected.failing_constraints",
                    f"Bad candidate did not trigger expected constraints: {sorted(missing_failures)}.",
                )

            checked.append(
                {
                    "id": entry_id,
                    "gate_decision": result.get("gate_decision"),
                    "recommended_action": result.get("recommended_action"),
                    "aix_decision": aix_decision,
                }
            )

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "checked_examples": checked,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Validate the AANA adapter gallery.")
    parser.add_argument("--gallery", default="examples/adapter_gallery.json", help="Path to adapter gallery JSON.")
    parser.add_argument("--run-examples", action="store_true", help="Run executable examples and compare expected gate behavior.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main():
    args = parse_args()
    gallery = load_gallery(args.gallery)
    report = validate_gallery(gallery, run_examples=args.run_examples)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        status = "valid" if report["valid"] else "invalid"
        print(f"Adapter gallery is {status}: {report['errors']} error(s), {report['warnings']} warning(s).")
        for issue in report["issues"]:
            print(f"- {issue['level'].upper()} {issue['path']}: {issue['message']}")
        if report["checked_examples"]:
            print("Checked examples:")
            for item in report["checked_examples"]:
                print(f"- {item['id']}: gate={item['gate_decision']} action={item['recommended_action']} aix={item.get('aix_decision')}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Adapter gallery validation failed: {exc}", file=sys.stderr)
        sys.exit(2)
