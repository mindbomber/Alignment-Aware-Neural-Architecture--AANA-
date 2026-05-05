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

    def external_evidence_manifest(self):
        policy = self.load_json("examples/production_certification_template.json")
        return {
            "external_evidence_version": "0.1",
            "evidence_scope": "external_deployment",
            "connector_manifests": [
                {
                    "connector_id": connector_id,
                    "manifest_uri": f"https://ops.example/aana/connectors/{connector_id}.json",
                    "environment": "production",
                    "owner": "Domain Operations",
                    "auth_boundary": "Read-only, tenant-scoped evidence retrieval credentials.",
                    "freshness_slo": "Connector enforces the approved production freshness SLO.",
                    "redaction_policy": "Connector returns redacted summaries and keeps raw records in the source system.",
                    "failure_modes": ["unauthorized", "stale_evidence", "unredacted_evidence", "connector_unavailable"],
                }
                for connector_id in policy["connector_evidence"]["required_connectors"]
            ],
            "shadow_mode_logs": {
                "audit_log_uri": "s3://prod-aana-audit/shadow-mode.jsonl",
                "environment": "production",
                "redacted": True,
                "retention_policy_ref": "prod-aana-audit-retention",
            },
            "audit_retention_policy": {
                "policy_uri": "https://ops.example/aana/policies/audit-retention",
                "owner": "Security and Compliance",
                "retention_days": 365,
                "immutable": True,
            },
            "escalation_policy": {
                "policy_uri": "https://ops.example/aana/policies/escalation",
                "owner": "Governance Operations",
                "human_review_queue": "AANA Production Human Review",
                "covers": ["high-impact decisions", "low-confidence verifier results", "irreversible external actions"],
            },
            "owner_approval": {
                "approval_uri": "https://ops.example/aana/approvals/domain-owner",
                "domain_owner": "Named Domain Owner",
                "approved_at": "2026-05-05T00:00:00Z",
                "scope": "production",
            },
        }

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
        self.assertIn("not production-certified", boundary["demo"]["certification_line"])

    def test_public_readiness_matrix_defines_family_specific_gates(self):
        matrix = production_certification.certification_program_matrix()

        self.assertEqual(set(matrix["levels"]), {"demo_ready", "pilot_ready", "production_ready"})
        self.assertEqual(set(matrix["families"]), {"enterprise", "personal_productivity", "government_civic"})
        self.assertIn("not production-certified by itself", matrix["production_positioning"])
        self.assertIn("boundary checker", matrix["certification_scope"])
        self.assertIn("external_connector_manifests", matrix["levels"]["production_ready"]["required_gates"])
        self.assertIn("connector_freshness", matrix["families"]["enterprise"]["required_gates"])
        self.assertIn("local_only_default", matrix["families"]["personal_productivity"]["required_gates"])
        self.assertIn("source_law_traceability", matrix["families"]["government_civic"]["required_gates"])

    def test_production_certification_fails_without_shadow_audit_and_operating_artifacts(self):
        report = production_certification.production_certification_report_from_paths(
            certification_policy_path=ROOT / "examples" / "production_certification_template.json",
        )

        self.assertFalse(report["valid"])
        self.assertFalse(report["production_ready"])
        self.assertFalse(report["repo_local_ready"])
        self.assertFalse(report["deployment_ready"])
        self.assertEqual(report["summary"]["readiness_level"], "repo_local_not_ready")
        self.assertIn("live evidence connectors", report["production_positioning"])
        failed = {check["name"] for check in report["checks"] if check["status"] == "fail"}
        self.assertIn("shadow_mode_evidence", failed)
        self.assertIn("deployment_manifest", failed)
        self.assertIn("governance_policy", failed)

    def test_complete_synthetic_bundle_is_repo_local_ready_but_not_deployment_ready(self):
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

        self.assertFalse(report["valid"], report)
        self.assertTrue(report["repo_local_ready"], report)
        self.assertFalse(report["deployment_ready"], report)
        self.assertFalse(report["production_ready"], report)
        self.assertEqual(report["summary"]["readiness_level"], "external_evidence_required")
        shadow = next(check for check in report["checks"] if check["name"] == "shadow_mode_evidence")
        self.assertEqual(shadow["details"]["shadow_record_count"], 100)
        self.assertGreaterEqual(shadow["details"]["duration_days"], 14)
        external = next(check for check in report["checks"] if check["name"] == "external_production_evidence")
        self.assertEqual(external["status"], "fail")

    def test_external_evidence_manifest_enables_deployment_boundary_but_not_certification_guarantee(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "shadow-audit.jsonl"
            external_evidence_path = pathlib.Path(tmp) / "external-evidence.json"
            self.write_shadow_audit(audit_log)
            external_evidence_path.write_text(json.dumps(self.external_evidence_manifest()), encoding="utf-8")
            report = production_certification.production_certification_report_from_paths(
                certification_policy_path=ROOT / "examples" / "production_certification_template.json",
                deployment_manifest_path=ROOT / "examples" / "production_deployment_template.json",
                governance_policy_path=ROOT / "examples" / "human_governance_policy_template.json",
                evidence_registry_path=ROOT / "examples" / "evidence_registry.json",
                observability_policy_path=ROOT / "examples" / "observability_policy.json",
                audit_log_path=audit_log,
                external_evidence_path=external_evidence_path,
            )

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["repo_local_ready"], report)
        self.assertTrue(report["deployment_ready"], report)
        self.assertTrue(report["production_ready"], report)
        self.assertFalse(report["production_certified"], report)
        self.assertTrue(report["production_claim_allowed"], report)
        self.assertEqual(report["summary"]["readiness_level"], "deployment_ready")

    def test_cli_production_certify_json_reports_not_ready_without_required_artifacts(self):
        output = StringIO()
        with redirect_stdout(output):
            code = aana_cli.main(["production-certify", "--json"])
        report = json.loads(output.getvalue())

        self.assertEqual(code, 1)
        self.assertFalse(report["production_ready"])
        self.assertFalse(report["deployment_ready"])
        self.assertEqual(report["summary"]["readiness_level"], "repo_local_not_ready")

    def test_external_evidence_template_is_shape_only_not_production_evidence(self):
        template = self.load_json("examples/external_production_evidence_template.json")
        policy = self.load_json("examples/production_certification_template.json")
        report = production_certification.validate_external_evidence_manifest(template, policy)

        self.assertFalse(report["valid"])
        self.assertIn("evidence_scope", {issue["path"].split(".")[-1] for issue in report["issues"]})

    def test_cli_contract_lists_production_certify(self):
        commands = {item["command"] for item in aana_cli.cli_command_matrix()}

        self.assertIn("production-certify", commands)
        self.assertIn("readiness-matrix", commands)


if __name__ == "__main__":
    unittest.main()
