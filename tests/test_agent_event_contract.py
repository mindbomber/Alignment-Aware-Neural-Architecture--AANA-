import datetime
import json
import pathlib
import unittest

from eval_pipeline import agent_api, agent_contract


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_fixtures():
    return json.loads((ROOT / "examples" / "agent_event_contract_fixtures.json").read_text(encoding="utf-8"))


class AgentEventContractTests(unittest.TestCase):
    def test_contract_fixtures_include_route_examples(self):
        fixtures = load_fixtures()
        routes = {item["expected_recommended_action"] for item in fixtures["valid_events"]}

        self.assertEqual(routes, {"accept", "revise", "ask", "defer", "refuse"})

    def test_valid_agent_event_fixtures_pass_contract_validation(self):
        registry = agent_api.load_evidence_registry(ROOT / "examples" / "evidence_registry.json")
        for item in load_fixtures()["valid_events"]:
            with self.subTest(item=item["name"]):
                report = agent_api.validate_event(item["event"], evidence_registry=registry)

                self.assertTrue(report["valid"], report)

    def test_invalid_agent_event_fixtures_fail_contract_validation(self):
        registry = agent_api.load_evidence_registry(ROOT / "examples" / "evidence_registry.json")
        for item in load_fixtures()["invalid_events"]:
            with self.subTest(item=item["name"]):
                report = agent_api.validate_event(item["event"], evidence_registry=registry)
                error_paths = {issue["path"] for issue in report["issues"] if issue["level"] == "error"}

                self.assertFalse(report["valid"], report)
                for path in item["expected_error_paths"]:
                    self.assertIn(path, error_paths)

    def test_route_mismatch_is_detected_without_blocking_validation(self):
        item = load_fixtures()["warning_events"][0]
        report = agent_api.validate_event(item["event"])
        warning_paths = {issue["path"] for issue in report["issues"] if issue["level"] == "warning"}

        self.assertTrue(report["valid"], report)
        self.assertIn("$.workflow", warning_paths)

    def test_check_event_rejects_adapter_override_mismatch(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_events" / "support_reply.json")

        with self.assertRaises(ValueError) as raised:
            agent_api.check_event(event, adapter_id="research_summary")

        self.assertIn("Route mismatch", str(raised.exception))

    def test_structured_evidence_required_rejects_string_evidence(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_events" / "support_reply.json")
        report = agent_api.validate_event(event, require_structured_evidence=True)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"].startswith("$.available_evidence") for issue in report["issues"]))

    def test_evidence_registry_detects_stale_agent_event_evidence(self):
        registry = {
            "registry_version": "0.1",
            "sources": [
                {
                    "source_id": "fresh-agent-source",
                    "owner": "Agent Runtime",
                    "enabled": True,
                    "allowed_trust_tiers": ["verified"],
                    "allowed_redaction_statuses": ["redacted"],
                    "max_age_hours": 1,
                }
            ],
        }
        event = {
            "event_version": agent_contract.AGENT_EVENT_VERSION,
            "event_id": "stale-evidence-001",
            "agent": "test-agent",
            "adapter_id": "research_summary",
            "user_request": "Answer using Source A.",
            "candidate_action": "Answer using Source A.",
            "available_evidence": [
                {
                    "source_id": "fresh-agent-source",
                    "retrieved_at": "2026-05-05T00:00:00Z",
                    "trust_tier": "verified",
                    "redaction_status": "redacted",
                    "text": "Source A: verified.",
                }
            ],
            "allowed_actions": ["accept", "revise"],
            "metadata": {"policy_preset": "research_summary"},
        }

        report = agent_api.validate_event(
            event,
            evidence_registry=registry,
            now=datetime.datetime(2026, 5, 5, 2, 30, tzinfo=datetime.timezone.utc),
        )

        self.assertFalse(report["valid"])
        self.assertIn("$.available_evidence[0].retrieved_at", {issue["path"] for issue in report["issues"]})

    def test_policy_preset_adapter_mismatch_is_warning(self):
        event = {
            "event_version": agent_contract.AGENT_EVENT_VERSION,
            "event_id": "preset-mismatch-001",
            "agent": "test-agent",
            "adapter_id": "research_summary",
            "user_request": "Draft a support reply.",
            "candidate_action": "Draft a support reply.",
            "available_evidence": ["Support policy: verified facts only."],
            "allowed_actions": ["accept", "revise"],
            "metadata": {"policy_preset": "message_send"},
        }

        report = agent_api.validate_event(event)

        self.assertTrue(report["valid"], report)
        self.assertTrue(any(issue["path"] == "$.metadata.policy_preset" for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
