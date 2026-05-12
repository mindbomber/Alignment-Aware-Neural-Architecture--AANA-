import json
import pathlib
import tempfile
import unittest

import aana
from eval_pipeline import enterprise_support_demo
from scripts import aana_cli


class EnterpriseSupportDemoTests(unittest.TestCase):
    def test_demo_batch_uses_support_email_ticket_wedge(self):
        batch = enterprise_support_demo.build_enterprise_support_demo_batch()

        self.assertEqual(batch["batch_id"], "enterprise-support-email-ticket-demo")
        self.assertEqual(
            [item["adapter"] for item in batch["requests"]],
            ["crm_support_reply", "email_send_guardrail", "ticket_update_checker"],
        )
        self.assertEqual(batch["requests"][1]["allowed_actions"], ["defer", "refuse"])

    def test_run_demo_writes_runtime_audit_report_and_dashboard_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            flow = enterprise_support_demo.run_enterprise_support_demo(output_dir=temp_dir)

            self.assertTrue(flow["valid"], flow)
            self.assertEqual(len(flow["steps"]), 3)
            actions = {step["aana_check"]["recommended_action"] for step in flow["steps"]}
            self.assertIn("revise", actions)
            self.assertIn("defer", actions)
            for key in ("audit_log", "metrics", "dashboard", "aix_report_json", "aix_report_md", "demo_flow"):
                self.assertTrue(pathlib.Path(flow["artifacts"][key]).exists(), key)

            audit_text = pathlib.Path(flow["artifacts"]["audit_log"]).read_text(encoding="utf-8")
            self.assertNotIn("sk-live-secret-123", audit_text)
            self.assertNotIn("payroll.xlsx", audit_text)
            self.assertIn("Pilot demo evidence only", flow["claim_boundary"])

            report = json.loads(pathlib.Path(flow["artifacts"]["aix_report_json"]).read_text(encoding="utf-8"))
            self.assertIn("not production certification", " ".join(report["limitations"]).lower())

    def test_public_aana_exports_enterprise_support_demo(self):
        batch = aana.build_enterprise_support_demo_batch()

        self.assertEqual(batch["batch_id"], "enterprise-support-email-ticket-demo")
        self.assertEqual(aana.ENTERPRISE_SUPPORT_DEMO_VERSION, enterprise_support_demo.ENTERPRISE_SUPPORT_DEMO_VERSION)

    def test_cli_runs_enterprise_support_demo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            code = aana_cli.main(["enterprise-support-demo", "--output-dir", temp_dir])

            self.assertEqual(code, 0)
            self.assertTrue((pathlib.Path(temp_dir) / "demo-flow.json").exists())


if __name__ == "__main__":
    unittest.main()
