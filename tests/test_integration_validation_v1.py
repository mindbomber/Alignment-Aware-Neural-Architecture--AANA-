import json
import pathlib
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class IntegrationValidationV1Tests(unittest.TestCase):
    def test_heldout_cases_are_marked_no_tuning(self):
        payload = json.loads((ROOT / "examples" / "integration_validation_v1_heldout_cases.json").read_text(encoding="utf-8"))

        self.assertTrue(payload["split_policy"]["no_tuning_on_these_cases"])
        self.assertEqual(payload["split_policy"]["allowed_use"], "heldout_validation")
        self.assertGreaterEqual(len(payload["cases"]), 8)
        self.assertTrue(any(case["source_schema"].startswith("mcp") for case in payload["cases"]))
        self.assertTrue(any("hermes" in case["source_schema"] for case in payload["cases"]))
        self.assertTrue(any("qwen" in case["source_schema"] for case in payload["cases"]))

    def test_smoke_run_checks_all_surfaces_without_raw_payloads(self):
        output = ROOT / "eval_outputs" / "integration_validation_v1_heldout_results.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_integration_validation_v1.py",
                "--case-limit",
                "2",
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=180,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(output.read_text(encoding="utf-8"))
        metrics = payload["metrics"]
        self.assertEqual(payload["experiment_id"], "integration_validation_v1_heldout")
        self.assertEqual(metrics["route_parity"], 1.0)
        self.assertEqual(metrics["route_accuracy"], 1.0)
        self.assertEqual(metrics["decision_shape_parity"], 1.0)
        self.assertEqual(metrics["blocked_tool_non_execution"], 1.0)
        self.assertEqual(metrics["schema_failure_rate"], 0.0)
        self.assertGreaterEqual(metrics["fastapi_audit_coverage"], 1.0)
        self.assertEqual(metrics["surface_count"], 11)

        serialized = json.dumps(payload)
        self.assertIn("argument_value_sha256", serialized)
        self.assertNotIn("Agent Action Contract v1", serialized)
        self.assertNotIn("cust_redacted", serialized)
        self.assertTrue(all(row["raw_payload_logged"] is False for row in payload["rows"]))


if __name__ == "__main__":
    unittest.main()
