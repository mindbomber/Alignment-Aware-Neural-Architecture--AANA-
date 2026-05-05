"""Constraint-result utilities for adapter runner reports."""

from collections import defaultdict


def violation_constraint_ids(adapter, code, mapping_specs=(), default_mapping=None):
    constraint_ids = {constraint.get("id") for constraint in adapter.get("constraints", [])}
    for marker_constraint_id, mapping in mapping_specs:
        if marker_constraint_id in constraint_ids:
            return mapping.get(code, ["unmapped_constraint"])

    mapped = (default_mapping or {}).get(code)
    return [mapped] if mapped else ["unmapped_constraint"]


def constraint_results(adapter, report, mapping_specs=(), default_mapping=None):
    failures = defaultdict(list)
    for violation in report.get("violations", []):
        for constraint_id in violation_constraint_ids(
            adapter,
            violation.get("code"),
            mapping_specs=mapping_specs,
            default_mapping=default_mapping,
        ):
            failures[constraint_id].append(violation)

    results = []
    for constraint in adapter.get("constraints", []):
        constraint_id = constraint.get("id", "")
        mapped_failures = failures.get(constraint_id, [])
        results.append(
            {
                "id": constraint_id,
                "layer": constraint.get("layer"),
                "hard": bool(constraint.get("hard")),
                "status": "fail" if mapped_failures else "pass",
                "description": constraint.get("description", ""),
                "violations": mapped_failures,
            }
        )

    for violation in failures.get("unmapped_constraint", []):
        results.append(
            {
                "id": "unmapped_constraint",
                "layer": None,
                "hard": True,
                "status": "fail",
                "description": "A deterministic tool violation did not map to an adapter constraint.",
                "violations": [violation],
            }
        )

    return results

