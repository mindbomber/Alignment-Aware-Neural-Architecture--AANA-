import copy
import unittest

from eval_pipeline.mi_boundary_gate import mi_boundary_batch
from eval_pipeline.propagated_risk import track_propagated_risk
from tests.test_handoff_gate import clean_handoff


def clean_result():
    return {
        "handoff_id": "handoff-1",
        "sender": {"id": "sender", "type": "agent"},
        "recipient": {"id": "recipient", "type": "agent"},
        "gate_decision": "pass",
        "recommended_action": "accept",
        "message": {
            "summary": "Supported handoff.",
            "claims": ["Claim A"],
            "assumptions": [
                {
                    "id": "assumption-a",
                    "description": "Assumption A is supported.",
                    "support_status": "supported",
                }
            ],
            "payload_redaction_status": "redacted",
        },
        "evidence_summary": [
            {
                "source_id": "source-a",
                "trust_tier": "verified",
                "redaction_status": "redacted",
                "retrieval_url": "aana://source-a",
                "supports": ["Claim A"],
                "metadata": {"freshness_status": "fresh"},
            }
        ],
        "violations": [],
    }


class PropagatedRiskTests(unittest.TestCase):
    def test_detects_hidden_assumption(self):
        result = clean_result()
        result["message"]["assumptions"][0]["support_status"] = "unknown"

        tracked = track_propagated_risk([result])

        self.assertEqual(tracked["risk_counts"]["hidden_assumption"], 1)
        self.assertTrue(tracked["has_propagated_risk"])

    def test_detects_unsupported_claim(self):
        result = clean_result()
        result["message"]["claims"] = ["Claim B"]

        tracked = track_propagated_risk([result])

        self.assertEqual(tracked["risk_counts"]["unsupported_claim"], 1)
        self.assertEqual(tracked["risks"][0]["severity"], "medium")

    def test_detects_stale_evidence(self):
        result = clean_result()
        result["evidence_summary"][0]["metadata"]["freshness_status"] = "stale"

        tracked = track_propagated_risk([result])

        self.assertEqual(tracked["risk_counts"]["stale_evidence"], 1)
        self.assertEqual(tracked["risks"][0]["source"], "source-a")

    def test_detects_accepted_violation(self):
        result = clean_result()
        result["violations"] = [
            {
                "code": "soft_policy_violation",
                "id": "soft_policy_violation",
                "severity": "medium",
                "message": "Accepted with a known policy violation.",
            }
        ]

        tracked = track_propagated_risk([result])

        self.assertEqual(tracked["risk_counts"]["accepted_violation"], 1)
        self.assertEqual(tracked["risks"][0]["source"], "soft_policy_violation")

    def test_marks_uncertain_output_as_downstream_premise(self):
        upstream = clean_result()
        upstream["handoff_id"] = "h1"
        upstream["message"]["assumptions"][0]["support_status"] = "unknown"
        downstream = clean_result()
        downstream["handoff_id"] = "h2"
        downstream["message"]["assumptions"] = [
            {
                "id": "premise-from-h1",
                "description": "Downstream step relies on h1 output.",
                "support_status": "supported",
                "source_handoff_id": "h1",
            }
        ]

        tracked = track_propagated_risk([upstream, downstream])

        self.assertEqual(tracked["propagation_count"], 1)
        link = tracked["propagation_links"][0]
        self.assertEqual(link["kind"], "uncertain_output_became_premise")
        self.assertEqual(link["source_handoff_id"], "h1")
        self.assertEqual(link["downstream_handoff_id"], "h2")

    def test_boundary_batch_includes_propagated_risk(self):
        handoff = copy.deepcopy(clean_handoff())
        handoff["metadata"]["boundary_type"] = "agent_to_tool"
        handoff["message"]["assumptions"][0]["support_status"] = "unknown"

        result = mi_boundary_batch([handoff])

        self.assertIn("propagated_risk", result)
        self.assertEqual(result["summary"]["propagated_risk_count"], 1)
        self.assertTrue(result["summary"]["has_propagated_risk"])


if __name__ == "__main__":
    unittest.main()
