import pathlib
import unittest

from eval_pipeline import agent_api


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AgentApiTests(unittest.TestCase):
    def test_check_event_returns_agent_guardrail_result(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")

        result = agent_api.check_event(event)

        self.assertEqual(result["agent"], "openclaw")
        self.assertEqual(result["adapter_id"], "support_reply")
        self.assertEqual(result["candidate_gate"], "block")
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "revise")
        self.assertTrue(result["violations"])
        self.assertIn("safe_response", result)

    def test_policy_presets_include_agent_workflows(self):
        presets = agent_api.list_policy_presets()

        self.assertIn("message_send", presets)
        self.assertIn("file_write", presets)
        self.assertIn("code_commit", presets)
        self.assertIn("support_reply", presets)
        self.assertIn("private_data_use", presets)

    def test_validate_event_reports_missing_adapter(self):
        report = agent_api.validate_event({"user_request": "Draft a reply."})

        self.assertFalse(report["valid"])
        self.assertEqual(report["errors"], 1)
        self.assertIn("adapter_id", report["issues"][0]["path"])

    def test_run_agent_event_examples(self):
        report = agent_api.run_agent_event_examples()

        self.assertTrue(report["valid"])
        self.assertGreaterEqual(report["count"], 3)
        event_ids = {item["event_id"] for item in report["checked_examples"]}
        self.assertIn("demo-support-refund-001", event_ids)
        self.assertIn("demo-travel-booking-001", event_ids)
        self.assertIn("demo-meal-planning-001", event_ids)


if __name__ == "__main__":
    unittest.main()
