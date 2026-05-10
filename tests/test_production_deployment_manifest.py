import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.human_signoff import write_human_signoff_record
from eval_pipeline.live_connector_readiness import write_live_connector_readiness_plan
from eval_pipeline.mi_release_bundle import create_mi_release_bundle
from eval_pipeline.mi_release_bundle_verification import verify_mi_release_bundle
from eval_pipeline.production_deployment_manifest import (
    PRODUCTION_DEPLOYMENT_MANIFEST_TYPE,
    production_deployment_manifest,
    validate_production_deployment_manifest,
    write_production_deployment_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class ProductionDeploymentManifestTests(unittest.TestCase):
    def _bundle_context(self, directory: str):
        bundle = create_mi_release_bundle(directory)
        verification_path = Path(directory) / "release_bundle_verification.json"
        verify_mi_release_bundle(bundle["paths"]["release_manifest"], output_path=verification_path)
        signoff_path = Path(directory) / "human_signoff.json"
        write_human_signoff_record(
            signoff_path,
            release_manifest_path=bundle["paths"]["release_manifest"],
            verification_path=verification_path,
        )
        live_connector_path = Path(directory) / "live_connector_readiness_plan.json"
        write_live_connector_readiness_plan(live_connector_path)
        return bundle, verification_path, signoff_path, live_connector_path

    def test_manifest_references_verified_bundle_and_blocks_without_human_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, verification_path, signoff_path, live_connector_path = self._bundle_context(directory)
            manifest = production_deployment_manifest(
                release_manifest_path=bundle["paths"]["release_manifest"],
                verification_path=verification_path,
                human_signoff_path=signoff_path,
                live_connector_plan_path=live_connector_path,
            )
            validation = validate_production_deployment_manifest(manifest)

        self.assertEqual(manifest["manifest_type"], PRODUCTION_DEPLOYMENT_MANIFEST_TYPE)
        self.assertTrue(validation["valid"], validation["issues"])
        self.assertEqual(manifest["verified_mi_release_bundle"]["verification_status"], "pass")
        self.assertEqual(manifest["verified_mi_release_bundle"]["rc_status"], "pass")
        self.assertEqual(manifest["verified_mi_release_bundle"]["readiness_status"], "ready")
        self.assertFalse(manifest["deployment_authorized"])
        self.assertIn("human_signoff_not_approved", manifest["blockers"])

    def test_manifest_includes_environment_secrets_audit_and_rollback_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, verification_path, signoff_path, live_connector_path = self._bundle_context(directory)
            manifest = production_deployment_manifest(
                release_manifest_path=bundle["paths"]["release_manifest"],
                verification_path=verification_path,
                human_signoff_path=signoff_path,
                live_connector_plan_path=live_connector_path,
            )

        self.assertEqual(manifest["environment_assumptions"]["target_environment"], "production")
        self.assertFalse(manifest["secrets_policy"]["plaintext_files_allowed"])
        self.assertFalse(manifest["secrets_policy"]["secrets_in_logs_allowed"])
        self.assertEqual(manifest["audit_policy"]["mode"], "redacted_decision_metadata_only")
        self.assertFalse(manifest["audit_policy"]["raw_private_content_allowed"])
        self.assertEqual(manifest["rollback"]["owner"]["role"], "release_manager")
        self.assertTrue(manifest["rollback"]["rollback_required_before_live_enablement"])

    def test_validation_rejects_unverified_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, verification_path, signoff_path, live_connector_path = self._bundle_context(directory)
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            verification["status"] = "block"
            verification_path.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            manifest = production_deployment_manifest(
                release_manifest_path=bundle["paths"]["release_manifest"],
                verification_path=verification_path,
                human_signoff_path=signoff_path,
                live_connector_plan_path=live_connector_path,
            )

        validation = validate_production_deployment_manifest(manifest)
        self.assertFalse(validation["valid"])
        self.assertTrue(any(issue["path"] == "$.verified_mi_release_bundle.verification_status" for issue in validation["issues"]))

    def test_write_manifest_outputs_json(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, verification_path, signoff_path, live_connector_path = self._bundle_context(directory)
            output_path = Path(directory) / "production_deployment_manifest.json"
            payload = write_production_deployment_manifest(
                output_path,
                release_manifest_path=bundle["paths"]["release_manifest"],
                verification_path=verification_path,
                human_signoff_path=signoff_path,
                live_connector_plan_path=live_connector_path,
            )
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(written, payload["manifest"])
        self.assertTrue(payload["validation"]["valid"], payload["validation"]["issues"])
        self.assertGreater(payload["bytes"], 0)

    def test_production_deployment_manifest_cli_writes_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, verification_path, signoff_path, live_connector_path = self._bundle_context(directory)
            output_path = Path(directory) / "production_deployment_manifest.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/publication/production_deployment_manifest.py",
                    "--output",
                    str(output_path),
                    "--manifest",
                    bundle["paths"]["release_manifest"],
                    "--verification",
                    str(verification_path),
                    "--human-signoff",
                    str(signoff_path),
                    "--live-connector-plan",
                    str(live_connector_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("blocked -- verification=pass", completed.stdout)
        self.assertEqual(written["deployment_status"], "blocked")


if __name__ == "__main__":
    unittest.main()
