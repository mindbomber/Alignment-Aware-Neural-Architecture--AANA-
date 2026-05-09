import json
import pathlib
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PublicPrivateReadRoutingHFExperimentTests(unittest.TestCase):
    def test_manifest_uses_registered_splits(self):
        from eval_pipeline.hf_dataset_registry import load_registry
        from scripts.run_public_private_read_routing_hf_experiment import DEFAULT_EXPERIMENT, DEFAULT_REGISTRY, _load_json, validate_experiment

        experiment = _load_json(DEFAULT_EXPERIMENT)
        registry = load_registry(DEFAULT_REGISTRY)

        self.assertEqual(validate_experiment(experiment, registry), [])
        self.assertEqual(experiment["experiment_id"], "public_private_read_routing_v1_hf_validation")
        self.assertIn("public_read_allow_rate", experiment["metrics"])
        self.assertIn("private_read_escalation_rate", experiment["metrics"])
        self.assertIn("authorized_private_read_allow_rate", experiment["metrics"])

    def test_fixture_mode_reports_read_routing_without_raw_payloads(self):
        output = ROOT / "eval_outputs" / "public_private_read_routing_hf_experiment_results.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_public_private_read_routing_hf_experiment.py",
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
        self.assertEqual(payload["experiment_id"], "public_private_read_routing_v1_hf_validation")
        heldout = payload["heldout_validation"]["metrics_by_method"]
        self.assertEqual(heldout["deterministic_aana_v2"]["schema_failure_rate"], 0.0)
        self.assertEqual(heldout["deterministic_aana_v2"]["authorized_private_read_allow_rate"], 1.0)
        self.assertIn("plain_permissive_agent", heldout)
        first_row = payload["heldout_validation"]["rows"][0]
        self.assertIn("expected_read_category", first_row)
        self.assertIn("argument_value_sha256", first_row)
        self.assertNotIn("proposed_arguments", first_row)
        serialized = json.dumps(payload)
        self.assertNotIn("Find public docs", serialized)
        self.assertNotIn("bank_routing_number", serialized)

    def test_fixture_cases_include_public_and_private_reads(self):
        from scripts.run_public_private_read_routing_hf_experiment import _fixture_rows, _load_json

        experiment = _load_json(ROOT / "examples" / "public_private_read_routing_hf_experiment.json")
        rows = _fixture_rows(experiment)
        self.assertEqual({row["expected_read_category"] if "expected_read_category" in row else row["tool_category"] for row in rows}, {"public_read", "private_read"})


if __name__ == "__main__":
    unittest.main()
