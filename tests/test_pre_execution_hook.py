import unittest

from eval_pipeline.pre_execution_hook import (
    PRE_EXECUTION_DECISIONS,
    PRE_EXECUTION_HOOK_VERSION,
    pre_execution_hook,
)


def clean_batch():
    return {
        "results": [
            {
                "handoff_id": "release-agent-to-deploy-gate",
                "gate_decision": "pass",
                "recommended_action": "accept",
                "evidence_summary": [{"source_id": "ci", "trust_tier": "verified"}],
                "aix": {"score": 0.97, "decision": "accept", "hard_blockers": []},
                "handoff_aix": {"score": 0.97, "decision": "accept", "hard_blockers": []},
            }
        ],
        "global_aix": {
            "score": 0.97,
            "decision": "accept",
            "recommended_action": "accept",
            "risk_tier": "high",
            "thresholds": {"accept": 0.93, "revise": 0.75, "defer": 0.6},
            "hard_blockers": [],
        },
        "propagated_risk": {
            "risk_count": 0,
            "propagation_count": 0,
            "has_propagated_risk": False,
        },
    }


class PreExecutionHookTests(unittest.TestCase):
    def test_allows_clean_high_risk_batch(self):
        result = pre_execution_hook(
            action_type="deployment.release",
            handoff_batch=clean_batch(),
            risk_tier="high",
        )

        self.assertEqual(result["pre_execution_hook_version"], PRE_EXECUTION_HOOK_VERSION)
        self.assertIn(result["decision"], PRE_EXECUTION_DECISIONS)
        self.assertEqual(result["decision"], "allow")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["production_mi_readiness"]["release_status"], "ready")

    def test_retrieves_when_evidence_is_missing(self):
        batch = clean_batch()
        batch["results"][0]["evidence_summary"] = []

        result = pre_execution_hook(action_type="deployment.release", handoff_batch=batch)

        self.assertEqual(result["decision"], "retrieve")
        self.assertFalse(result["allowed"])
        self.assertIn("evidence-present", result["blockers"])

    def test_blocks_when_hard_blockers_exist(self):
        batch = clean_batch()
        batch["global_aix"]["hard_blockers"] = ["deployment_without_approval"]

        result = pre_execution_hook(action_type="deployment.release", handoff_batch=batch)

        self.assertEqual(result["decision"], "block")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["recommended_action"], "refuse")
        self.assertIn("deployment_without_approval", result["hard_blockers"])

    def test_revises_when_propagated_risk_is_unresolved(self):
        batch = clean_batch()
        batch["propagated_risk"] = {
            "risk_count": 1,
            "propagation_count": 1,
            "has_propagated_risk": True,
        }

        result = pre_execution_hook(action_type="research.publish", handoff_batch=batch)

        self.assertEqual(result["decision"], "revise")
        self.assertFalse(result["allowed"])
        self.assertIn("propagation-resolved", result["blockers"])

    def test_defers_when_mi_checks_are_missing(self):
        result = pre_execution_hook(action_type="file.write", handoff_batch={})

        self.assertEqual(result["decision"], "defer")
        self.assertFalse(result["allowed"])
        self.assertIn("mi-checks-present", result["blockers"])

    def test_injects_evidence_into_batch_before_readiness_check(self):
        batch = clean_batch()
        batch["results"][0].pop("evidence_summary")
        evidence = {"source_id": "release-ticket", "trust_tier": "verified"}

        result = pre_execution_hook(
            action_type="deployment.release",
            handoff_batch=batch,
            evidence=evidence,
            risk_tier="high",
        )

        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["evidence_count"], 1)
        self.assertNotIn("evidence-present", result["blockers"])

    def test_accepts_wrapped_mi_batch_payload(self):
        result = pre_execution_hook(
            action_type="deployment.release",
            handoff_batch={"mi_batch": clean_batch()},
        )

        self.assertEqual(result["decision"], "allow")
        self.assertTrue(result["allowed"])

    def test_strict_risk_tier_raises_accept_threshold(self):
        batch = clean_batch()
        batch["global_aix"]["score"] = 0.95

        result = pre_execution_hook(
            action_type="deployment.release",
            handoff_batch=batch,
            risk_tier="strict",
        )

        self.assertEqual(result["decision"], "defer")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["production_mi_readiness"]["global_aix"]["accept_threshold"], 0.96)


if __name__ == "__main__":
    unittest.main()
