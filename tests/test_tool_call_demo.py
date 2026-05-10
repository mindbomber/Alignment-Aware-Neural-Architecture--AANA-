import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO = ROOT / "docs" / "tool-call-demo"


class ToolCallDemoTests(unittest.TestCase):
    def test_static_demo_files_exist_and_link_assets(self):
        html = (DEMO / "index.html").read_text(encoding="utf-8")

        self.assertIn("Try AANA", html)
        self.assertIn('href="app.css"', html)
        self.assertIn('src="app.js"', html)
        self.assertTrue((DEMO / "app.css").exists())
        self.assertTrue((DEMO / "app.js").exists())

    def test_demo_has_contract_fields_and_decision_surface(self):
        html = (DEMO / "index.html").read_text(encoding="utf-8")

        for item in [
            "tool-json",
            "tool-category",
            "authorization-state",
            "risk-domain",
            "runtime-route",
            "evidence-json",
            "gate-decision",
            "recommended-action",
            "aix-score",
            "execution-status",
            "execution-proof",
        ]:
            self.assertIn(item, html)

    def test_browser_gate_logic_contains_aana_routes_and_blockers(self):
        script = (DEMO / "app.js").read_text(encoding="utf-8")

        self.assertIn("aana.agent_tool_precheck.v1", script)
        self.assertIn("private_read_has_authenticated_context", script)
        self.assertIn("write_missing_validation_or_confirmation", script)
        self.assertIn("evidence_missing_authorization", script)
        self.assertIn("schema_validation_failed", script)
        self.assertIn("public_read_allowed_without_identity_auth", script)
        self.assertIn("guardedSyntheticExecution", script)
        self.assertIn("synthetic_executor_call_count_after", script)

    def test_docs_link_to_tool_call_demo(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        index = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        try_demo = (ROOT / "docs" / "try-demo" / "index.md").read_text(encoding="utf-8")

        self.assertIn("docs/tool-call-demo/index.html", readme)
        self.assertIn("tool-call-demo/", index)
        self.assertIn("../tool-call-demo/index.html", try_demo)


if __name__ == "__main__":
    unittest.main()
