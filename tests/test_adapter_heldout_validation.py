import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.adapter_heldout_validation import ADAPTER_IMPROVEMENT_PATTERNS, validate_adapter_heldout_manifest


ROOT = Path(__file__).resolve().parents[1]


def valid_manifest():
    return {
        "schema_version": "0.1",
        "policy": {
            "require_after_every_adapter_improvement": True,
            "allow_training_or_tuned_split": False,
            "adapter_family_surfaces": list(ADAPTER_IMPROVEMENT_PATTERNS),
        },
        "adapter_improvements": [
            {
                "improvement_id": "retail-order-planner-v1",
                "adapter_id": "tau2/aana_contract_agent",
                "summary": "Improve evidence-derived retail order workflow planning.",
                "changed_paths": ["examples/tau2/aana_contract_agent.py"],
                "heldout_validation": {
                    "task_set": "held-out retail order tasks",
                    "task_set_path": "tests/test_adapter_heldout_validation.py",
                    "result_artifact": "tests/test_adapter_heldout_validation.py",
                    "split": "held_out",
                    "label_visibility": "hidden_from_gate",
                    "status": "pass",
                    "run_without_benchmark_probes": True,
                    "metrics": {"pass1": 1.0, "schema_failure_rate": 0.0},
                    "notes": "Unit fixture for held-out validation policy.",
                },
            }
        ],
    }


class AdapterHeldoutValidationTests(unittest.TestCase):
    def test_current_manifest_is_valid(self):
        manifest = json.loads((ROOT / "examples" / "adapter_heldout_validation.json").read_text(encoding="utf-8"))
        report = validate_adapter_heldout_manifest(manifest, root=ROOT)

        self.assertTrue(report["valid"], report["issues"])
        self.assertGreaterEqual(report["record_count"], 1)

    def test_blocks_adapter_improvement_without_heldout_validation(self):
        manifest = valid_manifest()
        manifest["adapter_improvements"][0].pop("heldout_validation")
        report = validate_adapter_heldout_manifest(manifest, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertIn("heldout_validation", {issue["path"].split(".")[-1] for issue in report["issues"]})

    def test_blocks_training_or_tuned_split(self):
        manifest = valid_manifest()
        manifest["adapter_improvements"][0]["heldout_validation"]["split"] = "calibration"
        report = validate_adapter_heldout_manifest(manifest, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertIn("training, tuning, dev, or calibration", report["issues"][0]["message"])

    def test_blocks_probe_enabled_validation(self):
        manifest = valid_manifest()
        manifest["adapter_improvements"][0]["heldout_validation"]["run_without_benchmark_probes"] = False
        report = validate_adapter_heldout_manifest(manifest, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"].endswith("run_without_benchmark_probes") for issue in report["issues"]))

    def test_cli_validates_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "heldout.json"
            manifest_path.write_text(json.dumps(valid_manifest()), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "scripts/validate_adapter_heldout.py", "--manifest", str(manifest_path), "--require-existing-artifacts"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass -- records=1", completed.stdout)

    def test_blocks_policy_missing_adapter_family_surface(self):
        manifest = valid_manifest()
        manifest["policy"]["adapter_family_surfaces"].remove("examples/*_adapter.json")
        report = validate_adapter_heldout_manifest(manifest, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("examples/*_adapter.json" in issue["message"] for issue in report["issues"]))

    def test_accepts_adapter_family_paths_as_tracked_surfaces(self):
        manifest = valid_manifest()
        manifest["adapter_improvements"][0]["changed_paths"] = [
            "examples/learning_tutor_answer_checker_adapter.json",
            "eval_pipeline/adapter_runner/verifier_modules/customer_comms.py",
            "docs/families/data.json",
        ]
        report = validate_adapter_heldout_manifest(manifest, root=ROOT)

        self.assertTrue(report["valid"], report["issues"])


if __name__ == "__main__":
    unittest.main()
