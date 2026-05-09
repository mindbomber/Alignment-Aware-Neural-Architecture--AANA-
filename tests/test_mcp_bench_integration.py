import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from aana.integrations.mcp_bench import (
    AANABlockedToolResult,
    MCPBenchAANAConfig,
    build_mcp_bench_precheck_event,
    infer_mcp_bench_tool_category,
    install_mcp_bench_aana_guard,
    make_aana_guarded_manager_class,
    restore_mcp_bench_aana_guard,
)


class FakeMCPBenchManager:
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
        self.executed.append({"tool_name": tool_name, "parameters": parameters, "use_cache": use_cache})
        return {"executed": True, "tool_name": tool_name}


class FakeTaskExecutor:
    def __init__(self, server_manager):
        self.server_manager = server_manager

    async def execute(self, task):
        return {"task": task}


class MCPBenchIntegrationTests(unittest.TestCase):
    def test_public_utility_tool_category_is_public_read(self):
        category = infer_mcp_bench_tool_category(
            "Unit Converter:convert_temperature",
            {"value": 32, "from_unit": "fahrenheit", "to_unit": "celsius"},
            "Convert public units.",
        )
        self.assertEqual(category, "public_read")

    def test_build_event_uses_contract_fields_without_labels(self):
        event = build_mcp_bench_precheck_event(
            tool_name="Weather Data:get_forecast",
            parameters={"city": "Boston"},
            tool_info={
                "server": "Weather Data",
                "original_name": "get_forecast",
                "description": "Fetch public weather forecast data.",
                "input_schema": {"type": "object"},
            },
            task_context="Check the weather.",
            config=MCPBenchAANAConfig(),
        )
        self.assertEqual(event["schema_version"], "aana.agent_tool_precheck.v1")
        self.assertEqual(event["tool_category"], "public_read")
        self.assertEqual(event["recommended_route"], "accept")
        self.assertNotIn("expected_route", event)

    def test_guarded_manager_executes_only_when_aana_accepts(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = Path(tmp) / "audit.jsonl"
            guarded_cls = make_aana_guarded_manager_class(
                FakeMCPBenchManager,
                MCPBenchAANAConfig(audit_log_path=audit_log, authorization_state="none"),
            )
            manager = guarded_cls()

            allowed = asyncio.run(manager.call_tool("Weather Data:get_forecast", {"city": "Boston"}))
            blocked = asyncio.run(manager.call_tool("Admin:delete_user", {"user_id": "u-123"}))

            self.assertEqual(allowed["executed"], True)
            self.assertIsInstance(blocked, AANABlockedToolResult)
            self.assertEqual(len(manager.executed), 1)
            self.assertEqual(manager.executed[0]["tool_name"], "Weather Data:get_forecast")
            lines = [json.loads(line) for line in audit_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(lines), 2)
            self.assertTrue(lines[0]["execution_allowed"])
            self.assertFalse(lines[1]["execution_allowed"])
            self.assertIn("argument_sha256", lines[1])
            self.assertNotIn("u-123", audit_log.read_text(encoding="utf-8"))

    def test_install_and_restore_patches_mcp_bench_runner_classes(self):
        module = SimpleNamespace(
            PersistentMultiServerManager=FakeMCPBenchManager,
            TaskExecutor=FakeTaskExecutor,
        )
        originals = install_mcp_bench_aana_guard(module, MCPBenchAANAConfig())
        self.assertNotEqual(module.PersistentMultiServerManager, FakeMCPBenchManager)
        self.assertNotEqual(module.TaskExecutor, FakeTaskExecutor)
        restore_mcp_bench_aana_guard(module, originals)
        self.assertEqual(module.PersistentMultiServerManager, FakeMCPBenchManager)
        self.assertEqual(module.TaskExecutor, FakeTaskExecutor)


if __name__ == "__main__":
    unittest.main()

