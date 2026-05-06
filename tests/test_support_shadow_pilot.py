import json
import pathlib
import tempfile
import unittest

from scripts import run_support_shadow_pilot


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SupportShadowPilotTests(unittest.TestCase):
    def test_shadow_pilot_runs_support_fixtures_and_writes_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            args = run_support_shadow_pilot.parse_args(
                [
                    "--audit-log",
                    str(temp_root / "audit" / "shadow.jsonl"),
                    "--metrics-output",
                    str(temp_root / "metrics.json"),
                    "--reviewer-report",
                    str(temp_root / "review.md"),
                    "--output",
                    str(temp_root / "results.json"),
                ]
            )

            result = run_support_shadow_pilot.run_shadow_pilot(args)

            self.assertEqual(result["measurement_status"], "accepted", result)
            self.assertEqual(result["execution_mode"], "shadow")
            self.assertEqual(result["enforcement"], "observe_only")
            self.assertGreater(result["summary"]["total_checks"], 0)
            self.assertGreater(result["would_metrics"]["would_block"], 0)
            self.assertIn("would_ask", result["would_metrics"])
            self.assertIn("would_defer", result["would_metrics"])
            self.assertIn("would_refuse", result["would_metrics"])
            self.assertEqual(result["metrics"]["over_acceptance_count"], 0)
            self.assertEqual(result["metrics"]["over_refusal_count"], 0)
            self.assertGreaterEqual(result["metrics"]["correction_success_rate"], 1.0)
            self.assertTrue((temp_root / "audit" / "shadow.jsonl").exists())
            self.assertTrue((temp_root / "metrics.json").exists())
            self.assertTrue((temp_root / "review.md").exists())
            self.assertTrue((temp_root / "results.json").exists())

            record = json.loads((temp_root / "audit" / "shadow.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["execution_mode"], "shadow")
            self.assertEqual(record["shadow_observation"]["enforcement"], "observe_only")

    def test_shadow_pilot_result_is_default_measured_artifact_shape(self):
        self.assertEqual(
            pathlib.Path(run_support_shadow_pilot.DEFAULT_OUTPUT),
            ROOT / "eval_outputs" / "pilots" / "support-shadow-internal-pilot-results.json",
        )
        self.assertEqual(
            pathlib.Path(run_support_shadow_pilot.DEFAULT_AUDIT_LOG),
            ROOT / "eval_outputs" / "audit" / "support-shadow-internal-pilot.jsonl",
        )


if __name__ == "__main__":
    unittest.main()
