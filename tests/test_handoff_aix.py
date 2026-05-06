import unittest

from eval_pipeline.handoff_aix import calculate_handoff_aix
from eval_pipeline.handoff_gate import handoff_gate
from eval_pipeline.mi_boundary_gate import mi_boundary_gate
from tests.test_handoff_gate import clean_handoff


class HandoffAixTests(unittest.TestCase):
    def test_calculates_handoff_aix_for_exchanged_message(self):
        handoff = clean_handoff()
        result = handoff_gate(handoff)
        handoff_aix = result["handoff_aix"]

        self.assertEqual(handoff_aix["handoff_aix_version"], "0.1")
        self.assertEqual(handoff_aix["handoff_id"], handoff["handoff_id"])
        self.assertEqual(handoff_aix["sender_id"], "research_agent")
        self.assertEqual(handoff_aix["recipient_id"], "publication_checker")
        self.assertEqual(set(handoff_aix["components"]), {"P", "B", "C", "F"})
        self.assertEqual(handoff_aix["verifier_components"]["P"], 1.0)
        self.assertEqual(handoff_aix["verifier_components"]["B"], 0.95)
        self.assertEqual(handoff_aix["verifier_components"]["C"], 1.0)
        self.assertEqual(handoff_aix["verifier_components"]["F"], 1.0)
        self.assertEqual(handoff_aix["decision"], "accept")

    def test_direct_helper_matches_gate_handoff_aix_score(self):
        handoff = clean_handoff()
        result = handoff_gate(handoff)
        direct = calculate_handoff_aix(
            handoff,
            constraint_results=result["constraint_results"],
            violations=result["violations"],
            gate_decision=result["gate_decision"],
            recommended_action=result["recommended_action"],
        )

        self.assertEqual(direct["score"], result["handoff_aix"]["score"])
        self.assertEqual(direct["message_fingerprint"], result["handoff_aix"]["message_fingerprint"])

    def test_failed_handoff_aix_tracks_failed_layer(self):
        handoff = clean_handoff()
        handoff["verifier_scores"]["C"] = {
            "score": 0.1,
            "status": "fail",
            "confidence": 0.95,
            "verifier_ids": ["source_policy"],
        }

        result = handoff_gate(handoff)

        self.assertEqual(result["handoff_aix"]["verifier_components"]["C"], 0.1)
        self.assertEqual(result["handoff_aix"]["verifier_statuses"]["C"], "fail")
        self.assertIn("use-approved-sources", result["handoff_aix"]["hard_blockers"])

    def test_mi_boundary_gate_preserves_handoff_aix(self):
        handoff = clean_handoff()
        handoff["sender"]["type"] = "agent"
        handoff["recipient"]["type"] = "tool"

        result = mi_boundary_gate(handoff)

        self.assertEqual(result["boundary_type"], "agent_to_tool")
        self.assertIn("handoff_aix", result)
        self.assertEqual(result["handoff_aix"]["components"]["P"], 1.0)


if __name__ == "__main__":
    unittest.main()
