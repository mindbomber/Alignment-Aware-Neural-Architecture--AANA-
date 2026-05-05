import datetime
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from eval_pipeline import agent_api, production_certification
from scripts import aana_cli


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProductionCertificationTests(unittest.TestCase):
    def load_json(self, relative_path):
        return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))

    def write_shadow_audit(self, path, records=100, duration_days=15):
        event = self.load_json("examples/agent_event_support_reply.json")
        result = agent_api.apply_shadow_mode(agent_api.check_event(event))
        start = datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc)
        total_seconds = duration_days * 24 * 60 * 60
        for index in range(records):
            offset = int((total_seconds * index) / max(records - 1, 1))
            created_at = (start + datetime.timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")
            record = agent_api.audit_event_check(event, result=result, created_at=created_at, shadow_mode=True)
            agent_api.append_audit_record(path, record)

    def test_certification_policy_defines_required_production_gates(self):
        policy = self.load_json("examples/production_certification_template.json")
        report = production_certification.validate_certification_policy(policy)

        self.assertTrue(report["valid"], report)
        self.assertIn("shadow_records_total", policy["metrics"]["required"])
        self.assertGreaterEqual(policy["shadow_mode"]["minimum_duration_days"], 14)
        self.assertGreaterEqual(policy["audit_retention"]["minimum_days"], 365)

    def test_readiness_boundary_draws_demo_pilot_production_line(self):
        boundary = production_certification.readiness_boundary()

        self.assertEqual(set(boundary), {"demo", "pilot", "production"})
        self.assertIn("Synthetic-only", boundary["demo"]["data"])
        self.assertIn("Shadow", boundary["pilot"]["side_effects"])
        self.assertIn("shadow-mode evidence", boundary["production"]["certification_line"])

    def test_public_readiness_matrix_defines_family_specific_gates(self):
        matrix = production_certification.certification_program_matrix()

        self.assertEqual(set(matrix["levels"]), {"demo_ready", "pilot_ready", "production_ready"})
        self.assertEqual(set(matrix["families"]), {"enterprise", "personal_productivity", "government_civic"})
        self.assertIn("connector_freshness", matrix["families"]["enterprise"]["required_gates"])
        self.assertIn("local_only_default", matrix["families"]["personal_productivity"]["required_gates"])
        self.assertIn("source_law_traceability", matrix["families"]["government_civic"]["required_gates"])

    def test_production_certification_fails_without_shadow_audit_and_operating_artifacts(self):
        report = production_certification.production_certification_report_from_paths(
            certification_policy_path=ROOT / "examples" / "production_certification_template.json",
        )

        self.assertFalse(report["valid"])
        self.assertFalse(report["production_ready"])
        self.assertEqual(report["summary"]["readiness_level"], "not_production_ready")
        failed = {check["name"] for check in report["checks"] if check["status"] == "fail"}
        self.assertIn("shadow_mode_evidence", failed)
        self.assertIn("deployment_manifest", failed)
        self.assertIn("governance_policy", failed)

    def test_production_certification_passes_with_complete_synthetic_shadow_evidence_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "shadow-audit.jsonl"
            self.write_shadow_audit(audit_log)
            report = production_certification.production_certification_report_from_paths(
                certification_policy_path=ROOT / "examples" / "production_certification_template.json",
                deployment_manifest_path=ROOT / "examples" / "production_deployment_template.json",
                governance_policy_path=ROOT / "examples" / "human_governance_policy_template.json",
                evidence_registry_path=ROOT / "examples" / "evidence_registry.json",
                observability_policy_path=ROOT / "examples" / "observability_policy.json",
                audit_log_path=audit_log,
            )

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["production_ready"], report)
        self.assertEqual(report["summary"]["readiness_level"], "production_ready")
        shadow = next(check for check in report["checks"] if check["name"] == "shadow_mode_evidence")
        self.assertEqual(shadow["details"]["shadow_record_count"], 100)
        self.assertGreaterEqual(shadow["details"]["duration_days"], 14)

    def test_cli_production_certify_json_reports_not_ready_without_required_artifacts(self):
        output = StringIO()
        with redirect_stdout(output):
            code = aana_cli.main(["production-certify", "--json"])
        report = json.loads(output.getvalue())

        self.assertEqual(code, 1)
        self.assertFalse(report["production_ready"])
        self.assertEqual(report["summary"]["readiness_level"], "not_production_ready")

    def test_cli_contract_lists_production_certify(self):
        commands = {item["command"] for item in aana_cli.cli_command_matrix()}

        self.assertIn("production-certify", commands)
        self.assertIn("readiness-matrix", commands)


if __name__ == "__main__":
    unittest.main()
