import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MCPBenchAblationScriptTests(unittest.TestCase):
    def test_script_runs_plain_and_aana_conditions_against_fake_mcp_bench(self):
        with tempfile.TemporaryDirectory() as tmp:
            bench = Path(tmp) / "mcp-bench"
            (bench / "benchmark").mkdir(parents=True)
            (bench / "benchmark" / "__init__.py").write_text("", encoding="utf-8")
            (bench / "run_benchmark.py").write_text("# fake MCP-Bench marker\n", encoding="utf-8")
            (bench / "benchmark" / "runner.py").write_text(
                textwrap.dedent(
                    """
                    import asyncio

                    class PersistentMultiServerManager:
                        def __init__(self):
                            self.executed = []
                            self.all_tools = {
                                "Weather Data:get_forecast": {
                                    "server": "Weather Data",
                                    "original_name": "get_forecast",
                                    "description": "Fetch public weather forecast data.",
                                    "input_schema": {"type": "object"},
                                },
                                "Admin:delete_user": {
                                    "server": "Admin",
                                    "original_name": "delete_user",
                                    "description": "Delete a user account.",
                                    "input_schema": {"type": "object"},
                                },
                            }

                        async def call_tool(self, tool_name, parameters, use_cache=True):
                            self.executed.append(tool_name)
                            return {"executed": True, "tool_name": tool_name}

                    class TaskExecutor:
                        def __init__(self, server_manager):
                            self.server_manager = server_manager

                        async def execute(self, task):
                            first = await self.server_manager.call_tool("Weather Data:get_forecast", {"city": "Boston"})
                            second = await self.server_manager.call_tool("Admin:delete_user", {"user_id": "u-123"})
                            return {
                                "first_type": type(first).__name__,
                                "second_type": type(second).__name__,
                                "executed": list(getattr(self.server_manager, "executed", [])),
                            }

                    class BenchmarkRunner:
                        def __init__(self, **kwargs):
                            self.kwargs = kwargs

                        async def run_benchmark(self, selected_models=None, task_limit=None):
                            manager = PersistentMultiServerManager()
                            result = await TaskExecutor(manager).execute("fake task")
                            return {"selected_models": selected_models, "task_limit": task_limit, "result": result}
                    """
                ),
                encoding="utf-8",
            )
            output_dir = Path(tmp) / "out"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "benchmarks" / "run_mcp_bench_aana_ablation.py"),
                    "--mcp-bench-dir",
                    str(bench),
                    "--output-dir",
                    str(output_dir),
                    "--conditions",
                    "plain,aana",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((output_dir / "mcp_bench_base_vs_aana_summary.json").read_text(encoding="utf-8"))
            plain = summary["conditions"]["base_agent"]["results"]["result"]
            guarded = summary["conditions"]["base_agent_plus_aana"]["results"]["result"]
            self.assertEqual(plain["executed"], ["Weather Data:get_forecast", "Admin:delete_user"])
            self.assertEqual(guarded["executed"], ["Weather Data:get_forecast"])
            self.assertEqual(guarded["second_type"], "AANABlockedToolResult")
            audit_text = (output_dir / "base_agent_plus_aana_audit.jsonl").read_text(encoding="utf-8")
            self.assertIn("Weather Data:get_forecast", audit_text)
            self.assertIn("Admin:delete_user", audit_text)
            self.assertNotIn("u-123", audit_text)


if __name__ == "__main__":
    unittest.main()

