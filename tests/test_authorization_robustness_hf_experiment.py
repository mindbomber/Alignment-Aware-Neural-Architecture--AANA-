import json
import pathlib
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AuthorizationRobustnessHFExperimentTests(unittest.TestCase):
    def test_fixture_mode_reports_robustness_metrics_without_raw_payloads(self):
        output = ROOT / "eval_outputs" / "authorization_robustness_hf_experiment_results.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/hf/run_authorization_robustness_hf_experiment.py",
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
        self.assertEqual(payload["experiment_id"], "authorization_robustness_v1_hf_validation")
        metrics = payload["heldout_validation"]["metrics_by_method"]["deterministic_aana_v2"]
        self.assertEqual(metrics["missing_auth_recall"], 1.0)
        self.assertEqual(metrics["safe_public_read_allow_rate"], 1.0)
        self.assertIn("contract_only_gate", payload["heldout_validation"]["metrics_by_method"])
        first_row = payload["heldout_validation"]["rows"][0]
        self.assertIn("perturbation", first_row)
        self.assertIn("argument_value_sha256", first_row)
        self.assertNotIn("event", first_row)
        self.assertNotIn("proposed_arguments", first_row)
        serialized = json.dumps(payload)
        self.assertNotIn("Find public docs", serialized)
        self.assertNotIn("bank_routing_number", serialized)

    def test_perturbations_cover_required_noise_modes(self):
        from scripts.hf.run_authorization_robustness_hf_experiment import perturb_rows
        from scripts.hf.run_public_private_read_routing_hf_experiment import _fixture_rows, _load_json

        experiment = _load_json(ROOT / "examples" / "public_private_read_routing_hf_experiment.json")
        rows = _fixture_rows(experiment)
        perturbations = {case["perturbation"] for case in perturb_rows(rows)}

        self.assertIn("downgrade_authenticated_to_user_claimed", perturbations)
        self.assertIn("remove_auth_evidence", perturbations)
        self.assertIn("mark_auth_evidence_stale", perturbations)
        self.assertIn("add_contradictory_evidence", perturbations)
        self.assertIn("mislabel_private_read_as_public_read", perturbations)
        self.assertIn("runtime_recommends_accept_incorrectly", perturbations)
        self.assertIn("malformed_evidence_refs", perturbations)


if __name__ == "__main__":
    unittest.main()
