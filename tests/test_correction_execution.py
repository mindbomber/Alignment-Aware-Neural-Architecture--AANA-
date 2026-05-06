import copy
import unittest

from eval_pipeline.correction_execution import CORRECTION_EXECUTION_LOOP_VERSION, execute_correction_loop
from tests.test_handoff_gate import clean_handoff


def retrieved_source_a():
    return {
        "source_id": "source-a",
        "retrieved_at": "2026-05-05T00:00:00Z",
        "trust_tier": "verified",
        "redaction_status": "redacted",
        "text": "Source A supports the narrow claim.",
        "retrieval_url": "aana://evidence/source-a",
        "supports": ["Source A supports the narrow claim."],
    }


class CorrectionExecutionTests(unittest.TestCase):
    def test_executes_retrieve_route_and_improves_after_rerun(self):
        handoff = copy.deepcopy(clean_handoff())
        handoff["metadata"]["boundary_type"] = "agent_to_tool"
        handoff["evidence"] = []

        result = execute_correction_loop(
            [handoff],
            route="retrieve",
            retrieved_evidence=retrieved_source_a(),
        )

        comparison = result["aix_comparison"]
        self.assertEqual(result["correction_execution_loop_version"], CORRECTION_EXECUTION_LOOP_VERSION)
        self.assertTrue(result["executed"])
        self.assertEqual(result["route"], "retrieve_evidence")
        self.assertEqual(result["execution_details"]["added_source_ids"], ["source-a"])
        self.assertEqual(comparison["before_recommended_action"], "retrieve")
        self.assertEqual(comparison["after_recommended_action"], "accept")
        self.assertGreater(comparison["target_after_score"], comparison["target_before_score"])
        self.assertEqual(result["after"]["results"][0]["gate_decision"], "pass")

    def test_executes_revise_upstream_output_and_compares_aix(self):
        handoff = copy.deepcopy(clean_handoff())
        handoff["metadata"]["boundary_type"] = "agent_to_agent"
        handoff["recipient"] = {"id": "review_agent", "type": "agent", "trust_tier": "system"}
        handoff["verifier_scores"]["C"] = {
            "score": 0.1,
            "status": "fail",
            "confidence": 0.95,
            "verifier_ids": ["source_policy"],
        }

        result = execute_correction_loop([handoff], route="revise_upstream_output")

        comparison = result["aix_comparison"]
        self.assertTrue(result["executed"])
        self.assertEqual(result["route"], "revise_upstream_output")
        self.assertEqual(comparison["before_recommended_action"], "revise")
        self.assertEqual(comparison["after_recommended_action"], "accept")
        self.assertGreater(comparison["target_after_score"], comparison["target_before_score"])
        self.assertEqual(result["corrected_handoffs"][0]["verifier_scores"]["C"]["status"], "pass")

    def test_noop_when_no_executable_route_exists(self):
        handoff = copy.deepcopy(clean_handoff())
        handoff["metadata"]["boundary_type"] = "agent_to_tool"

        result = execute_correction_loop([handoff])

        self.assertFalse(result["executed"])
        self.assertEqual(result["reason"], "No executable correction route was available.")
        self.assertEqual(result["before"]["summary"]["recommended_actions"]["accept"], 1)


if __name__ == "__main__":
    unittest.main()
