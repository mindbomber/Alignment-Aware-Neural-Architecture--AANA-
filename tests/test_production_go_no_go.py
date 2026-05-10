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
from eval_pipeline.post_release_monitoring import write_post_release_monitoring_policy
from eval_pipeline.production_deployment_manifest import write_production_deployment_manifest
from eval_pipeline.production_dry_run import run_production_dry_run
from eval_pipeline.production_go_no_go import (
    PRODUCTION_GO_NO_GO_REPORT_TYPE,
    production_go_no_go_report,
    validate_production_go_no_go_report,
    write_production_go_no_go_report,
)


ROOT = Path(__file__).resolve().parents[1]


class ProductionGoNoGoTests(unittest.TestCase):
    def _context(self, directory: str):
        root = Path(directory)
        bundle = create_mi_release_bundle(root / "bundle")
        verification_path = root / "bundle" / "release_bundle_verification.json"
        verify_mi_release_bundle(bundle["paths"]["release_manifest"], output_path=verification_path)
        signoff_path = root / "bundle" / "human_signoff.json"
        write_human_signoff_record(
            signoff_path,
            release_manifest_path=bundle["paths"]["release_manifest"],
            verification_path=verification_path,
        )
        connector_path = root / "bundle" / "live_connector_readiness_plan.json"
        write_live_connector_readiness_plan(connector_path)
        deployment_path = root / "bundle" / "production_deployment_manifest.json"
        write_production_deployment_manifest(
            deployment_path,
            release_manifest_path=bundle["paths"]["release_manifest"],
            verification_path=verification_path,
            human_signoff_path=signoff_path,
            live_connector_plan_path=connector_path,
        )
        monitoring_path = root / "bundle" / "post_release_monitoring_policy.json"
        write_post_release_monitoring_policy(monitoring_path, deployment_manifest_path=deployment_path)
        dry_run_payload = run_production_dry_run(
            output_path=root / "bundle" / "production_dry_run_report.json",
            release_report_path=root / "bundle" / "aana_mi_release_report.json",
            rc_report_path=root / "bundle" / "aana_mi_release_candidate_report.json",
            benchmark_dir=root / "benchmark",
            bundle_dir=root / "bundle",
            deployment_manifest_path=deployment_path,
            human_signoff_path=signoff_path,
            live_connector_plan_path=connector_path,
        )
        return {
            "release_manifest_path": root / "bundle" / "release_manifest.json",
            "bundle_verification_path": root / "bundle" / "release_bundle_verification.json",
            "human_signoff_path": signoff_path,
            "deployment_manifest_path": deployment_path,
            "monitoring_policy_path": monitoring_path,
            "dry_run_report_path": Path(dry_run_payload["path"]),
        }

    def test_go_no_go_combines_required_artifacts_and_reports_no_go(self):
        with tempfile.TemporaryDirectory() as directory:
            context = self._context(directory)
            report = production_go_no_go_report(**context)
            validation = validate_production_go_no_go_report(report)

        self.assertEqual(report["report_type"], PRODUCTION_GO_NO_GO_REPORT_TYPE)
        self.assertTrue(validation["valid"], validation["issues"])
        self.assertEqual(report["status"], "no_go")
        self.assertFalse(report["go"])
        blocker_codes = {blocker["code"] for blocker in report["blockers"]}
        self.assertIn("human_signoff_not_approved", blocker_codes)
        self.assertIn("deployment_not_authorized", blocker_codes)
        self.assertIn("production_dry_run_not_pass", blocker_codes)

    def test_go_no_go_references_all_final_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            context = self._context(directory)
            report = production_go_no_go_report(**context)

        expected_refs = {
            "release_manifest",
            "release_bundle_verification",
            "human_signoff",
            "production_deployment_manifest",
            "post_release_monitoring_policy",
            "production_dry_run_report",
        }
        self.assertEqual(set(report["artifact_refs"]), expected_refs)
        self.assertTrue(all(ref["exists"] for ref in report["artifact_refs"].values()))
        self.assertEqual(report["summary"]["bundle_verification_status"], "pass")
        self.assertEqual(report["summary"]["monitoring_policy_valid"], True)
        self.assertFalse(report["summary"]["live_external_actions_attempted"])

    def test_validation_rejects_no_go_without_explicit_blockers(self):
        with tempfile.TemporaryDirectory() as directory:
            context = self._context(directory)
            report = production_go_no_go_report(**context)
            report["blockers"] = []

        validation = validate_production_go_no_go_report(report)
        self.assertFalse(validation["valid"])
        self.assertTrue(any("No-go status must include explicit blockers" in issue["message"] for issue in validation["issues"]))

    def test_write_go_no_go_outputs_json(self):
        with tempfile.TemporaryDirectory() as directory:
            context = self._context(directory)
            output_path = Path(directory) / "production_go_no_go_report.json"
            payload = write_production_go_no_go_report(output_path, **context)
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(written, payload["report"])
        self.assertTrue(payload["validation"]["valid"], payload["validation"]["issues"])
        self.assertGreater(payload["bytes"], 0)

    def test_go_no_go_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as directory:
            context = self._context(directory)
            output_path = Path(directory) / "production_go_no_go_report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/publication/production_go_no_go.py",
                    "--output",
                    str(output_path),
                    "--release-manifest",
                    str(context["release_manifest_path"]),
                    "--bundle-verification",
                    str(context["bundle_verification_path"]),
                    "--human-signoff",
                    str(context["human_signoff_path"]),
                    "--deployment-manifest",
                    str(context["deployment_manifest_path"]),
                    "--monitoring-policy",
                    str(context["monitoring_policy_path"]),
                    "--dry-run-report",
                    str(context["dry_run_report_path"]),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("no_go -- blockers=", completed.stdout)
        self.assertEqual(report["status"], "no_go")


if __name__ == "__main__":
    unittest.main()
