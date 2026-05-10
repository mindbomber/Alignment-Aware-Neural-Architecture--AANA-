import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.hf_calibration import (
    REQUIRED_CALIBRATION_FAMILIES,
    REQUIRED_CALIBRATION_METRICS,
    validate_hf_calibration_plan,
)


ROOT = Path(__file__).resolve().parents[1]


def load_plan():
    return json.loads((ROOT / "examples" / "hf_calibration_plan.json").read_text(encoding="utf-8"))


def load_registry():
    return json.loads((ROOT / "examples" / "hf_dataset_validation_registry.json").read_text(encoding="utf-8"))


class HFCalibrationTests(unittest.TestCase):
    def test_current_calibration_plan_is_valid(self):
        report = validate_hf_calibration_plan(load_plan(), load_registry())

        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["family_count"], len(REQUIRED_CALIBRATION_FAMILIES))
        self.assertEqual(report["required_family_count"], len(REQUIRED_CALIBRATION_FAMILIES))

    def test_requires_all_calibration_families(self):
        plan = load_plan()
        broken = copy.deepcopy(plan)
        broken["families"] = [family for family in broken["families"] if family["family_id"] != "pharma"]

        report = validate_hf_calibration_plan(broken, load_registry())

        self.assertFalse(report["valid"])
        self.assertTrue(any("Missing required calibration family: pharma" in issue["message"] for issue in report["issues"]))

    def test_requires_exact_metric_tracking(self):
        plan = load_plan()
        broken = copy.deepcopy(plan)
        broken["required_metrics"].remove("route_quality")

        report = validate_hf_calibration_plan(broken, load_registry())

        self.assertFalse(report["valid"])
        self.assertTrue(any("required_metrics" == issue["path"] for issue in report["issues"]))

    def test_blocks_calibration_reporting_split_leakage(self):
        plan = load_plan()
        broken = copy.deepcopy(plan)
        family = next(item for item in broken["families"] if item["family_id"] == "privacy")
        family["reporting_sources"][0] = {
            "dataset_name": "ai4privacy/pii-masking-openpii-1m",
            "config": "default",
            "split": "train",
            "allowed_use": "calibration",
        }

        report = validate_hf_calibration_plan(broken, load_registry())

        self.assertFalse(report["valid"])
        self.assertTrue(any("allowed_use must be one of" in issue["message"] for issue in report["issues"]))

    def test_blocks_registered_split_reuse_even_if_allowed_use_is_changed(self):
        plan = load_plan()
        broken = copy.deepcopy(plan)
        family = next(item for item in broken["families"] if item["family_id"] == "privacy")
        family["reporting_sources"][0] = {
            "dataset_name": "ai4privacy/pii-masking-openpii-1m",
            "config": "default",
            "split": "train",
            "allowed_use": "heldout_validation",
        }

        report = validate_hf_calibration_plan(broken, load_registry())

        self.assertFalse(report["valid"])
        self.assertTrue(any("Calibration and reporting cannot share" in issue["message"] for issue in report["issues"]))

    def test_requires_targets_for_each_metric(self):
        plan = load_plan()
        broken = copy.deepcopy(plan)
        family = next(item for item in broken["families"] if item["family_id"] == "support")
        family["targets"].pop("false_positive_rate")

        report = validate_hf_calibration_plan(broken, load_registry())

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"].endswith("targets.false_positive_rate") for issue in report["issues"]))

    def test_current_metrics_must_include_all_required_metrics(self):
        plan = load_plan()
        broken = copy.deepcopy(plan)
        family = next(item for item in broken["families"] if item["family_id"] == "tool_use")
        family["current_metrics"] = {metric: 1.0 for metric in REQUIRED_CALIBRATION_METRICS}
        family["current_metrics"].pop("schema_failure_rate")

        report = validate_hf_calibration_plan(broken, load_registry())

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"].endswith("current_metrics.schema_failure_rate") for issue in report["issues"]))

    def test_cli_validates_current_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / "hf-calibration.json"
            plan_path.write_text(json.dumps(load_plan()), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "scripts/hf/validate_hf_calibration.py", "--plan", str(plan_path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass -- families=8/8", completed.stdout)


if __name__ == "__main__":
    unittest.main()
