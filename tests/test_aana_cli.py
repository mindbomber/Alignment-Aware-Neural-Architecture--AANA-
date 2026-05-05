import importlib.util
import io
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


aana_cli = load_script("aana_cli", ROOT / "scripts" / "aana_cli.py")


class AanaCliTests(unittest.TestCase):
    def run_cli(self, args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = aana_cli.main(args)
        return code, output.getvalue()

    def test_list_shows_gallery_adapters(self):
        code, output = self.run_cli(["list"])

        self.assertEqual(code, 0)
        self.assertIn("travel_planning", output)
        self.assertIn("meal_planning", output)
        self.assertIn("support_reply", output)
        self.assertIn("research_summary", output)

    def test_doctor_reports_platform_readiness(self):
        code, output = self.run_cli(["doctor"])

        self.assertEqual(code, 0)
        self.assertIn("AANA doctor", output)
        self.assertIn("adapter_gallery", output)
        self.assertIn("agent_event_examples", output)

    def test_doctor_json_reports_checks(self):
        code, output = self.run_cli(["doctor", "--json"])

        self.assertEqual(code, 0)
        self.assertIn('"valid": true', output)
        self.assertIn('"agent_schemas"', output)

    def test_production_preflight_lists_external_gates(self):
        code, output = self.run_cli(["production-preflight"])

        self.assertEqual(code, 0)
        self.assertIn("AANA production preflight", output)
        self.assertIn("external_deployment_gates", output)
        self.assertIn("TLS termination", output)

    def test_production_preflight_json_reports_not_fully_ready(self):
        code, output = self.run_cli(["production-preflight", "--json"])

        self.assertEqual(code, 0)
        self.assertIn('"production_ready": false', output)
        self.assertIn('"external_deployment_gates"', output)

    def test_production_preflight_accepts_evidence_registry(self):
        code, output = self.run_cli(
            [
                "production-preflight",
                "--evidence-registry",
                "examples/evidence_registry.json",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("evidence_registry", output)
        self.assertIn("Evidence registry is production-ready", output)

    def test_validate_deployment_template_is_production_ready(self):
        code, output = self.run_cli(
            [
                "validate-deployment",
                "--deployment-manifest",
                "examples/production_deployment_template.json",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("Deployment manifest is production-ready", output)

    def test_validate_governance_template_is_production_ready(self):
        code, output = self.run_cli(
            [
                "validate-governance",
                "--governance-policy",
                "examples/human_governance_policy_template.json",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("Governance policy is production-ready", output)

    def test_validate_observability_policy_is_production_ready(self):
        code, output = self.run_cli(
            [
                "validate-observability",
                "--observability-policy",
                "examples/observability_policy.json",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("Observability policy is production-ready", output)

    def test_production_preflight_accepts_deployment_manifest(self):
        code, output = self.run_cli(
            [
                "production-preflight",
                "--deployment-manifest",
                "examples/production_deployment_template.json",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("deployment_manifest", output)
        self.assertIn("Deployment manifest is production-ready", output)

    def test_release_check_reports_governance_and_preflight_warnings(self):
        code, output = self.run_cli(["release-check", "--skip-local-check"])

        self.assertEqual(code, 0)
        self.assertIn("AANA release check", output)
        self.assertIn("governance_policy", output)
        self.assertIn("production_preflight", output)
        self.assertIn("observability_policy", output)

    def test_release_check_accepts_observability_policy(self):
        code, output = self.run_cli(
            [
                "release-check",
                "--skip-local-check",
                "--deployment-manifest",
                "examples/production_deployment_template.json",
                "--governance-policy",
                "examples/human_governance_policy_template.json",
                "--evidence-registry",
                "examples/evidence_registry.json",
                "--observability-policy",
                "examples/observability_policy.json",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("observability_policy", output)
        self.assertIn("Observability policy is production-ready", output)

    def test_run_gallery_adapter(self):
        code, output = self.run_cli(["run", "support_reply"])

        self.assertEqual(code, 0)
        self.assertIn('"gate_decision": "pass"', output)
        self.assertIn('"recommended_action": "revise"', output)

    def test_run_research_summary_adapter(self):
        code, output = self.run_cli(["run", "research_summary"])

        self.assertEqual(code, 0)
        self.assertIn('"candidate_gate": "block"', output)
        self.assertIn('"gate_decision": "pass"', output)
        self.assertIn('"recommended_action": "revise"', output)
        self.assertIn("Grounded research summary", output)

    def test_validate_gallery_runs_examples(self):
        code, output = self.run_cli(["validate-gallery", "--run-examples"])

        self.assertEqual(code, 0)
        self.assertIn("support_reply", output)

    def test_run_file_support_adapter(self):
        code, output = self.run_cli(
            [
                "run-file",
                "--adapter",
                "examples/support_reply_adapter.json",
                "--prompt",
                "Draft a customer-support reply for a refund request. Use only verified facts: customer name is Maya Chen, order ID and refund eligibility are not available.",
                "--candidate",
                "Hi Maya, order #A1842 is eligible for a full refund and your card ending 4242 will be credited in 3 days.",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn('"candidate_gate": "block"', output)

    def test_scaffold_creates_adapter_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, output = self.run_cli(["scaffold", "insurance claim triage", "--output-dir", tmp])

            self.assertEqual(code, 0)
            self.assertIn("insurance_claim_triage_adapter.json", output)
            self.assertTrue((pathlib.Path(tmp) / "insurance_claim_triage_adapter.json").exists())

    def test_agent_check_support_event(self):
        code, output = self.run_cli(["agent-check", "--event", "examples/agent_event_support_reply.json"])

        self.assertEqual(code, 0)
        self.assertIn('"agent": "openclaw"', output)
        self.assertIn('"gate_decision": "pass"', output)
        self.assertIn('"recommended_action": "revise"', output)
        self.assertIn('"safe_response"', output)

    def test_agent_check_writes_redacted_audit_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "audit.jsonl"
            code, output = self.run_cli(
                [
                    "agent-check",
                    "--event",
                    "examples/agent_event_support_reply.json",
                    "--audit-log",
                    str(audit_log),
                ]
            )
            summary_code, summary_output = self.run_cli(["audit-summary", "--audit-log", str(audit_log)])

            self.assertEqual(code, 0)
            self.assertEqual(summary_code, 0)
            self.assertTrue(audit_log.exists())
            log_text = audit_log.read_text(encoding="utf-8")
            self.assertIn("agent_check", log_text)
            self.assertIn("AANA audit summary", summary_output)
            self.assertIn("revise", summary_output)
            self.assertNotIn("card ending 4242", log_text)
            self.assertIn('"safe_response"', output)

    def test_policy_presets_lists_agent_workflows(self):
        code, output = self.run_cli(["policy-presets"])

        self.assertEqual(code, 0)
        self.assertIn("message_send", output)
        self.assertIn("code_commit", output)
        self.assertIn("private_data_use", output)
        self.assertIn("research_summary", output)

    def test_validate_event_accepts_support_event(self):
        code, output = self.run_cli(["validate-event", "--event", "examples/agent_event_support_reply.json"])

        self.assertEqual(code, 0)
        self.assertIn("Agent event is valid", output)

    def test_agent_schema_prints_event_schema(self):
        code, output = self.run_cli(["agent-schema", "agent_event"])

        self.assertEqual(code, 0)
        self.assertIn("AANA Agent Event", output)
        self.assertIn("adapter_id", output)

    def test_workflow_check_runs_contract_request(self):
        code, output = self.run_cli(
            [
                "workflow-check",
                "--adapter",
                "research_summary",
                "--request",
                "Write a concise research brief. Use only Source A and Source B. Label uncertainty.",
                "--candidate",
                "AANA improves productivity by 40% for all teams [Source C].",
                "--evidence",
                "Source A: AANA makes constraints explicit.",
                "--evidence",
                "Source B: Source coverage can be incomplete.",
                "--constraint",
                "Do not invent citations.",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn('"contract_version": "0.1"', output)
        self.assertIn('"adapter": "research_summary"', output)
        self.assertIn('"recommended_action": "revise"', output)

    def test_workflow_check_accepts_file_request(self):
        code, output = self.run_cli(["workflow-check", "--workflow", "examples/workflow_research_summary.json"])

        self.assertEqual(code, 0)
        self.assertIn('"workflow_id": "demo-workflow-research-summary-001"', output)
        self.assertIn('"adapter": "research_summary"', output)
        self.assertIn('"recommended_action": "revise"', output)

    def test_workflow_batch_runs_contract_requests(self):
        code, output = self.run_cli(["workflow-batch", "--batch", "examples/workflow_batch_productive_work.json"])

        self.assertEqual(code, 0)
        self.assertIn('"batch_id": "demo-batch-productive-work-001"', output)
        self.assertIn('"total": 3', output)
        self.assertIn('"failed": 0', output)

    def test_workflow_batch_writes_per_item_audit_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "workflow-audit.jsonl"
            code, _ = self.run_cli(
                [
                    "workflow-batch",
                    "--batch",
                    "examples/workflow_batch_productive_work.json",
                    "--audit-log",
                    str(audit_log),
                ]
            )
            summary_code, summary_output = self.run_cli(["audit-summary", "--audit-log", str(audit_log), "--json"])

            self.assertEqual(code, 0)
            self.assertEqual(summary_code, 0)
            self.assertEqual(len(audit_log.read_text(encoding="utf-8").strip().splitlines()), 3)
            self.assertIn('"total": 3', summary_output)
            self.assertIn('"workflow_check": 3', summary_output)

    def test_validate_workflow_accepts_example(self):
        code, output = self.run_cli(["validate-workflow", "--workflow", "examples/workflow_research_summary.json"])

        self.assertEqual(code, 0)
        self.assertIn("Workflow request is valid", output)

    def test_validate_workflow_batch_accepts_example(self):
        code, output = self.run_cli(["validate-workflow-batch", "--batch", "examples/workflow_batch_productive_work.json"])

        self.assertEqual(code, 0)
        self.assertIn("Workflow batch request is valid", output)

    def test_validate_evidence_registry_accepts_example(self):
        code, output = self.run_cli(["validate-evidence-registry", "--evidence-registry", "examples/evidence_registry.json"])

        self.assertEqual(code, 0)
        self.assertIn("Evidence registry is valid", output)

    def test_validate_workflow_evidence_accepts_structured_example(self):
        code, output = self.run_cli(
            [
                "validate-workflow-evidence",
                "--workflow",
                "examples/workflow_research_summary_structured.json",
                "--evidence-registry",
                "examples/evidence_registry.json",
                "--require-structured",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("Workflow evidence is production-ready", output)

    def test_workflow_check_rejects_unstructured_evidence_when_required(self):
        code, output = self.run_cli(
            [
                "workflow-check",
                "--workflow",
                "examples/workflow_research_summary.json",
                "--evidence-registry",
                "examples/evidence_registry.json",
                "--require-structured-evidence",
            ]
        )

        self.assertEqual(code, 1)
        self.assertIn("evidence_validation", output)

    def test_workflow_check_accepts_structured_evidence_registry(self):
        code, output = self.run_cli(
            [
                "workflow-check",
                "--workflow",
                "examples/workflow_research_summary_structured.json",
                "--evidence-registry",
                "examples/evidence_registry.json",
                "--require-structured-evidence",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn('"gate_decision": "pass"', output)

    def test_workflow_schema_prints_request_schema(self):
        code, output = self.run_cli(["workflow-schema", "workflow_request"])

        self.assertEqual(code, 0)
        self.assertIn("AANA Workflow Request", output)
        self.assertIn("adapter", output)

    def test_workflow_schema_prints_batch_schema(self):
        code, output = self.run_cli(["workflow-schema", "workflow_batch_request"])

        self.assertEqual(code, 0)
        self.assertIn("AANA Workflow Batch Request", output)
        self.assertIn("requests", output)

    def test_run_agent_examples(self):
        code, output = self.run_cli(["run-agent-examples"])

        self.assertEqual(code, 0)
        self.assertIn("demo-support-refund-001", output)
        self.assertIn("demo-travel-booking-001", output)
        self.assertIn("demo-meal-planning-001", output)
        self.assertIn("demo-research-summary-001", output)

    def test_scaffold_agent_event_creates_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, output = self.run_cli(["scaffold-agent-event", "support_reply", "--output-dir", tmp])

            self.assertEqual(code, 0)
            self.assertIn("support_reply.json", output)
            self.assertTrue((pathlib.Path(tmp) / "support_reply.json").exists())


if __name__ == "__main__":
    unittest.main()
