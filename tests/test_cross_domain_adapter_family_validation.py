import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.cross_domain_adapter_family_validation import REQUIRED_FAMILIES, validate_cross_domain_adapter_family_validation


ROOT = Path(__file__).resolve().parents[1]


def load_current():
    manifest = json.loads((ROOT / "examples" / "cross_domain_adapter_family_validation.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "examples" / "hf_dataset_validation_registry.json").read_text(encoding="utf-8"))
    return manifest, registry


class CrossDomainAdapterFamilyValidationTests(unittest.TestCase):
    def test_current_manifest_is_valid(self):
        manifest, registry = load_current()
        report = validate_cross_domain_adapter_family_validation(manifest, registry, root=ROOT, require_existing_artifacts=True)

        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["passed_family_count"], len(REQUIRED_FAMILIES))

    def test_blocks_missing_required_family(self):
        manifest, registry = load_current()
        manifest["families"] = [family for family in manifest["families"] if family["family_id"] != "finance"]
        report = validate_cross_domain_adapter_family_validation(manifest, registry, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("finance" in issue["message"] for issue in report["issues"]))

    def test_blocks_calibration_only_mapping(self):
        manifest, registry = load_current()
        broken = copy.deepcopy(manifest)
        broken["families"][0]["datasets"][0]["dataset_name"] = "zake7749/Qwen-3.6-plus-agent-tool-calling-trajectory"
        broken["families"][0]["datasets"][0]["config"] = "default"
        broken["families"][0]["datasets"][0]["split"] = "train"
        broken["families"][0]["datasets"][0]["allowed_use"] = "calibration"
        report = validate_cross_domain_adapter_family_validation(broken, registry, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("allowed_use" in issue["path"] for issue in report["issues"]))

    def test_blocks_missing_validation_artifact_when_required(self):
        manifest, registry = load_current()
        broken = copy.deepcopy(manifest)
        broken["families"][0]["validation_result"]["artifact"] = "eval_outputs/missing/family.json"
        report = validate_cross_domain_adapter_family_validation(broken, registry, root=ROOT, require_existing_artifacts=True)

        self.assertFalse(report["valid"])
        self.assertTrue(any("does not exist" in issue["message"] for issue in report["issues"]))

    def test_cli_validates_manifest(self):
        manifest, _registry = load_current()
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "families.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/validation/validate_cross_domain_adapter_families.py",
                    "--manifest",
                    str(manifest_path),
                    "--require-existing-artifacts",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass -- families=6", completed.stdout)


if __name__ == "__main__":
    unittest.main()

