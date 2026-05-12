import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import aana
from eval_pipeline import mlcflow_aana_step


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MLCFlowAANAStepTests(unittest.TestCase):
    def test_step_generates_manifest_for_modelbench_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            result = mlcflow_aana_step.run_mlcflow_aana_step(
                results_path=ROOT / "examples" / "mlcommons_modelbench_journal_actual.jsonl",
                source_type="modelbench",
                output_dir=directory,
            )

            self.assertTrue(result["valid"], result)
            self.assertEqual(result["step_status"], "pass")
            self.assertEqual(result["hard_blockers"], [])
            self.assertTrue(pathlib.Path(result["manifest_path"]).exists())
            self.assertTrue(result["manifest_validation"]["valid"], result["manifest_validation"])
            self.assertEqual(len(result["manifest"]["artifacts"]), 4)
            self.assertTrue(all(artifact["sha256"] for artifact in result["manifest"]["artifacts"]))

    def test_step_fails_when_hard_blockers_exist(self):
        blocker_artifact = {
            "benchmark": "AILuminate blocker sample",
            "hazard_scores": [
                {"hazard_uid": "prv", "score": 0.98, "violation_rate": 0.04, "samples": 10},
                {"hazard_uid": "spc_med", "score": 0.97, "violation_rate": 0.03, "samples": 10},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            artifact_path = pathlib.Path(directory) / "blocker-results.json"
            artifact_path.write_text(json.dumps(blocker_artifact), encoding="utf-8")
            result = mlcflow_aana_step.run_mlcflow_aana_step(
                results_path=artifact_path,
                source_type="ailuminate",
                output_dir=pathlib.Path(directory) / "out",
            )

            self.assertFalse(result["valid"])
            self.assertEqual(result["step_status"], "fail")
            self.assertIn("hard_blockers_present", result["fail_reasons"])
            self.assertIn("privacy_violation", result["hard_blockers"])
            self.assertTrue(result["manifest_validation"]["valid"], result["manifest_validation"])

    def test_step_warns_on_insufficient_evidence_without_hard_blockers(self):
        with tempfile.TemporaryDirectory() as directory:
            result = mlcflow_aana_step.run_mlcflow_aana_step(
                results_path=ROOT / "examples" / "mlcommons_ailuminate_prompt_set_sample.csv",
                source_type="ailuminate",
                output_dir=directory,
            )

            self.assertTrue(result["valid"], result)
            self.assertEqual(result["step_status"], "warn")
            self.assertIn("insufficient_evidence", result["fail_reasons"])
            self.assertEqual(result["hard_blockers"], [])

    def test_optional_benchmark_command_failure_fails_step(self):
        with tempfile.TemporaryDirectory() as directory:
            result = mlcflow_aana_step.run_mlcflow_aana_step(
                results_path=ROOT / "examples" / "mlcommons_modelbench_journal_actual.jsonl",
                source_type="modelbench",
                output_dir=directory,
                benchmark_command=f"{sys.executable} -c \"import sys; sys.exit(7)\"",
            )

            self.assertFalse(result["valid"])
            self.assertEqual(result["step_status"], "fail")
            self.assertIn("benchmark_command_failed", result["fail_reasons"])
            self.assertEqual(result["manifest"]["benchmark_result"]["returncode"], 7)

    def test_cli_runs_mlcflow_step(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/aana_cli.py",
                    "mlcflow-aana-step",
                    "--results",
                    "examples/mlcommons_modelbench_journal_actual.jsonl",
                    "--source-type",
                    "modelbench",
                    "--output-dir",
                    directory,
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["step_status"], "pass")
            self.assertTrue(pathlib.Path(payload["manifest_path"]).exists())

    def test_python_sdk_exports_mlcflow_helpers(self):
        self.assertTrue(callable(aana.run_mlcflow_aana_step))
        self.assertTrue(callable(aana.validate_mlcflow_step_manifest))
        self.assertEqual(aana.MLCFLOW_AANA_STEP_VERSION, mlcflow_aana_step.MLCFLOW_AANA_STEP_VERSION)


if __name__ == "__main__":
    unittest.main()
