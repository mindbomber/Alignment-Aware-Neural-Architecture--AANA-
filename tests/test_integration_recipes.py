import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class IntegrationRecipeTests(unittest.TestCase):
    def test_recipe_index_and_recipe_docs_exist(self):
        paths = [
            "docs/integration-recipes.md",
            "docs/recipes/use-aana-with-github-actions.md",
            "docs/recipes/use-aana-with-a-local-agent.md",
            "docs/recipes/use-aana-with-crm-support-drafts.md",
            "docs/recipes/use-aana-for-deployment-reviews.md",
            "docs/recipes/use-aana-in-shadow-mode.md",
        ]

        for path in paths:
            with self.subTest(path=path):
                recipe = ROOT / path
                self.assertTrue(recipe.exists(), path)
                text = recipe.read_text(encoding="utf-8")
                self.assertIn("Expected Result", text) if path != "docs/integration-recipes.md" else self.assertIn("Recipes", text)

    def test_recipes_reference_checked_in_working_inputs(self):
        expected_references = {
            "docs/recipes/use-aana-with-github-actions.md": [
                "examples/github-actions/aana-guardrails.yml",
                ".github/actions/aana-guardrails",
            ],
            "docs/recipes/use-aana-with-a-local-agent.md": [
                "examples/agent_event_support_reply.json",
            ],
            "docs/recipes/use-aana-with-crm-support-drafts.md": [
                "examples/workflow_crm_support_reply.json",
                "examples/evidence_registry.json",
            ],
            "docs/recipes/use-aana-for-deployment-reviews.md": [
                "examples/workflow_deployment_readiness.json",
                "examples/production_deployment_internal_pilot.json",
                "examples/human_governance_policy_internal_pilot.json",
                "examples/observability_policy_internal_pilot.json",
            ],
            "docs/recipes/use-aana-in-shadow-mode.md": [
                "examples/workflow_batch_productive_work.json",
                "examples/workflow_deployment_readiness.json",
            ],
        }

        for recipe_path, references in expected_references.items():
            text = (ROOT / recipe_path).read_text(encoding="utf-8")
            for reference in references:
                with self.subTest(recipe=recipe_path, reference=reference):
                    self.assertIn(reference, text)
                    self.assertTrue((ROOT / reference).exists(), reference)

    def test_recipes_include_copyable_commands(self):
        command_expectations = {
            "docs/recipes/use-aana-with-github-actions.md": [
                "python scripts/integrations/run_github_action_guardrails.py",
                "uses: mindbomber/Alignment-Aware-Neural-Architecture--AANA-/.github/actions/aana-guardrails@main",
            ],
            "docs/recipes/use-aana-with-a-local-agent.md": [
                "python scripts/aana_server.py",
                "python scripts/aana_cli.py agent-check",
                "Invoke-RestMethod",
            ],
            "docs/recipes/use-aana-with-crm-support-drafts.md": [
                "python scripts/aana_cli.py workflow-check",
                "--require-structured-evidence",
                "Invoke-RestMethod",
            ],
            "docs/recipes/use-aana-for-deployment-reviews.md": [
                "python scripts/aana_cli.py workflow-check",
                "python scripts/aana_cli.py release-check",
            ],
            "docs/recipes/use-aana-in-shadow-mode.md": [
                "python scripts/aana_cli.py workflow-batch",
                "--shadow-mode",
                "http://127.0.0.1:8765/dashboard",
            ],
        }

        for recipe_path, commands in command_expectations.items():
            text = (ROOT / recipe_path).read_text(encoding="utf-8")
            for command in commands:
                with self.subTest(recipe=recipe_path, command=command):
                    self.assertIn(command, text)


if __name__ == "__main__":
    unittest.main()
