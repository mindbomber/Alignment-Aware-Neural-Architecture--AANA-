import json
import pathlib
import unittest

from eval_pipeline import agent_api


ROOT = pathlib.Path(__file__).resolve().parents[1]
RECIPE = ROOT / "docs" / "recipes" / "use-aana-with-support-agents.md"
FIXTURE = ROOT / "examples" / "support_workflow_contract_examples.json"


class SupportIntegrationRecipeTests(unittest.TestCase):
    def test_support_recipe_routes_only_through_public_contract_paths(self):
        text = RECIPE.read_text(encoding="utf-8")

        self.assertIn("/workflow-check", text)
        self.assertIn("/agent-check", text)
        self.assertIn("/workflow-batch", text)
        self.assertIn("aana.SupportAANAClient", text)
        self.assertIn("LangGraph-Style Node", text)
        self.assertIn("CrewAI-Style Tool", text)
        self.assertIn("python scripts/aana_cli.py workflow-check", text)
        self.assertIn("http://127.0.0.1:8765/playground?adapter=crm_support_reply", text)
        self.assertIn("examples/support_workflow_contract_examples.json", text)
        self.assertNotIn("run_adapter.py", text)
        self.assertNotIn("legacy_runner.py", text)
        self.assertNotIn("verifier_modules", text)

    def test_copyable_support_fixture_contracts_are_valid(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(payload["cases"]), 8)

        for case in payload["cases"]:
            with self.subTest(case=case["name"]):
                workflow_report = agent_api.validate_workflow_request(case["workflow_request"])
                event_report = agent_api.validate_event(case["agent_event"])

                self.assertTrue(workflow_report["valid"], workflow_report)
                self.assertTrue(event_report["valid"], event_report)
                self.assertIn(
                    case["workflow_request"]["adapter"],
                    {"support_reply", "crm_support_reply", "email_send_guardrail", "ticket_update_checker", "invoice_billing_reply"},
                )
                self.assertEqual(case["workflow_request"]["candidate"], case["candidate_output"])

    def test_integration_index_and_playground_link_support_recipe(self):
        integration_index = (ROOT / "docs" / "integration-recipes.md").read_text(encoding="utf-8")
        runtime_index = (ROOT / "docs" / "integrate-runtime" / "index.md").read_text(encoding="utf-8")
        playground = (ROOT / "docs" / "web-playground.md").read_text(encoding="utf-8")

        self.assertIn("recipes/use-aana-with-support-agents.md", integration_index)
        self.assertIn("Use AANA with support agents", runtime_index)
        self.assertIn("adapter=support_reply", playground)
        self.assertIn("adapter=crm_support_reply", playground)


if __name__ == "__main__":
    unittest.main()
