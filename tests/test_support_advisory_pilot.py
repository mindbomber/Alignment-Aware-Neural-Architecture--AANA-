import json
import pathlib
import tempfile
import unittest

from eval_pipeline import audit
from scripts import run_support_advisory_pilot


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SupportAdvisoryPilotTests(unittest.TestCase):
    def test_advisory_pilot_runs_support_fixtures_and_writes_review_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            args = run_support_advisory_pilot.parse_args(
                [
                    "--audit-log",
                    str(temp_root / "audit" / "advisory.jsonl"),
                    "--metrics-output",
                    str(temp_root / "metrics.json"),
                    "--reviewer-report",
                    str(temp_root / "review.md"),
                    "--output",
                    str(temp_root / "results.json"),
                ]
            )

            result = run_support_advisory_pilot.run_advisory_pilot(args)

            self.assertEqual(result["measurement_status"], "accepted", result)
            self.assertEqual(result["execution_mode"], "advisory")
            self.assertEqual(result["enforcement"], "human_decides")
            self.assertGreater(result["summary"]["total_checks"], 0)
            self.assertEqual(result["metrics"]["reviewer_agreement_rate"], 1.0)
            self.assertEqual(result["metrics"]["reviewer_disagreement_count"], 0)
            self.assertEqual(result["metrics"]["false_blocker_count"], 0)
            self.assertEqual(result["metrics"]["missed_unsafe_count"], 0)
            self.assertGreater(result["metrics"]["human_decision_load"], 0)
            self.assertTrue(result["support_aix_calibration"]["valid"])
            self.assertIn("threshold_tuning_recommendations", result)
            self.assertTrue((temp_root / "audit" / "advisory.jsonl").exists())
            self.assertTrue((temp_root / "metrics.json").exists())
            self.assertTrue((temp_root / "review.md").exists())
            self.assertTrue((temp_root / "results.json").exists())

            record = json.loads((temp_root / "audit" / "advisory.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["execution_mode"], "advisory")
            self.assertEqual(record["advisory_review"]["enforcement"], "human_decides")
            self.assertFalse(audit.validate_audit_record(record)["errors"])

    def test_advisory_pilot_result_is_default_measured_artifact_shape(self):
        self.assertEqual(
            pathlib.Path(run_support_advisory_pilot.DEFAULT_OUTPUT),
            ROOT / "eval_outputs" / "pilots" / "support-advisory-internal-pilot-results.json",
        )
        self.assertEqual(
            pathlib.Path(run_support_advisory_pilot.DEFAULT_AUDIT_LOG),
            ROOT / "eval_outputs" / "audit" / "support-advisory-internal-pilot.jsonl",
        )
        self.assertEqual(
            pathlib.Path(run_support_advisory_pilot.DEFAULT_REVIEWER_DECISIONS),
            ROOT / "examples" / "support_advisory_reviewer_decisions.json",
        )


if __name__ == "__main__":
    unittest.main()
