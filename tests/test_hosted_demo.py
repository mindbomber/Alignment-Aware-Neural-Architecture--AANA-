import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "docs" / "demo"


class HostedDemoTests(unittest.TestCase):
    def test_hosted_demo_static_files_exist(self):
        for filename in ["index.html", "app.css", "app.js", "scenarios.json"]:
            self.assertTrue((DEMO_DIR / filename).is_file(), filename)
        self.assertTrue((ROOT / "docs" / "hosted-demo.md").is_file())

    def test_scenarios_are_synthetic_only_and_cover_public_demo_families(self):
        payload = json.loads((DEMO_DIR / "scenarios.json").read_text(encoding="utf-8"))

        self.assertTrue(payload["synthetic_only"])
        self.assertFalse(payload["secrets_required"])
        self.assertFalse(payload["real_side_effects"])
        self.assertGreaterEqual(len(payload["scenarios"]), 5)
        self.assertGreaterEqual(
            set(payload["blocked_capabilities"]),
            {
                "send_email",
                "delete_file",
                "deploy_release",
                "run_migration",
                "submit_payment",
                "export_private_data",
            },
        )
        self.assertEqual(
            {family["id"] for family in payload["families"]},
            {"enterprise", "personal_productivity", "government_civic"},
        )
        self.assertIn("docker compose up", payload["local_pilot_path"])

        categories = {scenario["category"] for scenario in payload["scenarios"]}
        families = {scenario["family"] for scenario in payload["scenarios"]}
        self.assertEqual(families, {"enterprise", "personal_productivity", "government_civic"})
        self.assertGreaterEqual(
            categories,
            {"enterprise", "developer_tooling", "personal_productivity", "civic_government", "research"},
        )
        for scenario in payload["scenarios"]:
            self.assertIn("result", scenario)
            self.assertEqual(scenario["result"]["gate_decision"], "pass")
            self.assertEqual(scenario["result"]["recommended_action"], "revise")
            self.assertEqual(scenario["result"]["candidate_gate"], "block")
            self.assertTrue(scenario["result"]["violations"])
            self.assertTrue(scenario["result"]["safe_response"])

    def test_hosted_demo_does_not_collect_secrets_or_call_live_backend(self):
        html = (DEMO_DIR / "index.html").read_text(encoding="utf-8").lower()
        js = (DEMO_DIR / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("<form", html)
        self.assertNotIn("type=\"password\"", html)
        self.assertNotIn("name=\"token\"", html)
        self.assertNotIn("authorization", js.lower())
        self.assertNotIn("localstorage", js.lower())
        self.assertNotIn("sessionstorage", js.lower())
        self.assertIn("family-tabs", html)
        self.assertIn("docker compose up", html)

        fetch_targets = re.findall(r"fetch\(([^)]+)\)", js)
        self.assertEqual(fetch_targets, ['"scenarios.json", { cache: "no-store" }'])
        self.assertNotRegex(js, r"https?://")
        self.assertNotRegex(js, r"/(agent-check|workflow-check|workflow-batch|playground/check)")

    def test_public_site_links_to_hosted_demo(self):
        index = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn('href="demo/"', index)
        self.assertIn("/demo/", readme)


if __name__ == "__main__":
    unittest.main()
