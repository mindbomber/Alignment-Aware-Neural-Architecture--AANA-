import json
import pathlib
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FinanceHighRiskQaHFExperimentTests(unittest.TestCase):
    def test_experiment_manifest_uses_registered_heldout_split(self):
        from eval_pipeline.hf_dataset_registry import load_registry
        from scripts.hf.run_finance_high_risk_qa_hf_experiment import DEFAULT_EXPERIMENT, DEFAULT_REGISTRY, _load_json, validate_experiment

        experiment = _load_json(DEFAULT_EXPERIMENT)
        registry = load_registry(DEFAULT_REGISTRY)

        self.assertEqual(validate_experiment(experiment, registry), [])
        self.assertEqual(experiment["adapter_family"], "finance_high_risk_qa")
        self.assertEqual(experiment["split_policy"]["calibration_splits"], [])
        self.assertIn("PatronusAI/financebench default/train", experiment["split_policy"]["heldout_validation_splits"])

    def test_fixture_mode_reports_finance_metrics_without_raw_text(self):
        output = ROOT / "eval_outputs" / "finance_high_risk_qa_hf_experiment_results.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/hf/run_finance_high_risk_qa_hf_experiment.py",
                "--mode",
                "fixture",
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["experiment_id"], "finance_high_risk_qa_v1_hf_diagnostic")
        self.assertIn("base_accept_blindly", payload["comparisons"])
        self.assertIn("aana_revise_defer_route", payload["comparisons"])
        self.assertEqual(payload["metrics"]["unsupported_finance_claim_recall"], 1.0)
        self.assertEqual(payload["metrics"]["supported_answer_safe_allow_rate"], 1.0)

        serialized = json.dumps(payload)
        self.assertNotIn("Revenue was 10 million", serialized)
        self.assertNotIn("investors should buy", serialized)
        first_row = payload["rows"][0]
        self.assertIn("question_sha256", first_row)
        self.assertIn("evidence_sha256", first_row)
        self.assertNotIn("prompt", first_row)
        self.assertNotIn("answer", first_row)
        self.assertFalse(first_row["raw_text_logged"])


if __name__ == "__main__":
    unittest.main()
