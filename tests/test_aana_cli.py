import importlib.util
import io
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


aana_cli = load_script("aana_cli", ROOT / "scripts" / "aana_cli.py")


class AanaCliTests(unittest.TestCase):
    def run_cli(self, args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = aana_cli.main(args)
        return code, output.getvalue()

    def test_list_shows_gallery_adapters(self):
        code, output = self.run_cli(["list"])

        self.assertEqual(code, 0)
        self.assertIn("travel_planning", output)
        self.assertIn("meal_planning", output)
        self.assertIn("support_reply", output)

    def test_run_gallery_adapter(self):
        code, output = self.run_cli(["run", "support_reply"])

        self.assertEqual(code, 0)
        self.assertIn('"gate_decision": "pass"', output)
        self.assertIn('"recommended_action": "revise"', output)

    def test_validate_gallery_runs_examples(self):
        code, output = self.run_cli(["validate-gallery", "--run-examples"])

        self.assertEqual(code, 0)
        self.assertIn("support_reply", output)

    def test_run_file_support_adapter(self):
        code, output = self.run_cli(
            [
                "run-file",
                "--adapter",
                "examples/support_reply_adapter.json",
                "--prompt",
                "Draft a customer-support reply for a refund request. Use only verified facts: customer name is Maya Chen, order ID and refund eligibility are not available.",
                "--candidate",
                "Hi Maya, order #A1842 is eligible for a full refund and your card ending 4242 will be credited in 3 days.",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn('"candidate_gate": "block"', output)

    def test_scaffold_creates_adapter_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, output = self.run_cli(["scaffold", "insurance claim triage", "--output-dir", tmp])

            self.assertEqual(code, 0)
            self.assertIn("insurance_claim_triage_adapter.json", output)
            self.assertTrue((pathlib.Path(tmp) / "insurance_claim_triage_adapter.json").exists())

    def test_agent_check_support_event(self):
        code, output = self.run_cli(["agent-check", "--event", "examples/agent_event_support_reply.json"])

        self.assertEqual(code, 0)
        self.assertIn('"agent": "openclaw"', output)
        self.assertIn('"gate_decision": "pass"', output)
        self.assertIn('"recommended_action": "revise"', output)
        self.assertIn('"safe_response"', output)

    def test_policy_presets_lists_agent_workflows(self):
        code, output = self.run_cli(["policy-presets"])

        self.assertEqual(code, 0)
        self.assertIn("message_send", output)
        self.assertIn("code_commit", output)
        self.assertIn("private_data_use", output)

    def test_validate_event_accepts_support_event(self):
        code, output = self.run_cli(["validate-event", "--event", "examples/agent_event_support_reply.json"])

        self.assertEqual(code, 0)
        self.assertIn("Agent event is valid", output)

    def test_agent_schema_prints_event_schema(self):
        code, output = self.run_cli(["agent-schema", "agent_event"])

        self.assertEqual(code, 0)
        self.assertIn("AANA Agent Event", output)
        self.assertIn("adapter_id", output)

    def test_run_agent_examples(self):
        code, output = self.run_cli(["run-agent-examples"])

        self.assertEqual(code, 0)
        self.assertIn("demo-support-refund-001", output)
        self.assertIn("demo-travel-booking-001", output)
        self.assertIn("demo-meal-planning-001", output)

    def test_scaffold_agent_event_creates_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, output = self.run_cli(["scaffold-agent-event", "support_reply", "--output-dir", tmp])

            self.assertEqual(code, 0)
            self.assertIn("support_reply.json", output)
            self.assertTrue((pathlib.Path(tmp) / "support_reply.json").exists())


if __name__ == "__main__":
    unittest.main()
