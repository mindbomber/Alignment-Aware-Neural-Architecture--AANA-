import copy
import unittest

from eval_pipeline.mi_boundary_gate import mi_boundary_batch
from eval_pipeline.shared_correction import shared_correction_policy
from tests.test_handoff_gate import clean_handoff
from tests.test_propagated_risk import clean_result


class SharedCorrectionPolicyTests(unittest.TestCase):
    def test_stale_evidence_triggers_retrieve(self):
        result = clean_result()
        result["evidence_summary"][0]["metadata"]["freshness_status"] = "stale"

        policy = shared_correction_policy([result])

        self.assertEqual(policy["summary"]["action_counts"]["retrieve_evidence"], 1)
        self.assertEqual(policy["actions"][0]["target_handoff_id"], "handoff-1")

    def test_unsupported_claim_triggers_upstream_revision(self):
        result = clean_result()
        result["message"]["claims"] = ["Claim B"]

        policy = shared_correction_policy([result])

        self.assertEqual(policy["summary"]["action_counts"]["revise_upstream_output"], 1)
        self.assertEqual(policy["actions"][0]["target_agent_id"], "sender")

    def test_unknown_assumption_triggers_clarification(self):
        result = clean_result()
        result["message"]["assumptions"][0]["support_status"] = "unknown"

        policy = shared_correction_policy([result])

        self.assertEqual(policy["summary"]["action_counts"]["ask_clarification"], 1)
        self.assertEqual(policy["actions"][0]["requested_by_agent_id"], "recipient")

    def test_capacity_gap_triggers_human_review(self):
        result = clean_result()
        result["metadata"] = {"irreversible": True}

        policy = shared_correction_policy([result])

        self.assertEqual(policy["summary"]["action_counts"]["defer_human_review"], 1)
        self.assertFalse(policy["summary"]["capacity_sufficient"])

    def test_downstream_premise_triggers_upstream_revision(self):
        upstream = clean_result()
        upstream["handoff_id"] = "h1"
        upstream["sender"]["id"] = "research_agent"
        upstream["message"]["assumptions"][0]["support_status"] = "unknown"
        downstream = clean_result()
        downstream["handoff_id"] = "h2"
        downstream["recipient"]["id"] = "publication_agent"
        downstream["message"]["assumptions"] = [
            {
                "id": "premise-from-h1",
                "description": "Publication step relies on h1 output.",
                "support_status": "supported",
                "source_handoff_id": "h1",
            }
        ]

        policy = shared_correction_policy([upstream, downstream])

        revisions = [action for action in policy["actions"] if action["source"] == "uncertain_output_became_premise"]
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0]["action"], "revise_upstream_output")
        self.assertEqual(revisions[0]["target_handoff_id"], "h1")
        self.assertEqual(revisions[0]["requested_by_handoff_id"], "h2")
        self.assertEqual(revisions[0]["target_agent_id"], "research_agent")
        self.assertEqual(revisions[0]["requested_by_agent_id"], "publication_agent")

    def test_boundary_batch_includes_shared_correction_policy(self):
        handoff = copy.deepcopy(clean_handoff())
        handoff["metadata"]["boundary_type"] = "agent_to_tool"
        handoff["evidence"][0]["metadata"] = {"freshness_status": "stale"}

        result = mi_boundary_batch([handoff])

        self.assertIn("shared_correction", result)
        self.assertTrue(result["summary"]["has_network_correction"])
        self.assertGreaterEqual(result["summary"]["shared_correction_action_count"], 1)


if __name__ == "__main__":
    unittest.main()
