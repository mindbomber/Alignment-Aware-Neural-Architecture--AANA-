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


if __name__ == "__main__":
    unittest.main()
