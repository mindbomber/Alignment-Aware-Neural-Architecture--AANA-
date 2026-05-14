import copy
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile
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

    def test_public_package_excludes_repo_local_tooling(self):
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        scripts = pyproject["project"]["scripts"]
        finder = pyproject["tool"]["setuptools"]["packages"]["find"]
        manifest = load_manifest()
        python_surface = next(surface for surface in manifest["surfaces"] if surface["id"] == "python_package")

        self.assertEqual(scripts, {
            "aana": "aana.cli:main",
            "aana-fastapi": "aana.fastapi_app:main",
            "aana-validate-platform": "aana.validate_platform:main",
        })
        self.assertEqual(finder["include"], ["aana*", "eval_pipeline*"])
        self.assertEqual(finder["exclude"], ["scripts*", "tests*", "evals*"])
        self.assertEqual(python_surface["current_distribution"], "aana-eval-pipeline")
        self.assertEqual(python_surface["distribution_status"], "transitional_legacy_name")
        self.assertEqual(python_surface["future_distribution_target"], "aana")

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

    def test_requires_transitional_package_name_policy(self):
        manifest = load_manifest()
        broken = copy.deepcopy(manifest)
        broken["surfaces"][0]["distribution_status"] = "permanent"
        broken["surfaces"][0]["future_distribution_target"] = "aana-platform"
        broken["distribution_rename_plan"]["current_distribution_status"] = "permanent"
        broken["distribution_rename_plan"]["target_distribution"] = "aana-platform"

        report = validate_packaging_hardening(broken, root=ROOT)

        self.assertFalse(report["valid"])
        messages = "\n".join(issue["message"] for issue in report["issues"])
        self.assertIn("transitional_legacy_name", messages)
        self.assertIn("target distribution", messages)

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

    def test_runtime_modules_do_not_import_excluded_script_validators(self):
        runtime_files = [
            ROOT / "eval_pipeline" / "agent_api.py",
            ROOT / "eval_pipeline" / "contract_freeze.py",
        ]
        forbidden = [
            "from scripts.validation",
            "import validate_adapter",
            "import validate_adapter_gallery",
            "scripts/validation",
            "scripts\\\\validation",
        ]

        offenders = []
        for path in runtime_files:
            text = path.read_text(encoding="utf-8")
            offenders.extend(f"{path.relative_to(ROOT)} contains {marker}" for marker in forbidden if marker in text)

        self.assertEqual(offenders, [])

    def test_built_wheel_public_cli_smoke_in_clean_venv(self):
        if shutil.which("uv") is None:
            self.skipTest("uv is required for clean wheel smoke test")

        event = {
            "tool_name": "get_recent_transactions",
            "tool_category": "private_read",
            "authorization_state": "authenticated",
            "evidence_refs": [
                {
                    "source_id": "auth.test-session",
                    "kind": "auth_context",
                    "trust_tier": "system",
                    "redaction_status": "redacted",
                    "summary": "User is authenticated for the account view.",
                    "provenance": "test",
                    "freshness": "current",
                }
            ],
            "risk_domain": "finance",
            "proposed_arguments": {"account_id": "acct_test", "limit": 5},
            "recommended_route": "accept",
        }

        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            wheel_dir = tmp / "dist"
            venv_dir = tmp / "venv"
            event_path = tmp / "pre_tool_event.json"
            event_path.write_text(json.dumps(event), encoding="utf-8")

            build = subprocess.run(
                ["uv", "build", "--wheel", "--out-dir", str(wheel_dir)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)

            wheels = sorted(wheel_dir.glob("*.whl"))
            self.assertEqual(len(wheels), 1)
            wheel = wheels[0]
            with zipfile.ZipFile(wheel) as archive:
                packaged = archive.namelist()
                self.assertFalse(any(name.startswith("scripts/") for name in packaged))
                entry_points = [
                    archive.read(name).decode("utf-8")
                    for name in packaged
                    if name.endswith("entry_points.txt")
                ][0]
                self.assertIn("aana = aana.cli:main", entry_points)
                self.assertNotIn("scripts.aana_cli", entry_points)

            create_venv = subprocess.run(
                ["uv", "venv", "--python", sys.executable, str(venv_dir)],
                cwd=tmp,
                text=True,
                capture_output=True,
            )
            self.assertEqual(create_venv.returncode, 0, create_venv.stdout + create_venv.stderr)

            python = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            aana = venv_dir / ("Scripts/aana.exe" if sys.platform == "win32" else "bin/aana")
            install = subprocess.run(
                ["uv", "pip", "install", "--python", str(python), str(wheel)],
                cwd=tmp,
                text=True,
                capture_output=True,
            )
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)

            help_result = subprocess.run([str(aana), "--help"], cwd=tmp, text=True, capture_output=True)
            self.assertEqual(help_result.returncode, 0, help_result.stdout + help_result.stderr)
            self.assertIn("pre-tool-check", help_result.stdout)

            doctor = subprocess.run([str(aana), "doctor", "--json"], cwd=tmp, text=True, capture_output=True)
            self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
            doctor_report = json.loads(doctor.stdout)
            doctor_checks = {item["name"]: item for item in doctor_report["checks"]}
            self.assertTrue(doctor_report["valid"])
            self.assertEqual(doctor_checks["adapter_gallery"]["status"], "warn")
            self.assertTrue(doctor_checks["adapter_gallery"]["details"]["skipped"])
            self.assertEqual(doctor_checks["agent_event_examples"]["status"], "warn")
            self.assertTrue(doctor_checks["agent_event_examples"]["details"]["skipped"])

            precheck = subprocess.run(
                [str(aana), "pre-tool-check", "--event", str(event_path)],
                cwd=tmp,
                text=True,
                capture_output=True,
            )
            self.assertEqual(precheck.returncode, 0, precheck.stdout + precheck.stderr)
            self.assertIn('"route": "accept"', precheck.stdout)

    def test_cli_validates_packaging_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "packaging.json"
            manifest_path.write_text(json.dumps(load_manifest()), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/validation/validate_packaging_hardening.py",
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
