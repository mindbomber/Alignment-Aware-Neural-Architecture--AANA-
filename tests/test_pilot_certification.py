import unittest
from contextlib import redirect_stdout
from io import StringIO

from eval_pipeline import pilot_certification
from scripts import aana_cli


class PilotCertificationTests(unittest.TestCase):
    def test_pilot_readiness_report_passes_current_repo_surfaces(self):
        report = pilot_certification.pilot_readiness_report(cli_commands=aana_cli.cli_command_matrix())

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["summary"]["status"], "pass")
        self.assertEqual(report["summary"]["readiness_level"], "pilot_ready")
        self.assertGreaterEqual(report["summary"]["score_percent"], 90.0)
        self.assertIn("gates", report["summary"])
        surface_ids = {surface["surface_id"] for surface in report["surfaces"]}
        self.assertEqual(
            surface_ids,
            {
                "cli",
                "python_api",
                "http_bridge",
                "adapters",
                "agent_event_contract",
                "workflow_contract",
                "skills_plugins",
                "evidence",
                "audit_metrics",
                "docs",
                "contract_freeze",
            },
        )
        for surface in report["surfaces"]:
            self.assertIn("score_percent", surface)
            self.assertGreaterEqual(surface["score_percent"], 90.0)

    def test_pilot_readiness_report_fails_missing_cli_gate(self):
        report = pilot_certification.pilot_readiness_report(cli_commands=[])

        self.assertFalse(report["valid"])
        self.assertEqual(report["summary"]["readiness_level"], "not_pilot_ready")
        cli = next(surface for surface in report["surfaces"] if surface["surface_id"] == "cli")
        self.assertFalse(cli["ready"])
        self.assertEqual(cli["status"], "fail")
        self.assertLess(cli["score_percent"], 100.0)

    def test_cli_pilot_certify_json_reports_matrix(self):
        with redirect_stdout(StringIO()):
            code = aana_cli.main(["pilot-certify", "--json"])

        self.assertEqual(code, 0)

    def test_cli_contract_lists_pilot_certify(self):
        commands = {item["command"] for item in aana_cli.cli_command_matrix()}

        self.assertIn("pilot-certify", commands)


if __name__ == "__main__":
    unittest.main()
