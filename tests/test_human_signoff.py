import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.human_signoff import (
    human_signoff_record,
    validate_human_signoff_record,
    write_human_signoff_record,
)
from eval_pipeline.mi_release_bundle import create_mi_release_bundle
from eval_pipeline.mi_release_bundle_verification import verify_mi_release_bundle


ROOT = Path(__file__).resolve().parents[1]


class HumanSignoffTests(unittest.TestCase):
    def test_pending_signoff_records_reviewer_decision_scope_and_bundle_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = create_mi_release_bundle(directory)
            verification_path = Path(directory) / "release_bundle_verification.json"
            verify_mi_release_bundle(bundle["paths"]["release_manifest"], output_path=verification_path)
            record = human_signoff_record(
                release_manifest_path=bundle["paths"]["release_manifest"],
                verification_path=verification_path,
            )
            validation = validate_human_signoff_record(record)

            self.assertEqual(record["decision"], "pending")
            self.assertEqual(record["reviewer"]["role"], "domain_owner")
            self.assertEqual(record["scope"]["approval_boundary"], "local_mi_release_bundle")
            self.assertIn("release_manifest_sha256", record["evidence_bundle"])
            self.assertEqual(record["evidence_bundle"]["verification_status"], "pass")
            self.assertTrue(validation["valid"], validation["issues"])

    def test_approved_signoff_requires_passing_bundle_status(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = create_mi_release_bundle(directory)
            verification_path = Path(directory) / "release_bundle_verification.json"
            verify_mi_release_bundle(bundle["paths"]["release_manifest"], output_path=verification_path)
            record = human_signoff_record(
                reviewer={"id": "reviewer-1", "name": "Domain Reviewer", "role": "domain_owner"},
                decision="approved",
                release_manifest_path=bundle["paths"]["release_manifest"],
                verification_path=verification_path,
                notes="Approved for local MI release bundle scope.",
            )
            validation = validate_human_signoff_record(record)

            self.assertTrue(validation["valid"], validation["issues"])
            self.assertEqual(record["decision"], "approved")

    def test_signoff_validation_fails_when_manifest_hash_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = create_mi_release_bundle(directory)
            verification_path = Path(directory) / "release_bundle_verification.json"
            verify_mi_release_bundle(bundle["paths"]["release_manifest"], output_path=verification_path)
            record = human_signoff_record(
                release_manifest_path=bundle["paths"]["release_manifest"],
                verification_path=verification_path,
            )
            manifest_path = Path(bundle["paths"]["release_manifest"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rc_status"] = "block"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            report = validate_human_signoff_record(record)

        self.assertFalse(report["valid"])
        self.assertTrue(any("hash does not match" in issue["message"] for issue in report["issues"]))

    def test_write_human_signoff_record_outputs_json(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = create_mi_release_bundle(directory)
            verification_path = Path(directory) / "release_bundle_verification.json"
            verify_mi_release_bundle(bundle["paths"]["release_manifest"], output_path=verification_path)
            output_path = Path(directory) / "human_signoff.json"
            payload = write_human_signoff_record(
                output_path,
                release_manifest_path=bundle["paths"]["release_manifest"],
                verification_path=verification_path,
            )
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(written, payload["record"])
        self.assertTrue(payload["validation"]["valid"])
        self.assertGreater(payload["bytes"], 0)

    def test_human_signoff_cli_writes_pending_record(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = create_mi_release_bundle(directory)
            verification_path = Path(directory) / "release_bundle_verification.json"
            verify_mi_release_bundle(bundle["paths"]["release_manifest"], output_path=verification_path)
            output_path = Path(directory) / "human_signoff.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/publication/human_signoff.py",
                    "--output",
                    str(output_path),
                    "--manifest",
                    bundle["paths"]["release_manifest"],
                    "--verification",
                    str(verification_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            record = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("pending -- reviewer=pending-domain-owner", completed.stdout)
        self.assertEqual(record["record_type"], "aana_mi_human_signoff")


if __name__ == "__main__":
    unittest.main()
