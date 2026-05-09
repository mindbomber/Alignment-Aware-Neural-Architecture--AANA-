import json
import pathlib
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AgentToolUseHFExperimentTests(unittest.TestCase):
    def test_experiment_manifest_uses_registered_splits(self):
        from eval_pipeline.hf_dataset_registry import load_registry
        from scripts.run_agent_tool_use_hf_experiment import DEFAULT_EXPERIMENT, DEFAULT_REGISTRY, _load_json, validate_experiment

        experiment = _load_json(DEFAULT_EXPERIMENT)
        registry = load_registry(DEFAULT_REGISTRY)

        self.assertEqual(validate_experiment(experiment, registry), [])
        self.assertEqual(experiment["adapter_family"], "agent_tool_use")
        self.assertIn("tool_name", experiment["contract_fields"])
        self.assertIn("proposed_arguments", experiment["contract_fields"])

    def test_fixture_mode_reports_head_to_head_without_raw_arguments(self):
        output = ROOT / "eval_outputs" / "agent_tool_use_hf_experiment_results.test.json"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_agent_tool_use_hf_experiment.py",
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
        self.assertEqual(payload["experiment_id"], "agent_tool_use_control_v1_hf_validation")
        heldout = payload["heldout_validation"]["metrics_by_method"]
        self.assertIn("plain_permissive_agent", heldout)
        self.assertIn("deterministic_aana_v1", heldout)
        self.assertIn("deterministic_aana_v2", heldout)
        self.assertNotIn("aana_v2_semantic_calibrated", heldout)

        serialized = json.dumps(payload)
        self.assertNotIn("acct_redacted", serialized)
        self.assertNotIn("agent tool contract", serialized)
        first_row = payload["heldout_validation"]["rows"][0]
        self.assertIn("argument_keys", first_row)
        self.assertIn("argument_value_sha256", first_row)
        self.assertNotIn("proposed_arguments", first_row)
        self.assertFalse(first_row["raw_payload_logged"])

    def test_event_conversion_preserves_agent_action_contract_shape(self):
        from scripts.run_agent_tool_use_hf_experiment import _fixture_rows, _load_json, event_from_row

        experiment = _load_json(ROOT / "examples" / "agent_tool_use_hf_experiment.json")
        rows = _fixture_rows(experiment)
        event = event_from_row(rows[1])

        for field in (
            "tool_name",
            "tool_category",
            "authorization_state",
            "evidence_refs",
            "risk_domain",
            "proposed_arguments",
            "recommended_route",
        ):
            self.assertIn(field, event)
        self.assertEqual(event["recommended_route"], rows[1]["recommended_route"])
        self.assertGreaterEqual(len(event["evidence_refs"]), 2)


if __name__ == "__main__":
    unittest.main()
