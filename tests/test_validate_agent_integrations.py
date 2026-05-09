import unittest

from scripts.validate_agent_integrations import validate_agent_integrations


class ValidateAgentIntegrationsTests(unittest.TestCase):
    def test_agent_integration_stack_validator_passes(self):
        report = validate_agent_integrations()

        self.assertTrue(report["valid"])
        self.assertEqual(report["passed"], 4)
        self.assertEqual(report["total"], 4)
        names = {check["name"] for check in report["checks"]}
        self.assertEqual(
            names,
            {
                "openai_wrapped_tools_smoke",
                "fastapi_policy_service_smoke",
                "mcp_tool_smoke",
                "controlled_agent_eval_harness",
            },
        )


if __name__ == "__main__":
    unittest.main()
