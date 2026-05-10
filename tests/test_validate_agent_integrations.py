import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
while str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from scripts.validation.validate_agent_integrations import validate_agent_integrations


class ValidateAgentIntegrationsTests(unittest.TestCase):
    def test_agent_integration_stack_validator_passes(self):
        report = validate_agent_integrations()

        self.assertTrue(report["valid"])
        self.assertEqual(report["passed"], 15)
        self.assertEqual(report["total"], 15)
        names = {check["name"] for check in report["checks"]}
        self.assertEqual(
            names,
            {
                "cli_decision_shape_smoke",
                "python_sdk_smoke",
                "typescript_sdk_smoke",
                "plain_python_middleware_smoke",
                "openai_wrapped_tools_smoke",
                "openai_agents_sdk_example_middleware_smoke",
                "langchain_middleware_smoke",
                "autogen_middleware_smoke",
                "crewai_middleware_smoke",
                "fastapi_api_guard_middleware_smoke",
                "middleware_decision_shape_smoke",
                "fastapi_policy_service_smoke",
                "mcp_tool_smoke",
                "mcp_decision_shape_smoke",
                "controlled_agent_eval_harness",
            },
        )
        self.assertEqual(
            set(report["surfaces"]),
            {
                "CLI",
                "Python SDK",
                "TypeScript SDK",
                "Plain Python",
                "OpenAI Agents SDK",
                "OpenAI Agents SDK example",
                "LangChain",
                "AutoGen",
                "CrewAI",
                "FastAPI API guard",
                "Middleware",
                "FastAPI",
                "MCP descriptor",
                "MCP decision shape",
                "Controlled agent eval",
            },
        )
        for check in report["checks"]:
            if check["name"].endswith("decision_shape_smoke") or check["name"] in {"python_sdk_smoke", "typescript_sdk_smoke", "fastapi_policy_service_smoke"}:
                self.assertEqual(check.get("decision_shape_errors"), [])


if __name__ == "__main__":
    unittest.main()
