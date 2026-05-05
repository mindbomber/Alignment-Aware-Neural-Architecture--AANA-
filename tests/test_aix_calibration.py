import json
import pathlib
import unittest

from eval_pipeline import agent_api, aix


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "aix_calibration_cases.json"


def load_fixtures():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class AixCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = load_fixtures()

    def fixture_case(self, case_id, section="aix_calibration_cases"):
        for item in self.fixtures[section]:
            if item["id"] == case_id:
                return item
        self.fail(f"Missing AIx calibration fixture: {case_id}")

    def calculate_fixture(self, case):
        return aix.calculate_aix(
            adapter=case.get("adapter"),
            constraint_results=case.get("constraint_results"),
            tool_report=case.get("tool_report"),
            gate_decision=case.get("gate_decision"),
            recommended_action=case.get("recommended_action"),
        )

    def test_clean_candidates_score_high(self):
        case = self.fixture_case("clean_candidate_scores_high")

        result = self.calculate_fixture(case)

        self.assertGreaterEqual(result["score"], case["expected"]["min_score"])
        self.assertEqual(result["decision"], case["expected"]["decision"])
        self.assertEqual(result["hard_blockers"], case["expected"]["hard_blockers"])

    def test_hard_blockers_cap_acceptance(self):
        case = self.fixture_case("hard_blocker_caps_acceptance")

        result = self.calculate_fixture(case)

        self.assertLessEqual(result["score"], case["expected"]["max_score"])
        self.assertEqual(result["decision"], case["expected"]["decision"])
        self.assertEqual(result["hard_blockers"], case["expected"]["hard_blockers"])
        self.assertIn("Hard blocker present", " ".join(result["notes"]))

    def test_high_risk_violations_drop_aix_harder_with_beta(self):
        case = self.fixture_case("high_risk_beta_drops_aix_harder")
        baseline = dict(case)
        baseline["adapter"] = case["baseline_adapter"]

        baseline_result = self.calculate_fixture(baseline)
        high_risk_result = self.calculate_fixture(case)

        self.assertGreaterEqual(
            baseline_result["score"] - high_risk_result["score"],
            case["expected"]["score_delta_min"],
        )
        self.assertLessEqual(high_risk_result["score"], case["expected"]["max_score"])
        self.assertGreater(high_risk_result["beta"], baseline_result["beta"])

    def test_candidate_aix_improves_after_repair(self):
        case = self.fixture_case("candidate_aix_improves_after_repair", section="integration_cases")
        event = agent_api.load_json_file(ROOT / case["event_path"])

        result = agent_api.check_event(event)

        self.assertEqual(result["candidate_aix"]["decision"], case["expected"]["candidate_decision"])
        self.assertEqual(result["aix"]["decision"], case["expected"]["final_decision"])
        self.assertGreaterEqual(
            result["aix"]["score"] - result["candidate_aix"]["score"],
            case["expected"]["min_improvement"],
        )

    def test_allowed_action_fallback_blocks_direct_accept(self):
        case = self.fixture_case("allowed_action_fallback_blocks_direct_accept", section="integration_cases")

        result = agent_api.check_workflow_request(case["workflow_request"])

        self.assertEqual(result["recommended_action"], case["expected"]["recommended_action"])
        self.assertIn(case["expected"]["hard_blocker"], result["aix"]["hard_blockers"])
        self.assertLessEqual(result["aix"]["score"], case["expected"]["max_score"])
        self.assertNotEqual(result["aix"]["decision"], "accept")


if __name__ == "__main__":
    unittest.main()
