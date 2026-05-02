import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "examples" / "openclaw" / "aana-guardrail-skill-bundled" / "bin" / "aana_guardrail_check.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("aana_guardrail_check", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load_helper()


class OpenClawBundledHelperTests(unittest.TestCase):
    def test_validate_url_allows_localhost(self):
        self.assertEqual(helper.validate_url("http://127.0.0.1:8765/agent-check"), "http://127.0.0.1:8765/agent-check")
        self.assertEqual(helper.validate_url("http://localhost:8765/agent-check"), "http://localhost:8765/agent-check")

    def test_validate_url_blocks_remote_hosts(self):
        with self.assertRaises(ValueError):
            helper.validate_url("https://example.com/agent-check")

    def test_secret_like_keys_are_detected(self):
        found = helper.find_secret_like_keys({"metadata": {"api_key": "redacted"}})

        self.assertEqual(found, ["$.metadata.api_key"])

    def test_payload_converts_to_agent_event(self):
        event = helper.to_agent_event(
            {
                "adapter_id": "support_reply",
                "request_summary": "draft a refund support reply",
                "candidate_summary": "reply would promise refund eligibility",
                "evidence_summary": ["refund eligibility is unknown"],
            }
        )

        self.assertEqual(event["adapter_id"], "support_reply")
        self.assertEqual(event["user_request"], "draft a refund support reply")
        self.assertEqual(event["candidate_action"], "reply would promise refund eligibility")
        self.assertEqual(event["available_evidence"], ["refund eligibility is unknown"])
        self.assertTrue(event["metadata"]["redacted_review_payload"])


if __name__ == "__main__":
    unittest.main()
