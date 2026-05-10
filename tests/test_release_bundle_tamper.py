import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_release_bundle import create_mi_release_bundle
from eval_pipeline.mi_release_bundle_verification import verify_mi_release_bundle


ROOT = Path(__file__).resolve().parents[1]


class ReleaseBundleTamperTests(unittest.TestCase):
    def test_verifier_detects_modified_copied_artifacts_by_hash(self):
        tamper_targets = ("release_candidate_report", "audit_jsonl", "pilot_handoffs", "remediation_report")

        for target in tamper_targets:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                bundle = create_mi_release_bundle(directory)
                manifest_path = Path(bundle["paths"]["release_manifest"])
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                artifact_path = Path(manifest["artifacts"][target]["bundle_path"])
                original_hash = manifest["artifacts"][target]["sha256"]
                artifact_path.write_text(artifact_path.read_text(encoding="utf-8") + "\nTAMPERED\n", encoding="utf-8")

                verification = verify_mi_release_bundle(manifest_path, output_path=None)

            mismatches = [
                issue
                for issue in verification["issues"]
                if issue.get("code") == "sha256_mismatch" and issue.get("artifact") == target
            ]
            artifact_check = next(item for item in verification["artifact_checks"] if item["artifact"] == target)
            self.assertFalse(verification["valid"])
            self.assertEqual(verification["status"], "block")
            self.assertEqual(len(mismatches), 1)
            self.assertEqual(artifact_check["status"], "block")
            self.assertEqual(artifact_check["expected_sha256"], original_hash)
            self.assertNotEqual(artifact_check["actual_sha256"], original_hash)

    def test_cli_fails_after_copied_artifact_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = create_mi_release_bundle(directory)
            manifest_path = Path(bundle["paths"]["release_manifest"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            dashboard_path = Path(manifest["artifacts"]["dashboard"]["bundle_path"])
            dashboard_path.write_text(dashboard_path.read_text(encoding="utf-8") + "\nTAMPERED\n", encoding="utf-8")
            output_path = Path(directory) / "release_bundle_verification.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/publication/mi_verify_release_bundle.py",
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            verification = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 1)
        self.assertIn("block --", completed.stdout)
        self.assertIn("sha256_mismatch", completed.stdout)
        self.assertFalse(verification["valid"])
        self.assertTrue(any(issue.get("artifact") == "dashboard" for issue in verification["issues"]))


if __name__ == "__main__":
    unittest.main()
