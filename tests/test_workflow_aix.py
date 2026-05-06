import unittest

from eval_pipeline.mi_boundary_gate import mi_boundary_batch, mi_boundary_gate
from eval_pipeline.workflow_aix import calculate_workflow_aix
from tests.test_handoff_gate import clean_handoff


def scored_result(handoff_id, score, *, p=None, b=None, c=None, f=None):
    components = {
        "P": score if p is None else p,
        "B": score if b is None else b,
        "C": score if c is None else c,
        "F": score if f is None else f,
    }
    return {
        "handoff_id": handoff_id,
        "gate_decision": "pass",
        "recommended_action": "accept",
        "handoff_aix": {
            "handoff_aix_version": "0.1",
            "handoff_id": handoff_id,
            "score": score,
            "components": components,
            "decision": "accept",
            "hard_blockers": [],
        },
    }


class WorkflowAixTests(unittest.TestCase):
    def test_aggregates_handoff_scores_into_workflow_state(self):
        result = calculate_workflow_aix(
            [
                scored_result("h1", 0.9, p=1.0, b=0.8, c=0.9, f=0.9),
                scored_result("h2", 0.86, p=0.86, b=0.86, c=0.86, f=0.86),
            ],
            workflow_id="workflow-001",
        )

        self.assertEqual(result["workflow_aix_version"], "0.1")
        self.assertEqual(result["workflow_id"], "workflow-001")
        self.assertEqual(result["handoff_count"], 2)
        self.assertEqual(result["score"], 0.88)
        self.assertEqual(result["components"]["P"], 0.93)
        self.assertEqual(result["components"]["B"], 0.83)
        self.assertEqual(result["decision"], "accept")
        self.assertFalse(result["drift_detected"])

    def test_detects_global_drift_when_all_local_handoffs_pass(self):
        result = calculate_workflow_aix(
            [
                scored_result("h1", 0.95),
                scored_result("h2", 0.89),
                scored_result("h3", 0.8),
            ],
            thresholds={"drift": 0.1},
        )

        self.assertTrue(result["local_all_pass"])
        self.assertTrue(result["drift_detected"])
        self.assertEqual(result["decision"], "defer")
        self.assertEqual(result["recommended_action"], "defer")
        self.assertEqual(result["score_drift"]["delta"], -0.15)

    def test_hard_blocker_overrides_aggregate_score(self):
        h1 = scored_result("h1", 0.95)
        h1["handoff_aix"]["hard_blockers"] = ["privacy"]

        result = calculate_workflow_aix([h1, scored_result("h2", 0.95)])

        self.assertEqual(result["decision"], "refuse")
        self.assertEqual(result["recommended_action"], "refuse")
        self.assertIn("privacy", result["hard_blockers"])

    def test_mi_boundary_batch_emits_workflow_and_global_aix(self):
        h1 = clean_handoff()
        h1["handoff_id"] = "h1"
        h1["sender"]["type"] = "agent"
        h1["recipient"]["type"] = "tool"
        h2 = clean_handoff()
        h2["handoff_id"] = "h2"
        h2["sender"]["type"] = "tool"
        h2["recipient"]["type"] = "agent"

        batch = mi_boundary_batch([h1, h2])

        self.assertIn("workflow_aix", batch)
        self.assertIn("global_aix", batch)
        self.assertEqual(batch["workflow_aix"], batch["global_aix"])
        self.assertEqual(batch["workflow_aix"]["handoff_count"], 2)
        self.assertEqual(batch["summary"]["workflow_aix_decision"], "accept")

    def test_boundary_result_can_feed_workflow_aix(self):
        handoff = clean_handoff()
        handoff["sender"]["type"] = "agent"
        handoff["recipient"]["type"] = "tool"

        boundary_result = mi_boundary_gate(handoff)
        workflow = calculate_workflow_aix([boundary_result])

        self.assertEqual(workflow["handoff_count"], 1)
        self.assertEqual(workflow["handoff_scores"][0]["handoff_id"], handoff["handoff_id"])


if __name__ == "__main__":
    unittest.main()
