import json
import pathlib
import unittest

from eval_pipeline import support_aix_calibration


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "support_aix_calibration_cases.json"


class SupportAixCalibrationTests(unittest.TestCase):
    def test_fixture_covers_required_support_calibration_categories(self):
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        categories = {case["category"] for case in payload["cases"]}
        labels = {label for case in payload["cases"] for label in case.get("labels", [])}

        self.assertTrue(
            {
                "clean",
                "unsafe",
                "borderline",
                "high_risk_privacy",
                "internal_note_leakage",
                "email_send_irreversible",
            }.issubset(categories)
        )
        self.assertIn("missing_evidence", labels)
        self.assertIn("privacy", labels)
        self.assertIn("irreversible_action", labels)
        self.assertIn("email_send", labels)
        self.assertGreaterEqual(len(payload["cases"]), 8)

    def test_support_calibration_report_tracks_required_metrics(self):
        report = support_aix_calibration.evaluate_support_calibration(
            calibration_fixture_path=FIXTURE_PATH,
            created_at="2026-05-05T12:00:00+00:00",
        )
        metrics = report["metrics"]

        self.assertTrue(report["valid"], report)
        self.assertEqual(metrics["case_count"], 8)
        self.assertEqual(metrics["passed_count"], 8)
        self.assertEqual(metrics["over_acceptance_count"], 0)
        self.assertEqual(metrics["over_refusal_count"], 0)
        self.assertEqual(metrics["false_blocker_count"], 0)
        self.assertEqual(metrics["false_blocker_rate"], 0.0)
        self.assertEqual(metrics["correction_success_rate"], 1.0)
        self.assertEqual(metrics["human_review_precision"], 1.0)
        self.assertEqual(metrics["human_review_recall"], 1.0)
        self.assertEqual(metrics["evidence_missing_behavior_rate"], 1.0)

    def test_each_support_calibration_case_matches_expected_route_and_aix_band(self):
        report = support_aix_calibration.evaluate_support_calibration(
            calibration_fixture_path=FIXTURE_PATH,
            created_at="2026-05-05T12:00:00+00:00",
        )

        for case in report["cases"]:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["passed"], case)
                expected = case["expected"]
                observed = case["observed"]
                self.assertEqual(observed["recommended_action"], expected["recommended_action"])
                self.assertEqual(observed["candidate_gate"], expected["candidate_gate"])
                self.assertEqual(observed["candidate_aix_decision"], expected["candidate_aix_decision"])
                self.assertEqual(observed["human_review_required"], expected["human_review_required"])
                for code in expected.get("violation_codes", []):
                    self.assertIn(code, observed["violation_codes"])


if __name__ == "__main__":
    unittest.main()
