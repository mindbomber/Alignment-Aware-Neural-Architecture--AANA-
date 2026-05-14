import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from aana import cli


class PublicAanaCliTests(unittest.TestCase):
    def run_cli(self, args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = cli.main(args)
        return code, output.getvalue()

    def test_doctor_reports_runtime_readiness(self):
        code, output = self.run_cli(["doctor"])

        self.assertEqual(code, 0)
        self.assertIn("AANA doctor", output)
        self.assertIn("adapter_gallery", output)
        self.assertIn("agent_event_examples", output)

    def test_doctor_json_reports_checks(self):
        code, output = self.run_cli(["doctor", "--json"])
        report = json.loads(output)
        checks = {item["name"]: item for item in report["checks"]}

        self.assertEqual(code, 0)
        self.assertTrue(report["valid"])
        self.assertIn("adapter_gallery", checks)
        self.assertIn("agent_event_examples", checks)
        self.assertIn("agent_schemas", checks)

    def test_help_includes_doctor(self):
        parser = cli.build_parser()
        choices = parser._subparsers._group_actions[0].choices

        self.assertIn("doctor", choices)

    def test_help_includes_onboarding_commands(self):
        parser = cli.build_parser()
        choices = parser._subparsers._group_actions[0].choices

        for command in ("list", "run", "run-agent-examples", "scaffold-agent-event"):
            self.assertIn(command, choices)

    def test_list_json_shows_gallery_adapters(self):
        code, output = self.run_cli(["list", "--json"])
        report = json.loads(output)
        adapter_ids = {item["id"] for item in report["adapters"]}

        self.assertEqual(code, 0)
        self.assertIn("travel_planning", adapter_ids)
        self.assertIn("support_reply", adapter_ids)

    def test_run_gallery_adapter(self):
        code, output = self.run_cli(["run", "travel_planning"])
        report = json.loads(output)

        self.assertEqual(code, 0)
        self.assertEqual(report["adapter"], "travel_planning")
        self.assertEqual(report["gate_decision"], "pass")

    def test_run_agent_examples_json(self):
        code, output = self.run_cli(["run-agent-examples", "--json"])
        report = json.loads(output)

        self.assertEqual(code, 0)
        self.assertTrue(report["valid"])
        self.assertGreater(report["count"], 0)

    def test_scaffold_agent_event_dry_run(self):
        code, output = self.run_cli(["scaffold-agent-event", "support_reply", "--dry-run"])
        report = json.loads(output)

        self.assertEqual(code, 0)
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["event_preview"]["adapter_id"], "support_reply")

    def test_scaffold_agent_event_writes_file(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.run_cli(["scaffold-agent-event", "support_reply", "--output-dir", directory])
            report = json.loads(output)
            event_path = Path(report["created"]["event"])

            self.assertEqual(code, 0)
            self.assertTrue(event_path.exists())
            self.assertEqual(json.loads(event_path.read_text(encoding="utf-8"))["adapter_id"], "support_reply")


if __name__ == "__main__":
    unittest.main()
