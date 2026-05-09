#!/usr/bin/env python
"""Run the Agent Tool-Use Control validation suite."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline.agent_tool_use_control import score_tool_use_rows
from eval_pipeline.hf_dataset_registry import load_registry, validate_hf_dataset_registry


DEFAULT_CASES = ROOT / "examples" / "agent_tool_use_control_validation_cases.json"
DEFAULT_REGISTRY = ROOT / "examples" / "hf_dataset_validation_registry.json"
DEFAULT_OUTPUT = ROOT / "eval_outputs" / "agent_tool_use_control_upgrade_results.json"


def _registry_allowed_sources(registry: dict) -> dict[str, set[str]]:
    allowed: dict[str, set[str]] = {}
    for dataset in registry.get("datasets", []):
        name = dataset.get("dataset_name")
        if name:
            allowed[name] = {split.get("allowed_use") for split in dataset.get("split_uses", []) if split.get("allowed_use")}
    return allowed


def validate_case_sources(cases: list[dict], registry: dict) -> list[str]:
    errors: list[str] = []
    registry_report = validate_hf_dataset_registry(registry)
    if not registry_report["valid"]:
        return [issue["message"] for issue in registry_report["issues"]]
    allowed = _registry_allowed_sources(registry)
    for case in cases:
        dataset_name = case.get("source_dataset")
        if dataset_name not in allowed:
            errors.append(f"{case.get('id')}: source_dataset is not registered: {dataset_name}")
        elif not (allowed[dataset_name] & {"calibration", "heldout_validation"}):
            errors.append(f"{case.get('id')}: source_dataset has no calibration or heldout validation use: {dataset_name}")
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    payload = json.loads(pathlib.Path(args.cases).read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    registry = load_registry(args.registry)
    source_errors = validate_case_sources(cases, registry)
    if source_errors:
        for error in source_errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1

    result = score_tool_use_rows(cases)
    result["dataset_sources"] = payload.get("dataset_sources", [])
    result["task_list"] = payload.get("task_list", [])
    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    metrics = result["metrics"]
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            "pass -- "
            f"cases={metrics['case_count']} "
            f"unsafe_action_recall={metrics['unsafe_action_recall']:.3f} "
            f"private_read_write_gating={metrics['private_read_write_gating']:.3f} "
            f"ask_defer_refuse_quality={metrics['ask_defer_refuse_quality']:.3f} "
            f"schema_failure_rate={metrics['schema_failure_rate']:.3f} "
            f"safe_allow_rate={metrics['safe_allow_rate']:.3f} "
            f"route_accuracy={metrics['route_accuracy']:.3f} "
            f"output={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

