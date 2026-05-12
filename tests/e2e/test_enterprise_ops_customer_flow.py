import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "aana_cli.py"

FORBIDDEN_AUDIT_TERMS = [
    "sk-live-secret-123",
    "payroll.xlsx",
    "customer_export.csv",
    "card ending 4242",
    "Internal note: risk flag",
    "Priya's bad deploy",
]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def load_json(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


class EnterpriseOpsCustomerE2ETests(unittest.TestCase):
    def assert_cli_ok(self, completed):
        self.assertEqual(
            completed.returncode,
            0,
            f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}",
        )

    def assert_redacted_audit(self, audit_log):
        text = pathlib.Path(audit_log).read_text(encoding="utf-8")

        self.assertTrue(text.strip(), "Audit log should contain redacted JSONL records.")
        for forbidden in FORBIDDEN_AUDIT_TERMS:
            self.assertNotIn(forbidden, text)

    def test_customer_runs_enterprise_ops_aix_audit_from_cli(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = run_cli("aix-audit", "--output-dir", temp_dir)

            self.assert_cli_ok(completed)
            self.assertIn("AANA AIx Audit", completed.stdout)

            report = load_json(pathlib.Path(temp_dir) / "aix-report.json")
            dashboard = load_json(pathlib.Path(temp_dir) / "enterprise-dashboard.json")
            metrics = load_json(pathlib.Path(temp_dir) / "metrics.json")
            manifest = load_json(pathlib.Path(temp_dir) / "audit-integrity.json")
            connectors = load_json(pathlib.Path(temp_dir) / "enterprise-connector-readiness.json")

            self.assertEqual(report["product"], "AANA AIx Audit")
            self.assertEqual(report["product_bundle"], "enterprise_ops_pilot")
            self.assertEqual(report["deployment_recommendation"], "pilot_ready_with_controls")
            self.assertIn("not production certification", " ".join(report["limitations"]).lower())
            self.assertEqual(report["audit_metadata"]["audit_record_count"], 8)
            self.assertEqual(report["overall_aix"]["hard_blocker_count"], 0)

            self.assertEqual(dashboard["source_of_truth"], "redacted_audit_metrics")
            self.assertEqual(dashboard["cards"]["pass"], 8)
            self.assertEqual(dashboard["cards"]["hard_blockers"], 0)
            self.assertEqual(dashboard["cards"]["shadow_would_intervene"], 8)
            self.assertEqual(dashboard["recommended_actions"], {"revise": 8})
            self.assertEqual(
                {surface["id"] for surface in dashboard["surface_breakdown"]},
                {"support_customer_communications", "data_access_controls", "devops_release_controls"},
            )

            self.assertEqual(metrics["record_count"], 8)
            self.assertEqual(metrics["metrics"]["execution_mode_count.shadow"], 8)
            self.assertEqual(manifest["record_count"], 8)
            self.assertEqual(connectors["summary"]["connector_count"], 7)
            self.assertEqual(connectors["summary"]["live_execution_enabled_count"], 0)
            self.assert_redacted_audit(pathlib.Path(temp_dir) / "audit.jsonl")

    def test_customer_runs_support_email_ticket_shadow_demo_from_cli(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = run_cli("enterprise-support-demo", "--shadow-mode", "--output-dir", temp_dir)

            self.assert_cli_ok(completed)
            self.assertIn("customer support + email send + ticket update", completed.stdout)

            flow = load_json(pathlib.Path(temp_dir) / "demo-flow.json")
            report = load_json(pathlib.Path(temp_dir) / "aix-report.json")
            dashboard = load_json(pathlib.Path(temp_dir) / "enterprise-dashboard.json")
            drift = load_json(pathlib.Path(temp_dir) / "aix-drift.json")

            self.assertTrue(flow["valid"], flow)
            self.assertEqual(flow["wedge"], "customer support + email send + ticket update")
            self.assertEqual(len(flow["steps"]), 3)
            self.assertEqual(flow["aix_report_summary"]["deployment_recommendation"], "not_pilot_ready")
            self.assertEqual(flow["dashboard_cards"]["shadow_would_intervene"], 3)
            self.assertEqual(flow["dashboard_cards"]["shadow_would_block"], 1)
            self.assertEqual(flow["dashboard_cards"]["hard_blockers"], 1)

            step_routes = {step["stage"]: step["aana_check"]["recommended_action"] for step in flow["steps"]}
            self.assertEqual(step_routes["support_reply"], "revise")
            self.assertEqual(step_routes["email_send"], "defer")
            self.assertEqual(step_routes["ticket_update"], "revise")
            email_step = next(step for step in flow["steps"] if step["stage"] == "email_send")
            self.assertIn("recommended_action_not_allowed", email_step["aix"]["hard_blockers"])

            self.assertEqual(report["deployment_recommendation"], "not_pilot_ready")
            self.assertIn("recommended_action_not_allowed", report["hard_blockers"])
            self.assertEqual(dashboard["recommended_actions"], {"defer": 1, "revise": 2})
            self.assertFalse(drift["valid"])
            self.assertEqual(drift["metrics"]["execution_mode_count.shadow"], 3)
            self.assert_redacted_audit(pathlib.Path(temp_dir) / "audit.jsonl")

    def test_customer_generates_connector_readiness_before_live_integration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = pathlib.Path(temp_dir) / "enterprise-connectors.json"
            completed = run_cli("enterprise-connectors", "--output", str(output))

            self.assert_cli_ok(completed)
            connectors = load_json(output)

            self.assertEqual(
                set(connectors["summary"]["required_connector_ids"]),
                {"crm_support", "ticketing", "email_send", "iam", "ci", "deployment", "data_export"},
            )
            self.assertEqual(connectors["summary"]["live_execution_enabled_count"], 0)
            for connector in connectors["connectors"]:
                self.assertFalse(connector["live_execution_enabled"])
                self.assertEqual(connector["default_runtime_route_before_approval"], "defer")
                self.assertFalse(connector["auth_requirements"]["tokens_in_audit_logs"])
                self.assertFalse(connector["redaction_requirements"]["raw_private_content_allowed_in_audit"])
                self.assertTrue(connector["shadow_mode_requirements"]["write_operations_disabled"])


if __name__ == "__main__":
    unittest.main()
