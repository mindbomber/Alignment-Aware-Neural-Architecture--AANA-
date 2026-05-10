import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.hf_dataset_proof import validate_hf_dataset_proof_report


ROOT = Path(__file__).resolve().parents[1]


def load_current():
    return json.loads((ROOT / "examples" / "hf_dataset_proof_report.json").read_text(encoding="utf-8"))


def load_registry():
    return json.loads((ROOT / "examples" / "hf_dataset_validation_registry.json").read_text(encoding="utf-8"))


class HFDatasetProofTests(unittest.TestCase):
    def test_current_hf_dataset_proof_report_is_valid(self):
        report = validate_hf_dataset_proof_report(load_current(), root=ROOT, require_existing_artifacts=True, registry=load_registry())

        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["proof_axis_count"], 9)
        self.assertGreaterEqual(report["artifact_metric_checks"], 10)

    def test_requires_all_four_proof_axes(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["proof_axes"] = [axis for axis in broken["proof_axes"] if axis["id"] != "groundedness"]

        report = validate_hf_dataset_proof_report(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("Missing required proof axes" in issue["message"] for issue in report["issues"]))

    def test_blocks_comparative_language_without_paired_baselines(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["policy"]["public_language_rule"] = "Claim lower false positives and higher unsafe recall."

        report = validate_hf_dataset_proof_report(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("comparative deltas" in issue["message"] for issue in report["issues"]))

    def test_blocks_metric_threshold_failure(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["proof_axes"][0]["metrics"][0]["threshold"] = -1.0
        broken["proof_axes"][0]["metrics"][0]["direction"] = "at_most"

        report = validate_hf_dataset_proof_report(broken, root=ROOT, require_existing_artifacts=True, registry=load_registry())

        self.assertFalse(report["valid"])
        self.assertTrue(any("above threshold" in issue["message"] for issue in report["issues"]))

    def test_blocks_public_claim_dataset_ref_to_calibration_split(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["proof_axes"][0]["dataset_refs"] = [
            {
                "dataset_name": "ai4privacy/pii-masking-openpii-1m",
                "config": "default",
                "split": "train",
            }
        ]

        report = validate_hf_dataset_proof_report(broken, root=ROOT, registry=load_registry())

        self.assertFalse(report["valid"])
        self.assertTrue(any("registered for calibration" in issue["message"] for issue in report["issues"]))

    def test_requires_dataset_refs_for_public_proof_axes(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["proof_axes"][0].pop("dataset_refs")

        report = validate_hf_dataset_proof_report(broken, root=ROOT, registry=load_registry())

        self.assertFalse(report["valid"])
        self.assertTrue(any("dataset_refs" in issue["path"] for issue in report["issues"]))

    def test_requires_public_result_labels(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["result_label"] = "calibration"
        broken["proof_axes"][0].pop("result_label")

        report = validate_hf_dataset_proof_report(broken, root=ROOT, registry=load_registry())

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "result_label" for issue in report["issues"]))
        self.assertTrue(any(issue["path"].endswith("result_label") for issue in report["issues"]))

    def test_cli_validates_hf_dataset_proof_report(self):
        manifest = load_current()
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "hf-proof.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/hf/validate_hf_dataset_proof.py",
                    "--manifest",
                    str(manifest_path),
                    "--require-existing-artifacts",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass -- axes=9", completed.stdout)


if __name__ == "__main__":
    unittest.main()
