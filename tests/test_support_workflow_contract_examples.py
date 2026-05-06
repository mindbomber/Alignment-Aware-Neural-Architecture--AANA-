import json
import pathlib
import unittest

from eval_pipeline import agent_api


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "support_workflow_contract_examples.json"


class SupportWorkflowContractExamplesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_contains_canonical_support_workflows(self):
        expected_names = {
            "draft_refund_missing_account_facts",
            "verified_refund_ineligibility_reply",
            "block_private_payment_data_leakage",
            "block_internal_crm_note_leakage",
            "ask_for_verification_path",
            "email_send_verified_recipient",
            "block_broad_bcc_recipient",
            "block_private_export_attachment",
        }

        self.assertEqual(self.payload["fixture_version"], "0.1")
        self.assertEqual({case["name"] for case in self.payload["cases"]}, expected_names)

    def test_workflow_and_agent_event_fixtures_validate(self):
        for case in self.payload["cases"]:
            with self.subTest(case=case["name"]):
                workflow_report = agent_api.validate_workflow_request(case["workflow_request"])
                event_report = agent_api.validate_event(case["agent_event"])

                self.assertTrue(workflow_report["valid"], workflow_report)
                self.assertTrue(event_report["valid"], event_report)
                self.assertTrue(case["candidate_bad_output"])
                self.assertEqual(case["candidate_output"], case["workflow_request"]["candidate"])
                self.assertEqual(case["candidate_output"], case["agent_event"]["candidate_action"])

    def test_workflow_fixtures_match_expected_gate_action_and_aix(self):
        for case in self.payload["cases"]:
            with self.subTest(case=case["name"]):
                result = agent_api.check_workflow_request(case["workflow_request"])
                expected = case["expected"]["workflow"]

                self.assertEqual(result["gate_decision"], expected["gate_decision"])
                self.assertEqual(result["recommended_action"], expected["recommended_action"])
                self.assertEqual(result.get("candidate_gate"), expected["candidate_gate"])
                self.assertEqual(result.get("aix", {}).get("decision"), expected["aix_decision"])
                self.assertEqual(result.get("candidate_aix", {}).get("decision"), expected["candidate_aix_decision"])
                self.assertEqual(result.get("aix", {}).get("score"), expected["aix_score"])
                self.assertEqual(result.get("candidate_aix", {}).get("score"), expected["candidate_aix_score"])
                self.assertEqual([item.get("code") for item in result.get("violations", [])], expected["violation_codes"])

    def test_agent_event_fixtures_match_expected_gate_action_and_aix(self):
        for case in self.payload["cases"]:
            with self.subTest(case=case["name"]):
                result = agent_api.check_event(case["agent_event"])
                expected = case["expected"]["agent_event"]

                self.assertEqual(result["gate_decision"], expected["gate_decision"])
                self.assertEqual(result["recommended_action"], expected["recommended_action"])
                self.assertEqual(result.get("candidate_gate"), expected["candidate_gate"])
                self.assertEqual(result.get("aix", {}).get("decision"), expected["aix_decision"])
                self.assertEqual(result.get("candidate_aix", {}).get("decision"), expected["candidate_aix_decision"])
                self.assertEqual(result.get("aix", {}).get("score"), expected["aix_score"])
                self.assertEqual(result.get("candidate_aix", {}).get("score"), expected["candidate_aix_score"])
                self.assertEqual([item.get("code") for item in result.get("violations", [])], expected["violation_codes"])

    def test_audit_safe_examples_exclude_raw_request_candidate_and_evidence(self):
        for case in self.payload["cases"]:
            with self.subTest(case=case["name"]):
                result = agent_api.check_workflow_request(case["workflow_request"])
                audit_example = case["audit_safe_output_example"]
                audit_json = json.dumps(audit_example, sort_keys=True)

                self.assertEqual(audit_example["gate_decision"], result["audit_summary"]["gate_decision"])
                self.assertEqual(audit_example["recommended_action"], result["audit_summary"]["recommended_action"])
                self.assertEqual(audit_example["candidate_gate"], result["audit_summary"]["candidate_gate"])
                self.assertEqual(audit_example["violation_codes"], result["audit_summary"]["violation_codes"])
                self.assertNotIn(case["workflow_request"]["request"], audit_json)
                self.assertNotIn(case["workflow_request"]["candidate"], audit_json)
                for evidence in case["workflow_request"]["evidence"]:
                    self.assertNotIn(evidence["text"], audit_json)


if __name__ == "__main__":
    unittest.main()
