import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DocsConsolidationTests(unittest.TestCase):
    def test_three_primary_doc_entrypoints_exist(self):
        entrypoints = {
            "docs/try-demo/index.md": ["Hosted demo", "Adapter gallery", "Production positioning"],
            "docs/integrate-runtime/index.md": ["Product boundary", "Workflow Contract", "Agent Event Contract", "Production Boundary"],
            "docs/build-adapter/index.md": ["Product boundary", "Domain adapter template", "Adapter gallery", "Keep the claim narrow"],
        }

        for relative_path, expected_text in entrypoints.items():
            path = ROOT / relative_path
            with self.subTest(path=relative_path):
                self.assertTrue(path.exists(), relative_path)
                text = path.read_text(encoding="utf-8")
                for expected in expected_text:
                    self.assertIn(expected, text)

    def test_static_site_entrypoints_exist(self):
        for relative_path in [
            "docs/try-demo/index.html",
            "docs/integrate-runtime/index.html",
            "docs/build-adapter/index.html",
        ]:
            with self.subTest(path=relative_path):
                text = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("AANA Docs", text)
                self.assertIn("resource-card", text)

    def test_readme_points_to_three_entrypoints_instead_of_long_doc_sprawl(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("docs/try-demo/index.md", readme)
        self.assertIn("docs/integrate-runtime/index.md", readme)
        self.assertIn("docs/build-adapter/index.md", readme)
        self.assertNotIn("For the shortest practical path, see", readme)

    def test_compatibility_docs_name_their_canonical_entrypoint(self):
        expectations = {
            "docs/getting-started.md": "Canonical entry point: [Try Demo]",
            "docs/hosted-demo.md": "Canonical entry point: [Try Demo]",
            "docs/integration-recipes.md": "Canonical entry point: [Integrate Runtime]",
            "docs/product-boundary.md": "Canonical entry point: [Integrate Runtime]",
            "docs/aana-workflow-contract.md": "Canonical entry point: [Integrate Runtime]",
            "docs/agent-integration.md": "Canonical entry point: [Integrate Runtime]",
            "docs/domain-adapter-template.md": "Canonical entry point: [Build Adapter]",
            "docs/adapter-gallery.md": "Canonical entry point: [Build Adapter]",
        }

        for relative_path, expected in expectations.items():
            with self.subTest(path=relative_path):
                self.assertIn(expected, (ROOT / relative_path).read_text(encoding="utf-8"))

    def test_recommended_local_path_is_single_platform_onboarding_path(self):
        expected_commands = [
            "python -m pip install -e .",
            "aana doctor",
            "aana run travel_planning",
            "aana workflow-check --workflow examples/workflow_research_summary.json --audit-log eval_outputs/audit/local-onboarding.jsonl",
            "aana-server --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/aana-bridge.jsonl",
            "aana audit-summary --audit-log eval_outputs/audit/local-onboarding.jsonl",
        ]
        for relative_path in ["README.md", "docs/try-demo/index.md", "docs/getting-started.md"]:
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertIn("Recommended Local Path", text)
                self.assertIn("research", text.lower())
                self.assertIn("eval workflows", text.lower())
                for command in expected_commands:
                    self.assertIn(command, text)

    def test_product_boundary_defines_support_runtime_scope(self):
        boundary = (ROOT / "docs/product-boundary.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for text in [boundary, readme]:
            with self.subTest(source="boundary" if text == boundary else "readme"):
                self.assertIn("runtime guardrail layer", text)
                self.assertIn("Workflow Contract", text)
                self.assertIn("Agent Event", text)
                self.assertIn("accept", text)
                self.assertIn("revise", text)
                self.assertIn("retrieve", text)
                self.assertIn("ask", text)
                self.assertIn("defer", text)
                self.assertIn("refuse", text)

        support_scope = [
            "Draft support reply guardrail",
            "CRM support reply guardrail",
            "Refund/account fact boundary checker",
            "Email-send guardrail for support communications",
            "Ticket/customer-visible update checker",
            "Invoice/billing reply checker",
        ]
        for item in support_scope:
            self.assertIn(item, boundary)


if __name__ == "__main__":
    unittest.main()
