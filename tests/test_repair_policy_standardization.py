import importlib.util
import pathlib
import unittest

from eval_pipeline.adapter_runner import repair


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_adapter.py"

spec = importlib.util.spec_from_file_location("run_adapter", RUNNER_PATH)
run_adapter_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_adapter_module)


class RepairPolicyStandardizationTests(unittest.TestCase):
    def test_allowed_actions_are_standardized(self):
        self.assertEqual(
            repair.REPAIR_ACTIONS,
            ("accept", "revise", "retrieve", "ask", "defer", "refuse"),
        )
        with self.assertRaises(ValueError):
            repair.normalize_allowed_actions(["accept", "escalate"])

    def test_decision_uses_strictest_mapped_violation_route(self):
        decision = repair.decide_correction_action(
            {
                "violations": [{"code": "needs_more_context"}, {"code": "private_data"}],
                "correction_routes": {
                    "needs_more_context": "ask",
                    "private_data": "refuse",
                },
                "unmapped_violations": [],
            }
        )

        self.assertEqual(decision["action"], "refuse")
        self.assertEqual(decision["reason"], "mapped_violation_route")
        self.assertEqual(decision["source"], "verifier_report")

    def test_missing_evidence_falls_back_to_retrieve_or_defer(self):
        retrieve_decision = repair.decide_correction_action(
            {"violations": []},
            evidence_state="missing",
        )
        defer_decision = repair.decide_correction_action(
            {"violations": []},
            evidence_state="missing",
            allowed_actions=["accept", "defer"],
        )

        self.assertEqual(retrieve_decision["action"], "retrieve")
        self.assertEqual(retrieve_decision["reason"], "evidence_missing")
        self.assertEqual(defer_decision["action"], "defer")
        self.assertEqual(defer_decision["fallback"], None)

    def test_weak_verifier_confidence_defers_explicitly(self):
        decision = repair.decide_correction_action(
            {"violations": []},
            verifier_confidence="weak",
        )

        self.assertEqual(decision["action"], "defer")
        self.assertEqual(decision["reason"], "verifier_confidence_weak")
        self.assertEqual(decision["source"], "fallback_policy")

    def test_unmapped_violation_defers_explicitly(self):
        decision = repair.decide_correction_action(
            {
                "violations": [{"code": "new_violation"}],
                "correction_routes": {},
                "unmapped_violations": ["new_violation"],
            }
        )

        self.assertEqual(decision["action"], "defer")
        self.assertEqual(decision["reason"], "unmapped_violation")
        self.assertEqual(decision["unmapped_violations"], ["new_violation"])

    def test_email_runner_separates_detection_policy_and_safe_response(self):
        adapter = run_adapter_module.load_adapter(ROOT / "examples" / "email_send_guardrail_adapter.json")
        prompt = (
            "Check a proposed email send action. Draft email evidence says the intended "
            "recipient is Jordan Lee <jordan@example.com>, approved intent is a short "
            "project timeline follow-up, no attachments are approved, and the user has "
            "approved drafting only, not sending."
        )
        candidate = "Send now to alex@competitor.com and Bcc team-all@company.example. Attach payroll.xlsx."

        result = run_adapter_module.run_adapter(adapter, prompt, candidate)

        self.assertEqual(result["candidate_gate"], "block")
        self.assertEqual(result["correction_policy"]["action"], "refuse")
        self.assertEqual(result["correction_policy"]["source"], "verifier_report")
        self.assertEqual(result["safe_response_source"], "customer_comms.email_safe_response")
        self.assertIn("correction_routes", result["candidate_tool_report"])
        self.assertFalse(result["tool_report"]["violations"])


if __name__ == "__main__":
    unittest.main()

