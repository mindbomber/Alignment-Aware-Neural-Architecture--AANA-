import unittest

from eval_pipeline import aix


class AixTests(unittest.TestCase):
    def test_calculate_aix_accepts_clean_pass(self):
        result = aix.calculate_aix(
            constraint_results=[
                {"id": "facts", "layer": "P", "hard": True, "status": "pass"},
                {"id": "privacy", "layer": "B", "hard": True, "status": "pass"},
                {"id": "policy", "layer": "C", "hard": True, "status": "pass"},
                {"id": "tone", "layer": "F", "hard": False, "status": "pass"},
            ],
            tool_report={"violations": []},
            gate_decision="pass",
            recommended_action="accept",
        )

        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["decision"], "accept")
        self.assertFalse(result["hard_blockers"])

    def test_hard_blocker_prevents_accept(self):
        result = aix.calculate_aix(
            constraint_results=[
                {"id": "privacy", "layer": "B", "hard": True, "status": "fail"},
                {"id": "tone", "layer": "F", "hard": False, "status": "pass"},
            ],
            tool_report={
                "violations": [
                    {"code": "private_data", "severity": "high"},
                ]
            },
            gate_decision="block",
            recommended_action="revise",
        )

        self.assertLess(result["score"], result["thresholds"]["accept"])
        self.assertIn("privacy", result["hard_blockers"])
        self.assertNotEqual(result["decision"], "accept")

    def test_adapter_config_controls_beta_and_thresholds(self):
        result = aix.calculate_aix(
            adapter={
                "aix": {
                    "beta": 2.0,
                    "thresholds": {"accept": 0.9, "revise": 0.7, "defer": 0.4},
                }
            },
            constraint_results=[
                {"id": "facts", "layer": "P", "hard": True, "status": "pass"},
            ],
            tool_report={"violations": [{"code": "unsupported", "severity": "medium"}]},
            gate_decision="block",
            recommended_action="revise",
        )

        self.assertEqual(result["beta"], 2.0)
        self.assertEqual(result["thresholds"]["accept"], 0.9)
        self.assertEqual(result["score"], 0.7)
        self.assertEqual(result["decision"], "revise")


if __name__ == "__main__":
    unittest.main()
