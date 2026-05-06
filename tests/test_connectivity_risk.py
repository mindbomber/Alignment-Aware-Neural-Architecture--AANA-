import unittest

from eval_pipeline.connectivity_risk import (
    assess_connectivity_risk,
    risk_tier_rules,
    tier_for_connectivity,
)
from eval_pipeline.workflow_aix import calculate_workflow_aix
from tests.test_workflow_aix import scored_result


class ConnectivityRiskTests(unittest.TestCase):
    def test_tier_for_connectivity(self):
        self.assertEqual(tier_for_connectivity(0), "low")
        self.assertEqual(tier_for_connectivity(2), "elevated")
        self.assertEqual(tier_for_connectivity(4), "high")
        self.assertEqual(tier_for_connectivity(6), "strict")
        self.assertEqual(tier_for_connectivity(1, irreversible=True), "strict")

    def test_risk_tier_rules_expose_all_mi_workflow_tiers(self):
        rules = risk_tier_rules()

        self.assertEqual(rules["principle"], "C_global >= D_global")
        self.assertEqual(set(rules["tiers"]), {"low", "elevated", "high", "strict"})
        self.assertGreater(rules["tiers"]["strict"]["thresholds"]["accept"], rules["tiers"]["low"]["thresholds"]["accept"])
        self.assertGreater(rules["tiers"]["strict"]["required_correction_capacity"], rules["tiers"]["low"]["required_correction_capacity"])

    def test_assesses_declared_or_inferred_tier(self):
        result = scored_result("h1", 0.98)
        result["metadata"] = {"connectivity": 4}

        risk = assess_connectivity_risk([result])

        self.assertEqual(risk["risk_tier"], "high")
        self.assertEqual(risk["max_connectivity"], 4)
        self.assertFalse(risk["capacity_sufficient"])
        self.assertEqual(risk["capacity_gap"], 2)

    def test_irreversible_workflow_uses_strict_thresholds_and_defers_capacity_gap(self):
        result = scored_result("h1", 0.95)
        result["metadata"] = {"irreversible": True}

        workflow = calculate_workflow_aix([result])

        self.assertEqual(workflow["risk_tier"], "strict")
        self.assertEqual(workflow["connectivity_risk"]["required_correction_capacity"], 4)
        self.assertFalse(workflow["connectivity_risk"]["capacity_sufficient"])
        self.assertEqual(workflow["thresholds"]["accept"], 0.96)
        self.assertEqual(workflow["recommended_action"], "defer")
        self.assertIn("insufficient_correction_capacity", workflow["hard_blockers"])

    def test_strict_workflow_can_accept_when_capacity_and_score_clear_threshold(self):
        results = []
        for index in range(4):
            result = scored_result(f"h{index}", 0.98)
            result["metadata"] = {"mi_risk_tier": "strict", "connectivity": 6}
            results.append(result)

        workflow = calculate_workflow_aix(results)

        self.assertEqual(workflow["risk_tier"], "strict")
        self.assertTrue(workflow["connectivity_risk"]["capacity_sufficient"])
        self.assertEqual(workflow["decision"], "accept")
        self.assertEqual(workflow["recommended_action"], "accept")


if __name__ == "__main__":
    unittest.main()
