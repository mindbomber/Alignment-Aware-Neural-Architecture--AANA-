import json
import pathlib
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class GovernanceComplianceHFExperimentTests(unittest.TestCase):
    def test_experiment_manifest_uses_registered_heldout_splits(self):
        from eval_pipeline.hf_dataset_registry import load_registry
        from scripts.run_governance_compliance_hf_experiment import DEFAULT_EXPERIMENT, DEFAULT_REGISTRY, _load_json, validate_experiment

        experiment = _load_json(DEFAULT_EXPERIMENT)
        registry = load_registry(DEFAULT_REGISTRY)

        self.assertEqual(validate_experiment(experiment, registry), [])
        self.assertEqual(experiment["adapter_family"], "governance_compliance")
        self.assertEqual(experiment["split_policy"]["calibration_splits"], [])
        self.assertIn("huggingface/policy-docs default/train", experiment["split_policy"]["heldout_validation_splits"])

    def test_fixture_mode_reports_policy_metrics_without_raw_text(self):
        output = ROOT / "eval_outputs" / "governance_compliance_hf_experiment_results.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_governance_compliance_hf_experiment.py",
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
        self.assertEqual(payload["experiment_id"], "governance_compliance_v1_hf_policy_diagnostic")
        self.assertIn("base_accept_blindly", payload["comparisons"])
        self.assertIn("aana_policy_gate", payload["comparisons"])
        self.assertEqual(payload["metrics"]["risk_route_accuracy"], 1.0)
        self.assertEqual(payload["metrics"]["policy_citation_coverage"], 1.0)

        serialized = json.dumps(payload)
        self.assertNotIn("Model Nova improved internal summarization", serialized)
        self.assertNotIn("safest model", serialized)
        first_row = payload["rows"][0]
        self.assertIn("request_sha256", first_row)
        self.assertIn("candidate_sha256", first_row)
        self.assertNotIn("request", first_row)
        self.assertNotIn("candidate", first_row)
        self.assertFalse(first_row["raw_text_logged"])


if __name__ == "__main__":
    unittest.main()
