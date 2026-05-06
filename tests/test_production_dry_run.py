import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.production_dry_run import (
    PRODUCTION_DRY_RUN_REPORT_TYPE,
    run_production_dry_run,
)


ROOT = Path(__file__).resolve().parents[1]


class ProductionDryRunTests(unittest.TestCase):
    def test_dry_run_executes_release_and_blocks_with_explicit_unresolved_items(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = run_production_dry_run(
                output_path=root / "production_dry_run_report.json",
                release_report_path=root / "release" / "aana_mi_release_report.json",
                rc_report_path=root / "rc" / "aana_mi_release_candidate_report.json",
                benchmark_dir=root / "benchmark",
                bundle_dir=root / "bundle",
                deployment_manifest_path=root / "bundle" / "production_deployment_manifest.json",
                human_signoff_path=root / "bundle" / "human_signoff.json",
                live_connector_plan_path=root / "bundle" / "live_connector_readiness_plan.json",
            )
            report = payload["report"]
            written = json.loads(Path(payload["path"]).read_text(encoding="utf-8"))

        self.assertEqual(written, report)
        self.assertEqual(report["report_type"], PRODUCTION_DRY_RUN_REPORT_TYPE)
        self.assertEqual(report["status"], "block")
        self.assertFalse(report["live_external_actions_attempted"])
        self.assertEqual(report["release_report"]["status"], "pass")
        self.assertEqual(report["deployment_manifest"]["deployment_status"], "blocked")
        self.assertIn("human_signoff_not_approved", report["deployment_manifest"]["blockers"])
        self.assertGreater(report["unresolved_item_count"], 0)
        self.assertTrue(report["gate_confirmation"]["unresolved_items_explicit"])

    def test_dry_run_report_confirms_no_live_external_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = run_production_dry_run(
                output_path=root / "dry_run.json",
                release_report_path=root / "release.json",
                rc_report_path=root / "rc.json",
                benchmark_dir=root / "benchmark",
                bundle_dir=root / "bundle",
                deployment_manifest_path=root / "bundle" / "production_deployment_manifest.json",
                human_signoff_path=root / "bundle" / "human_signoff.json",
                live_connector_plan_path=root / "bundle" / "live_connector_readiness_plan.json",
            )
            report = payload["report"]

        self.assertFalse(report["allow_direct_execution"])
        self.assertTrue(report["gate_confirmation"]["external_actions_blocked"])
        self.assertEqual(report["stages"][-1]["name"], "live_external_actions")
        self.assertEqual(report["stages"][-1]["status"], "pass")

    def test_production_dry_run_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_path = root / "production_dry_run_report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/production_dry_run.py",
                    "--output",
                    str(output_path),
                    "--release-report",
                    str(root / "release.json"),
                    "--rc-report",
                    str(root / "rc.json"),
                    "--benchmark-dir",
                    str(root / "benchmark"),
                    "--bundle-dir",
                    str(root / "bundle"),
                    "--deployment-manifest",
                    str(root / "bundle" / "production_deployment_manifest.json"),
                    "--human-signoff",
                    str(root / "bundle" / "human_signoff.json"),
                    "--live-connector-plan",
                    str(root / "bundle" / "live_connector_readiness_plan.json"),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("block -- stages=4", completed.stdout)
        self.assertEqual(report["status"], "block")


if __name__ == "__main__":
    unittest.main()
