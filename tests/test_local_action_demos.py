import pathlib
import unittest

from eval_pipeline import agent_api


ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED_DEMOS = {
    "email_send": "email_send_guardrail",
    "file_operation": "file_operation_guardrail",
    "calendar_scheduling": "calendar_scheduling",
    "booking_purchase": "booking_purchase_guardrail",
    "research_grounding": "research_answer_grounding",
    "publication_check": "publication_check",
    "meeting_summary": "meeting_summary_checker",
}


def materialize_evidence(demo):
    values = {field["id"]: field.get("value", "") for field in demo.get("fields", [])}
    evidence = []
    for template in demo.get("evidence_template", []):
        text = template["text"]
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        item = {key: value for key, value in template.items() if key != "text"}
        item.setdefault("trust_tier", "verified")
        item.setdefault("redaction_status", "synthetic")
        item["text"] = text
        evidence.append(item)
    return evidence


class LocalActionDemoTests(unittest.TestCase):
    def test_demo_bundle_has_expected_surfaces(self):
        payload = agent_api.load_json_file(ROOT / "examples" / "local_action_demos.json")

        self.assertEqual(payload["local_action_demos_version"], "0.1")
        self.assertEqual({demo["id"]: demo["adapter_id"] for demo in payload["demos"]}, EXPECTED_DEMOS)
        for demo in payload["demos"]:
            self.assertTrue(demo["candidate"])
            self.assertGreaterEqual(len(demo["fields"]), 3)
            self.assertGreaterEqual(len(demo["evidence_template"]), 3)
            self.assertGreaterEqual(len(demo["constraints"]), 3)

    def test_each_demo_runs_through_workflow_contract(self):
        payload = agent_api.load_json_file(ROOT / "examples" / "local_action_demos.json")
        for demo in payload["demos"]:
            with self.subTest(demo=demo["id"]):
                workflow_request = {
                    "contract_version": "0.1",
                    "workflow_id": f"local-demo-test-{demo['id']}",
                    "adapter": demo["adapter_id"],
                    "request": demo["request"],
                    "candidate": demo["candidate"],
                    "evidence": materialize_evidence(demo),
                    "constraints": demo["constraints"],
                    "allowed_actions": ["accept", "revise", "retrieve", "ask", "defer", "refuse"],
                    "metadata": {"surface": "test_local_action_demos", "demo_id": demo["id"]},
                }

                result = agent_api.check_workflow_request(workflow_request)

                self.assertEqual(result["gate_decision"], "pass")
                self.assertEqual(result["recommended_action"], "revise")
                self.assertEqual(result["candidate_gate"], "block")
                self.assertEqual(result["candidate_aix"]["decision"], "refuse")
                self.assertGreaterEqual(len(result["violations"]), 1)


if __name__ == "__main__":
    unittest.main()
