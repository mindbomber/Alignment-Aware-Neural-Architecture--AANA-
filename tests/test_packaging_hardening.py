import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.packaging_hardening import validate_packaging_hardening


ROOT = Path(__file__).resolve().parents[1]


def load_manifest():
    return json.loads((ROOT / "examples" / "packaging_release_manifest.json").read_text(encoding="utf-8"))


class PackagingHardeningTests(unittest.TestCase):
    def test_current_packaging_manifest_is_valid(self):
        report = validate_packaging_hardening(load_manifest(), root=ROOT, require_existing_artifacts=True)

        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["surface_count"], 6)
        self.assertEqual(report["release_target_count"], 3)

    def test_requires_eval_tooling_surface(self):
        manifest = load_manifest()
        broken = copy.deepcopy(manifest)
        broken["surfaces"] = [surface for surface in broken["surfaces"] if surface["id"] != "benchmark_eval_tooling"]

        report = validate_packaging_hardening(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("benchmark_eval_tooling" in issue["message"] for issue in report["issues"]))

    def test_requires_examples_surface(self):
        manifest = load_manifest()
        broken = copy.deepcopy(manifest)
        broken["surfaces"] = [surface for surface in broken["surfaces"] if surface["id"] != "examples"]

        report = validate_packaging_hardening(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("examples" in issue["message"] for issue in report["issues"]))

    def test_requires_surface_boundaries_and_prevents_path_overlap(self):
        manifest = load_manifest()
        broken = copy.deepcopy(manifest)
        broken["surfaces"][0].pop("boundary")
        broken["surfaces"][1]["paths"].append("aana/sdk.py")

        report = validate_packaging_hardening(broken, root=ROOT)

        self.assertFalse(report["valid"])
        messages = "\n".join(issue["message"] for issue in report["issues"])
        self.assertIn("Surface must declare", messages)
        self.assertIn("claimed by multiple packaging surfaces", messages)

    def test_blocks_distribution_rename_without_migration_window(self):
        manifest = load_manifest()
        broken = copy.deepcopy(manifest)
        broken["distribution_rename_plan"]["rename_now"] = True
        broken["distribution_rename_plan"]["required_migration_rules"] = []

        report = validate_packaging_hardening(broken, root=ROOT)

        self.assertFalse(report["valid"])
        messages = "\n".join(issue["message"] for issue in report["issues"])
        self.assertIn("must not happen", messages)
        self.assertIn("Missing rename migration rule", messages)

    def test_requires_publication_checklist_for_all_targets(self):
        manifest = load_manifest()
        broken = copy.deepcopy(manifest)
        broken["release_checklist"] = [item for item in broken["release_checklist"] if item["target"] != "npm"]

        report = validate_packaging_hardening(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("npm" in issue["message"] for issue in report["issues"]))

    def test_release_checklist_declares_surface_boundaries(self):
        manifest = load_manifest()
        broken = copy.deepcopy(manifest)
        broken["release_checklist"][0].pop("surface_boundaries_checked")

        report = validate_packaging_hardening(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("surface_boundaries_checked" in issue["path"] for issue in report["issues"]))

    def test_cli_validates_packaging_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "packaging.json"
            manifest_path.write_text(json.dumps(load_manifest()), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/validate_packaging_hardening.py",
                    "--manifest",
                    str(manifest_path),
                    "--require-existing-artifacts",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass -- surfaces=6 release_targets=3", completed.stdout)


if __name__ == "__main__":
    unittest.main()
