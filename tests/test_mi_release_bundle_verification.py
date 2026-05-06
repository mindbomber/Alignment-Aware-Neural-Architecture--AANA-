import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_release_bundle import create_mi_release_bundle
from eval_pipeline.mi_release_bundle_verification import verify_mi_release_bundle


ROOT = Path(__file__).resolve().parents[1]


class MIReleaseBundleVerificationTests(unittest.TestCase):
    def test_verifies_release_bundle_hashes_and_statuses(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = create_mi_release_bundle(directory)
            output_path = Path(directory) / "release_bundle_verification.json"
            verification = verify_mi_release_bundle(bundle["paths"]["release_manifest"], output_path=output_path)
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(written, verification)
        self.assertTrue(verification["valid"])
        self.assertEqual(verification["status"], "pass")
        self.assertEqual(verification["artifact_count"], 9)
        self.assertEqual(verification["issue_count"], 0)
        self.assertEqual(verification["release_status_checks"]["rc_status"], "pass")
        self.assertEqual(verification["release_status_checks"]["readiness_status"], "ready")
        self.assertEqual(verification["release_status_checks"]["unresolved_blocker_count"], 0)

    def test_verification_fails_on_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = create_mi_release_bundle(directory)
            manifest = json.loads(Path(bundle["paths"]["release_manifest"]).read_text(encoding="utf-8"))
            artifact_path = Path(manifest["artifacts"]["dashboard"]["bundle_path"])
            artifact_path.write_text(artifact_path.read_text(encoding="utf-8") + "\nTAMPERED\n", encoding="utf-8")

            verification = verify_mi_release_bundle(bundle["paths"]["release_manifest"], output_path=None)

        self.assertFalse(verification["valid"])
        self.assertEqual(verification["status"], "block")
        self.assertTrue(any(issue["code"] == "sha256_mismatch" for issue in verification["issues"]))

    def test_verification_fails_on_missing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = create_mi_release_bundle(directory)
            manifest = json.loads(Path(bundle["paths"]["release_manifest"]).read_text(encoding="utf-8"))
            Path(manifest["artifacts"]["audit_jsonl"]["bundle_path"]).unlink()

            verification = verify_mi_release_bundle(bundle["paths"]["release_manifest"], output_path=None)

        self.assertFalse(verification["valid"])
        self.assertTrue(any(issue["code"] == "missing_artifact" for issue in verification["issues"]))

    def test_verification_fails_on_status_regression(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = create_mi_release_bundle(directory)
            manifest_path = Path(bundle["paths"]["release_manifest"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rc_status"] = "block"
            manifest["readiness_status"] = "blocked"
            manifest["global_aix"]["score"] = 0.1
            manifest["unresolved_blocker_count"] = 1
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            verification = verify_mi_release_bundle(manifest_path, output_path=None)

        codes = {issue["code"] for issue in verification["issues"]}
        self.assertIn("rc_not_pass", codes)
        self.assertIn("readiness_not_ready", codes)
        self.assertIn("global_aix_below_threshold", codes)
        self.assertIn("unresolved_blockers", codes)

    def test_verification_cli_writes_output(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = create_mi_release_bundle(directory)
            output_path = Path(directory) / "verification.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/mi_verify_release_bundle.py",
                    "--manifest",
                    bundle["paths"]["release_manifest"],
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            verification = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("pass -- artifacts=9 issues=0", completed.stdout)
        self.assertTrue(verification["valid"])


if __name__ == "__main__":
    unittest.main()
