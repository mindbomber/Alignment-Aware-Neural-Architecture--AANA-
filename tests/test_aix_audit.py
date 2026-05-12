import json
import pathlib
import tempfile
import unittest

from eval_pipeline import aix_audit


class AIxAuditTests(unittest.TestCase):
    def test_enterprise_ops_aix_audit_writes_report_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = aix_audit.run_enterprise_ops_aix_audit(output_dir=temp_dir)
            summary = report["summary"]

            self.assertTrue(report["valid"], report["aix_report_validation"])
            self.assertEqual(report["product"], "AANA AIx Audit")
            self.assertEqual(report["product_bundle"], "enterprise_ops_pilot")
            self.assertIn(
                report["deployment_recommendation"],
                {"pilot_ready", "pilot_ready_with_controls", "not_pilot_ready", "insufficient_evidence"},
            )
            self.assertGreater(summary["workflow_count"], 0)
            self.assertGreater(summary["audit_records"], 0)
            for key in [
                "audit_log",
                "metrics",
                "drift_report",
                "integrity_manifest",
                "enterprise_dashboard",
                "enterprise_connector_readiness",
                "aix_report_json",
                "aix_report_md",
            ]:
                self.assertTrue(pathlib.Path(summary[key]).exists(), key)
            self.assertTrue(report["adapter_config_validation"]["valid"], report["adapter_config_validation"])
            self.assertTrue(report["calibration_fixture_validation"]["valid"], report["calibration_fixture_validation"])
            self.assertTrue(aix_audit.validate_aix_report(report["aix_report"])["valid"])
            aix_report = report["aix_report"]
            self.assertIn("use_case_scope", aix_report)
            self.assertEqual(aix_report["use_case_scope"]["deployment_boundary"], "pilot_ready_evidence_only_not_production_certification")
            self.assertIn("failure_modes", aix_report)
            self.assertIn("top_violation_codes", aix_report["failure_modes"])
            self.assertIn("evidence_appendix", aix_report)
            self.assertFalse(aix_report["evidence_appendix"]["raw_payload_logged"])
            self.assertGreater(len(aix_report["evidence_appendix"]["entries"]), 0)
            dashboard = json.loads(pathlib.Path(summary["enterprise_dashboard"]).read_text(encoding="utf-8"))
            connector_readiness = json.loads(pathlib.Path(summary["enterprise_connector_readiness"]).read_text(encoding="utf-8"))
            self.assertEqual(connector_readiness["summary"]["connector_count"], 7)
            self.assertEqual(connector_readiness["summary"]["live_execution_enabled_count"], 0)
            self.assertEqual(dashboard["source_of_truth"], "redacted_audit_metrics")
            self.assertEqual(
                {item["id"] for item in dashboard["surface_breakdown"]},
                {"support_customer_communications", "data_access_controls", "devops_release_controls"},
            )
            self.assertIn("shadow_would_intervene", dashboard["cards"])
            markdown = pathlib.Path(summary["aix_report_md"]).read_text(encoding="utf-8")
            self.assertIn("AANA AIx Report: Enterprise Ops Pilot", markdown)
            self.assertIn("## Use-Case Scope", markdown)
            self.assertIn("## Failure Modes", markdown)
            self.assertIn("## Tested Workflows", markdown)
            self.assertIn("| Workflow | Surface | Adapter | Gate | Action | AIx | Blockers |", markdown)
            self.assertIn("## Evidence Appendix", markdown)
            self.assertIn("## Monitoring Plan", markdown)
            self.assertIn("Pilot readiness is not production certification", markdown)

    def test_enterprise_adapter_config_declares_required_aix_metadata(self):
        config = aix_audit.load_enterprise_adapter_config()
        validation = aix_audit.validate_enterprise_adapter_config(config)

        self.assertTrue(validation["valid"], validation)
        self.assertEqual(validation["adapter_count"], 9)
        required = set(aix_audit.REQUIRED_ADAPTER_DECLARATION_FIELDS)
        for adapter in config["adapters"]:
            self.assertLessEqual(required, set(adapter))
            self.assertIn(adapter["surface"], {"support_customer_communications", "data_access_controls", "devops_release_controls"})

    def test_enterprise_calibration_fixtures_cover_routes_and_failure_modes(self):
        fixtures = aix_audit.load_enterprise_calibration_fixtures()
        validation = aix_audit.validate_enterprise_calibration_fixtures(fixtures)

        self.assertTrue(validation["valid"], validation)
        self.assertLessEqual(set(aix_audit.REQUIRED_CALIBRATION_CASES), set(validation["covered_case_types"]))
        self.assertLessEqual({"accept", "revise", "ask", "defer", "refuse"}, set(validation["covered_routes"]))

    def test_aix_report_requires_pilot_not_certification_boundary(self):
        report = {
            "aix_report_schema_version": "0.1",
            "report_type": "aana_aix_report",
            "product": "AANA AIx Audit",
            "deployment_recommendation": "pilot_ready",
            "overall_aix": {},
            "component_scores": {},
            "risk_tier": "enterprise_ops_pilot",
            "use_case_scope": {},
            "tested_workflows": [],
            "hard_blockers": [],
            "evidence_quality": {},
            "verifier_coverage": {},
            "calibration_confidence": {},
            "failure_modes": {},
            "remediation_plan": [],
            "evidence_appendix": {},
            "human_review_requirements": [],
            "monitoring_plan": [],
            "limitations": ["Pilot only."],
            "audit_metadata": {},
        }

        validation = aix_audit.validate_aix_report(report)

        self.assertFalse(validation["valid"])
        self.assertTrue(any("AIx Reports must state" in issue["message"] for issue in validation["issues"]))


if __name__ == "__main__":
    unittest.main()
