#!/usr/bin/env python
"""Run MCP-Bench once plain and once with AANA before tool execution.

This script expects a local checkout of https://github.com/Accenture/mcp-bench.
It does not vendor MCP-Bench into this repo. The AANA condition monkey-patches
MCP-Bench's imported runner classes so the actual MCP tool execution boundary
calls AANA before `PersistentMultiServerManager.call_tool(...)` delegates to a
server.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import pathlib
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aana.integrations.mcp_bench import (  # noqa: E402
    MCPBenchAANAConfig,
    install_mcp_bench_aana_guard,
    restore_mcp_bench_aana_guard,
)


DEFAULT_OUTPUT_DIR = ROOT / "eval_outputs" / "mcp_bench_aana_ablation"


@contextmanager
def _pushd(path: pathlib.Path):
    previous = pathlib.Path.cwd()
    try:
        import os

        os.chdir(path)
        yield
    finally:
        os.chdir(previous)


def _parse_models(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    models: list[str] = []
    for value in values:
        models.extend(part.strip() for part in value.split(",") if part.strip())
    return models or None


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_json_safe(item) for item in value]
        return str(value)


def _load_runner_module(mcp_bench_dir: pathlib.Path) -> Any:
    if not (mcp_bench_dir / "run_benchmark.py").exists():
        raise FileNotFoundError(f"{mcp_bench_dir} does not look like an MCP-Bench checkout")
    mcp_path = str(mcp_bench_dir.resolve())
    if mcp_path not in sys.path:
        sys.path.insert(0, mcp_path)
    return importlib.import_module("benchmark.runner")


async def _run_condition(
    *,
    condition: str,
    runner_module: Any,
    selected_models: list[str] | None,
    tasks_file: str | None,
    task_limit: int | None,
    output_dir: pathlib.Path,
    enable_distraction_servers: bool,
    distraction_count: int,
    use_fuzzy_descriptions: bool,
    filter_problematic_tools: bool,
    concurrent_summarization: bool,
    aana_config: MCPBenchAANAConfig | None = None,
    allow_empty_results: bool = False,
) -> dict[str, Any]:
    originals: dict[str, Any] | None = None
    if aana_config:
        originals = install_mcp_bench_aana_guard(runner_module, aana_config)
    started = time.perf_counter()
    try:
        runner = runner_module.BenchmarkRunner(
            tasks_file=tasks_file,
            enable_distraction_servers=enable_distraction_servers,
            distraction_count=distraction_count,
            filter_problematic_tools=filter_problematic_tools,
            concurrent_summarization=concurrent_summarization,
            use_fuzzy_descriptions=use_fuzzy_descriptions,
        )
        if getattr(runner, "commands_config", None) is None and hasattr(runner, "load_commands_config"):
            runner.commands_config = await runner.load_commands_config()
        results = await runner.run_benchmark(selected_models=selected_models, task_limit=task_limit)
        if not results and not allow_empty_results:
            raise RuntimeError(f"MCP-Bench condition {condition!r} produced no metrics or result payload")
    finally:
        if originals:
            restore_mcp_bench_aana_guard(runner_module, originals)
    elapsed = time.perf_counter() - started
    payload = {
        "condition": condition,
        "elapsed_seconds": elapsed,
        "selected_models": selected_models,
        "tasks_file": tasks_file,
        "task_limit": task_limit,
        "results": _json_safe(results),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{condition}_results.json"
    output_file.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    payload["output_file"] = str(output_file)
    return payload


async def run(args: argparse.Namespace) -> dict[str, Any]:
    mcp_bench_dir = pathlib.Path(args.mcp_bench_dir).resolve()
    output_dir = pathlib.Path(args.output_dir).resolve()
    selected_models = _parse_models(args.models)
    conditions = {item.strip() for item in args.conditions.split(",") if item.strip()}
    invalid = conditions - {"plain", "aana"}
    if invalid:
        raise ValueError(f"Unknown conditions: {sorted(invalid)}")

    with _pushd(mcp_bench_dir):
        runner_module = _load_runner_module(mcp_bench_dir)
        common = {
            "runner_module": runner_module,
            "selected_models": selected_models,
            "tasks_file": args.tasks_file,
            "task_limit": args.task_limit,
            "output_dir": output_dir,
            "enable_distraction_servers": args.distraction_count > 0,
            "distraction_count": args.distraction_count,
            "use_fuzzy_descriptions": not args.disable_fuzzy,
            "filter_problematic_tools": not args.disable_filter_problematic_tools,
            "concurrent_summarization": not args.disable_concurrent_summarization,
            "allow_empty_results": args.allow_empty_results,
        }
        condition_results: dict[str, Any] = {}
        if "plain" in conditions:
            condition_results["base_agent"] = await _run_condition(condition="base_agent", aana_config=None, **common)
        if "aana" in conditions:
            audit_log_path = output_dir / "base_agent_plus_aana_audit.jsonl"
            if audit_log_path.exists() and not args.append_audit_log:
                audit_log_path.unlink()
            aana_config = MCPBenchAANAConfig(
                execution_mode=args.aana_execution_mode,
                authorization_state=args.aana_authorization_state,
                risk_domain=args.aana_risk_domain,
                audit_log_path=audit_log_path,
                condition_name="base_agent_plus_aana",
            )
            condition_results["base_agent_plus_aana"] = await _run_condition(
                condition="base_agent_plus_aana",
                aana_config=aana_config,
                **common,
            )

    summary = {
        "experiment_id": "mcp_bench_base_vs_aana_wrapper_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": (
            "This is a paired MCP-Bench runner for evaluating AANA as a pre-tool-call "
            "audit/control layer around a base agent. It is not an official leaderboard "
            "claim until the run completes under the benchmark maintainers' accepted protocol."
        ),
        "mcp_bench_dir": str(mcp_bench_dir),
        "output_dir": str(output_dir),
        "conditions": condition_results,
        "aana_execution_rule": "Only AANA route=accept can execute in enforcement mode.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_file = output_dir / "mcp_bench_base_vs_aana_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    summary["summary_file"] = str(summary_file)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MCP-Bench base-agent vs AANA-gated ablation.")
    parser.add_argument("--mcp-bench-dir", required=True, help="Path to a local Accenture/mcp-bench checkout.")
    parser.add_argument("--models", nargs="*", help="Model names to pass to MCP-Bench, comma-separated or repeated.")
    parser.add_argument("--tasks-file", help="Optional MCP-Bench tasks file path, relative to the MCP-Bench checkout.")
    parser.add_argument("--task-limit", type=int, help="Optional task limit for smoke runs.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for paired run artifacts.")
    parser.add_argument("--conditions", default="plain,aana", help="Comma-separated: plain,aana.")
    parser.add_argument("--distraction-count", type=int, default=0, help="MCP-Bench distraction server count. Default 0 for reproducible smoke runs.")
    parser.add_argument("--disable-fuzzy", action="store_true", help="Use concrete task descriptions instead of fuzzy descriptions.")
    parser.add_argument("--disable-filter-problematic-tools", action="store_true")
    parser.add_argument("--disable-concurrent-summarization", action="store_true")
    parser.add_argument("--aana-execution-mode", choices=["enforce", "shadow"], default="enforce")
    parser.add_argument("--aana-authorization-state", choices=["none", "user_claimed", "authenticated", "validated", "confirmed"], default="confirmed")
    parser.add_argument("--aana-risk-domain", default="agent_tool_use")
    parser.add_argument("--append-audit-log", action="store_true")
    parser.add_argument("--allow-empty-results", action="store_true", help="Do not fail if MCP-Bench returns an empty metrics payload.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = asyncio.run(run(args))
    conditions = ", ".join(summary["conditions"].keys())
    print(f"pass -- conditions={conditions} summary={summary['summary_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
