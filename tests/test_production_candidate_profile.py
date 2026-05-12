import copy
import pathlib
import tempfile
import unittest

import aana
from eval_pipeline import aix_audit, production_candidate_check, production_candidate_profile
from scripts import aana_cli


class ProductionCandidateProfileTests(unittest.TestCase):
    def test_default_profile_validates_as_candidate_but_not_go_live(self):
        profile = production_candidate_profile.default_production_candidate_profile()
        report = production_candidate_profile.validate_production_candidate_profile(profile)

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["production_candidate_ready"])
        self.assertFalse(report["go_live_ready"])
        self.assertGreaterEqual(report["warnings"], 1)
        self.assertIn("not production certification", profile["claim_boundary"].lower())
        self.assertIn("live_connector_config", report["component_reports"])
        self.assertIn("human_review_export", report["component_reports"])
        self.assertIn("live_monitoring", report["component_reports"])
        self.assertEqual(report["component_reports"]["live_connector_config"]["summary"]["write_enabled_count"], 0)

    def test_profile_requires_fail_closed_direct_execution_rule(self):
        profile = production_candidate_profile.default_production_candidate_profile()
        profile = copy.deepcopy(profile)
        profile["runtime"]["direct_execution_rule"]["recommended_action"] = "revise"

        report = production_candidate_profile.validate_production_candidate_profile(profile)

        self.assertFalse(report["valid"])
        paths = {issue["path"] for issue in report["issues"]}
        self.assertIn("runtime.direct_execution_rule.recommended_action", paths)

    def test_write_and_cli_validate_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "production-candidate-profile.json"
            write = production_candidate_profile.write_production_candidate_profile(path)
            code = aana_cli.main(["production-candidate-profile", "--profile", str(path)])

            self.assertTrue(path.exists())
            self.assertTrue(write["validation"]["valid"], write["validation"])
            self.assertEqual(code, 0)

    def test_public_exports_include_profile_helpers(self):
        profile = aana.default_production_candidate_profile()

        self.assertEqual(aana.PRODUCTION_CANDIDATE_PROFILE_VERSION, "0.1")
        self.assertEqual(profile["profile_type"], "aana_production_candidate_profile")
        self.assertTrue(aana.validate_production_candidate_profile(profile)["valid"])

    def test_production_candidate_check_profile_only_warns_but_is_valid(self):
        report = production_candidate_check.production_candidate_check(
            profile_path="examples/production_candidate_profile_enterprise_support.json"
        )

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["production_candidate_ready"])
        self.assertFalse(report["go_live_ready"])
        self.assertEqual(report["status"], "warn")
        self.assertIn("not production certification", report["claim_boundary"].lower())

    def test_production_candidate_check_validates_shadow_artifact_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = aix_audit.run_enterprise_ops_aix_audit(output_dir=temp_dir, shadow_mode=True)
            audit_log = pathlib.Path(result["summary"]["audit_log"])
            aana.export_runtime_human_review_queue(
                audit_log,
                queue_path=pathlib.Path(temp_dir) / "human-review-queue.jsonl",
                summary_path=pathlib.Path(temp_dir) / "human-review-summary.json",
            )
            aana.live_monitoring_report_jsonl(
                audit_log,
                output_path=pathlib.Path(temp_dir) / "live-monitoring-report.json",
            )
            aana.import_audit_log_to_durable_storage(
                audit_log,
                audit_path=pathlib.Path(temp_dir) / "durable-audit.jsonl",
                manifest_path=pathlib.Path(temp_dir) / "durable-audit.jsonl.sha256.json",
            )
            aana.run_enterprise_support_connector_smoke(
                output_path=pathlib.Path(temp_dir) / "live-connectors-smoke.json",
                mode="dry_run",
            )
            report_json = pathlib.Path(temp_dir) / "production-candidate-aix-report.json"
            report_json.write_text(
                '{"report_type":"aana_production_candidate_aix_report","claim_boundary":"Production-candidate evidence only; this is not production certification or go-live approval.","deployment_recommendation":"production_candidate_with_controls_not_go_live_ready","executive_summary":{"go_live_ready":false}}',
                encoding="utf-8",
            )

            report = production_candidate_check.production_candidate_check(
                profile_path="examples/production_candidate_profile_enterprise_support.json",
                artifact_dir=temp_dir,
            )

            self.assertTrue(report["valid"], report)
            self.assertTrue(report["production_candidate_ready"])
            self.assertFalse(report["go_live_ready"])
            self.assertIn(report["status"], {"warn", "pass"})
            self.assertEqual(report["artifact_summary"]["audit_records"], 8)
            self.assertEqual(report["artifact_summary"]["human_review_packets"], 2)
            self.assertIn("live_monitoring", report["component_reports"])

    def test_cli_production_candidate_check_runs(self):
        code = aana_cli.main(
            [
                "production-candidate-check",
                "--profile",
                "examples/production_candidate_profile_enterprise_support.json",
            ]
        )

        self.assertEqual(code, 0)

    def test_public_exports_include_production_candidate_check(self):
        report = aana.production_candidate_check(profile_path="examples/production_candidate_profile_enterprise_support.json")

        self.assertEqual(aana.PRODUCTION_CANDIDATE_CHECK_VERSION, "0.1")
        self.assertEqual(report["check_type"], "aana_production_candidate_check")
        self.assertTrue(report["valid"])


if __name__ == "__main__":
    unittest.main()
