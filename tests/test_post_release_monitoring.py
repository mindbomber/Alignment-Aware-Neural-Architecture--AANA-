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
from eval_pipeline.post_release_monitoring import (
    POST_RELEASE_MONITORING_POLICY_TYPE,
    REQUIRED_ALERT_IDS,
    post_release_monitoring_policy,
    validate_post_release_monitoring_policy,
    write_post_release_monitoring_policy,
)
from eval_pipeline.production_deployment_manifest import write_production_deployment_manifest


ROOT = Path(__file__).resolve().parents[1]


class PostReleaseMonitoringTests(unittest.TestCase):
    def _deployment_manifest(self, directory: str) -> Path:
        bundle = create_mi_release_bundle(directory)
        verification_path = Path(directory) / "release_bundle_verification.json"
        verify_mi_release_bundle(bundle["paths"]["release_manifest"], output_path=verification_path)
        signoff_path = Path(directory) / "human_signoff.json"
        write_human_signoff_record(
            signoff_path,
            release_manifest_path=bundle["paths"]["release_manifest"],
            verification_path=verification_path,
        )
        connector_path = Path(directory) / "live_connector_readiness_plan.json"
        write_live_connector_readiness_plan(connector_path)
        deployment_path = Path(directory) / "production_deployment_manifest.json"
        write_production_deployment_manifest(
            deployment_path,
            release_manifest_path=bundle["paths"]["release_manifest"],
            verification_path=verification_path,
            human_signoff_path=signoff_path,
            live_connector_plan_path=connector_path,
        )
        return deployment_path

    def test_policy_defines_required_runtime_metrics_and_alerts(self):
        with tempfile.TemporaryDirectory() as directory:
            deployment_path = self._deployment_manifest(directory)
            policy = post_release_monitoring_policy(deployment_manifest_path=deployment_path)
            validation = validate_post_release_monitoring_policy(policy)

        self.assertEqual(policy["policy_type"], POST_RELEASE_MONITORING_POLICY_TYPE)
        self.assertTrue(validation["valid"], validation["issues"])
        metric_ids = {metric["metric_id"] for metric in policy["metrics"]}
        self.assertIn("aix_drift_delta", metric_ids)
        self.assertIn("false_accept_rate", metric_ids)
        self.assertIn("false_refusal_rate", metric_ids)
        self.assertIn("audit_append_failure_count", metric_ids)
        self.assertIn("stale_evidence_rate", metric_ids)
        self.assertIn("unresolved_propagated_risk_count", metric_ids)
        self.assertEqual(REQUIRED_ALERT_IDS, tuple(alert["alert_id"] for alert in policy["alerts"]))

    def test_policy_uses_redacted_collection_only(self):
        with tempfile.TemporaryDirectory() as directory:
            deployment_path = self._deployment_manifest(directory)
            policy = post_release_monitoring_policy(deployment_manifest_path=deployment_path)

        self.assertFalse(policy["collection_policy"]["raw_private_content_allowed"])
        self.assertFalse(policy["collection_policy"]["raw_prompt_capture_allowed"])
        self.assertFalse(policy["collection_policy"]["raw_evidence_capture_allowed"])
        self.assertTrue(policy["collection_policy"]["redacted_metadata_only"])
        self.assertTrue(policy["incident_policy"]["critical_page"])

    def test_validation_rejects_missing_required_alert(self):
        with tempfile.TemporaryDirectory() as directory:
            deployment_path = self._deployment_manifest(directory)
            policy = post_release_monitoring_policy(deployment_manifest_path=deployment_path)
            policy["alerts"] = [alert for alert in policy["alerts"] if alert["alert_id"] != "aix_drift"]

        validation = validate_post_release_monitoring_policy(policy)
        self.assertFalse(validation["valid"])
        self.assertTrue(any("Missing required alert: aix_drift" in issue["message"] for issue in validation["issues"]))

    def test_write_policy_outputs_json(self):
        with tempfile.TemporaryDirectory() as directory:
            deployment_path = self._deployment_manifest(directory)
            output_path = Path(directory) / "post_release_monitoring_policy.json"
            payload = write_post_release_monitoring_policy(output_path, deployment_manifest_path=deployment_path)
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(written, payload["policy"])
        self.assertTrue(payload["validation"]["valid"], payload["validation"]["issues"])
        self.assertGreater(payload["bytes"], 0)

    def test_post_release_monitoring_cli_writes_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            deployment_path = self._deployment_manifest(directory)
            output_path = Path(directory) / "post_release_monitoring_policy.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/publication/post_release_monitoring.py",
                    "--output",
                    str(output_path),
                    "--deployment-manifest",
                    str(deployment_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("pass -- metrics=", completed.stdout)
        self.assertEqual(written["policy_type"], POST_RELEASE_MONITORING_POLICY_TYPE)


if __name__ == "__main__":
    unittest.main()
