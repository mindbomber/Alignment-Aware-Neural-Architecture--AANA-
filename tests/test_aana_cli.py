import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout


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

    def run_cli_with_stderr(self, args):
        output = io.StringIO()
        error = io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = aana_cli.main(args)
        return code, output.getvalue(), error.getvalue()

    def test_cli_contract_json_reports_command_matrix(self):
        code, output = self.run_cli(["cli-contract", "--json"])
        report = json.loads(output)
        commands = {item["command"]: item for item in report["commands"]}

        self.assertEqual(code, 0)
        self.assertEqual(report["cli_contract_version"], aana_cli.CLI_CONTRACT_VERSION)
        self.assertIn("0", report["exit_codes"])
        self.assertIn("release-check", commands)
        self.assertIn("workflow-check", commands)
        self.assertIn("support-aix-calibration", commands)
        self.assertTrue(commands["scaffold"]["dry_run"])

    def test_missing_input_path_reports_clear_text_error(self):
        code, output, error = self.run_cli_with_stderr(["validate-event", "--event", "missing-event.json"])

        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("event path does not exist: missing-event.json", error)

    def test_missing_input_path_reports_json_error_contract(self):
        code, output, error = self.run_cli_with_stderr(["validate-event", "--event", "missing-event.json", "--json"])
        report = json.loads(output)

        self.assertEqual(code, 2)
        self.assertEqual(error, "")
        self.assertFalse(report["ok"])
        self.assertEqual(report["cli_contract_version"], aana_cli.CLI_CONTRACT_VERSION)
        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["error"]["details"]["argument"], "--event")

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

    def test_contract_freeze_reports_frozen_contracts(self):
        code, output = self.run_cli(["contract-freeze"])

        self.assertEqual(code, 0)
        self.assertIn("AANA contract freeze", output)
        self.assertIn("contract_inventory", output)
        self.assertIn("compatibility_fixtures", output)

    def test_contract_freeze_json_reports_contract_inventory(self):
        code, output = self.run_cli(["contract-freeze", "--json"])

        self.assertEqual(code, 0)
        self.assertIn('"frozen": true', output)
        self.assertIn('"adapter_contract"', output)
        self.assertIn('"audit_metrics_export"', output)

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
        self.assertIn("Evidence registry satisfies production-readiness checks", output)
        self.assertIn("evidence_integrations", output)
        self.assertIn("Evidence registry covers production integration stubs", output)

    def test_validate_deployment_template_is_production_ready(self):
        code, output = self.run_cli(
            [
                "validate-deployment",
                "--deployment-manifest",
                "examples/production_deployment_template.json",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("Deployment manifest is ready for production-readiness review", output)

    def test_validate_governance_template_is_production_ready(self):
        code, output = self.run_cli(
            [
                "validate-governance",
                "--governance-policy",
                "examples/human_governance_policy_template.json",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("Governance policy is ready for production-readiness review", output)

    def test_validate_observability_policy_is_production_ready(self):
        code, output = self.run_cli(
            [
                "validate-observability",
                "--observability-policy",
                "examples/observability_policy.json",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("Observability policy is ready for production-readiness review", output)

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
        self.assertIn("Deployment manifest satisfies production-readiness checks", output)

    def test_release_check_reports_governance_and_preflight_warnings(self):
        code, output = self.run_cli(["release-check", "--skip-local-check"])

        self.assertEqual(code, 0)
        self.assertIn("AANA release check", output)
        self.assertIn("adapter_aix_tuning", output)
        self.assertIn("Adapter AIx tuning meets declared risk tiers", output)
        self.assertIn("adapter_catalog", output)
        self.assertIn("Catalog completeness: 1.0", output)
        self.assertIn("governance_policy", output)
        self.assertIn("production_preflight", output)
        self.assertIn("observability_policy", output)

    def test_release_check_fails_when_adapter_aix_tuning_is_below_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            adapter = json.loads((ROOT / "examples" / "medical_safety_router_adapter.json").read_text(encoding="utf-8"))
            adapter["aix"]["beta"] = 1.0
            adapter_path = tmp_path / "medical_safety_router_adapter.json"
            adapter_path.write_text(json.dumps(adapter), encoding="utf-8")
            gallery = {
                "version": "0.1",
                "description": "Temporary gallery with broken AIx tuning.",
                "adapters": [
                    {
                        "id": "medical_safety_router",
                        "title": "Medical Safety Router",
                        "status": "executable",
                        "adapter_path": str(adapter_path),
                        "workflow": "Route medical-adjacent answers safely.",
                        "best_for": ["medical safety"],
                        "prompt": "General medical safety question.",
                        "bad_candidate": "Take two extra doses and skip urgent care.",
                        "expected": {
                            "candidate_gate": "block",
                            "gate_decision": "pass",
                            "recommended_action": "revise",
                            "failing_constraints": ["medical_information_not_advice"],
                            "aix_decision": "accept",
                            "candidate_aix_decision": "refuse",
                        },
                        "copy_command": "python scripts/adapters/run_adapter.py --adapter medical_safety_router_adapter.json",
                        "caveats": ["Temporary test gallery."],
                    }
                ],
            }
            gallery_path = tmp_path / "adapter_gallery.json"
            gallery_path.write_text(json.dumps(gallery), encoding="utf-8")

            code, output = self.run_cli(["--gallery", str(gallery_path), "release-check", "--skip-local-check"])

        self.assertEqual(code, 1)
        self.assertIn("adapter_aix_tuning", output)
        self.assertIn("below declared risk-tier requirements", output)
        self.assertIn("aix.beta", output)

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
        self.assertIn("Observability policy satisfies production-readiness checks", output)

    def test_release_check_passes_aix_audit_enforcement_for_clean_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "audit.jsonl"
            check_code, _ = self.run_cli(
                [
                    "agent-check",
                    "--event",
                    "examples/agent_event_support_reply.json",
                    "--audit-log",
                    str(audit_log),
                ]
            )
            release_code, release_output = self.run_cli(
                [
                    "release-check",
                    "--skip-local-check",
                    "--audit-log",
                    str(audit_log),
                ]
            )

        self.assertEqual(check_code, 0)
        self.assertEqual(release_code, 0)
        self.assertIn("aix_audit_enforcement", release_output)
        self.assertIn("Audit AIx release gates passed", release_output)

    def test_release_check_fails_aix_audit_enforcement_for_low_score_and_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "audit.jsonl"
            audit_log.write_text(
                json.dumps(
                    {
                        "audit_record_version": "0.1",
                        "record_type": "agent_check",
                        "adapter_id": "deployment_readiness",
                        "gate_decision": "pass",
                        "recommended_action": "defer",
                        "violation_codes": ["rollback_missing"],
                        "aix": {
                            "score": 0.4,
                            "decision": "refuse",
                            "hard_blockers": ["rollback_missing"],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            release_code, release_output = self.run_cli(
                [
                    "release-check",
                    "--skip-local-check",
                    "--audit-log",
                    str(audit_log),
                ]
            )

        self.assertEqual(release_code, 1)
        self.assertIn("aix_audit_enforcement", release_output)
        self.assertIn("Audit AIx release gates failed", release_output)
        self.assertIn("FAIL", release_output)

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

    def test_evidence_integrations_reports_registry_coverage(self):
        code, output = self.run_cli(
            [
                "evidence-integrations",
                "--evidence-registry",
                "examples/evidence_registry.json",
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("AANA evidence connector contracts: valid", output)
        self.assertIn("crm_support", output)
        self.assertIn("deployment", output)

    def test_evidence_integrations_json_reports_templates(self):
        code, output = self.run_cli(
            [
                "evidence-integrations",
                "--evidence-registry",
                "examples/evidence_registry.json",
                "--json",
            ]
        )
        report = json.loads(output)

        self.assertEqual(code, 0)
        self.assertTrue(report["valid"])
        self.assertTrue(report["integrations"][0]["evidence_template"]["metadata"]["stub"])

    def test_aix_tuning_reports_adapter_risk_tiers(self):
        code, output = self.run_cli(["aix-tuning"])

        self.assertEqual(code, 0)
        self.assertIn("AANA adapter AIx tuning report: valid", output)
        self.assertIn("medical_safety_router: tier=strict", output)
        self.assertIn("travel_planning: tier=standard", output)

    def test_aix_tuning_json_reports_strict_adapter(self):
        code, output = self.run_cli(["aix-tuning", "--json"])
        report = json.loads(output)
        adapters = {item["id"]: item for item in report["adapters"]}

        self.assertEqual(code, 0)
        self.assertTrue(report["valid"])
        self.assertEqual(adapters["medical_safety_router"]["risk_tier"], "strict")
        self.assertGreaterEqual(adapters["medical_safety_router"]["beta"], 1.5)

    def test_support_aix_calibration_json_reports_required_metrics(self):
        code, output = self.run_cli(["support-aix-calibration", "--json"])
        report = json.loads(output)

        self.assertEqual(code, 0)
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["metrics"]["over_acceptance_count"], 0)
        self.assertEqual(report["metrics"]["false_blocker_rate"], 0.0)
        self.assertEqual(report["metrics"]["correction_success_rate"], 1.0)

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

    def test_scaffold_dry_run_does_not_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, output = self.run_cli(["scaffold", "insurance claim triage", "--output-dir", tmp, "--dry-run"])
            report = json.loads(output)

            self.assertEqual(code, 0)
            self.assertTrue(report["dry_run"])
            self.assertIn("insurance_claim_triage_adapter.json", report["would_create"]["adapter"])
            self.assertFalse((pathlib.Path(tmp) / "insurance_claim_triage_adapter.json").exists())

    def test_agent_check_support_event(self):
        code, output = self.run_cli(["agent-check", "--event", "examples/agent_event_support_reply.json"])

        self.assertEqual(code, 0)
        self.assertIn('"agent": "openclaw"', output)
        self.assertIn('"gate_decision": "pass"', output)
        self.assertIn('"recommended_action": "revise"', output)
        self.assertIn('"architecture_decision"', output)
        self.assertIn('"route": "revise"', output)
        self.assertIn('"audit_safe_log_event"', output)
        self.assertIn('"safe_response"', output)

    def test_pre_tool_check_exposes_architecture_decision(self):
        code, output = self.run_cli(["pre-tool-check", "--event", "examples/agent_tool_precheck_private_read.json"])

        self.assertEqual(code, 0)
        self.assertIn('"tool_name": "get_recent_transactions"', output)
        self.assertIn('"recommended_action": "accept"', output)
        self.assertIn('"architecture_decision"', output)
        self.assertIn('"route": "accept"', output)
        self.assertIn('"authorization_state": "authenticated"', output)
        self.assertIn('"auth.demo-session"', output)

    def test_pre_tool_check_writes_redacted_audit_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            event_path = tmp_path / "pre_tool_secret.json"
            audit_log = tmp_path / "audit.jsonl"
            event_path.write_text(
                json.dumps(
                    {
                        "tool_name": "send_email",
                        "tool_category": "write",
                        "authorization_state": "confirmed",
                        "evidence_refs": ["draft_id:123"],
                        "risk_domain": "customer_support",
                        "proposed_arguments": {
                            "to": "customer@example.com",
                            "api_key": "sk_live_12345678901234567890",
                        },
                        "recommended_route": "accept",
                    }
                ),
                encoding="utf-8",
            )

            code, output = self.run_cli(["pre-tool-check", "--event", str(event_path), "--audit-log", str(audit_log)])
            validate_code, validate_output = self.run_cli(["audit-validate", "--audit-log", str(audit_log)])
            summary_code, summary_output = self.run_cli(["audit-summary", "--audit-log", str(audit_log)])

            self.assertEqual(code, 1)
            self.assertEqual(validate_code, 0)
            self.assertEqual(summary_code, 0)
            log_text = audit_log.read_text(encoding="utf-8")
            self.assertIn("tool_precheck", log_text)
            self.assertIn("[redacted_sensitive_key]", log_text)
            self.assertIn("AANA audit validation: valid", validate_output)
            self.assertIn("AANA audit summary", summary_output)
            self.assertNotIn("customer@example.com", log_text)
            self.assertNotIn("sk_live", log_text)
            self.assertIn('"audit_record_type": "tool_precheck"', output)

    def test_evidence_pack_command_summarizes_public_boundary(self):
        code, output = self.run_cli(["evidence-pack", "--require-existing-artifacts"])

        self.assertEqual(code, 0)
        self.assertIn("AANA evidence pack", output)
        self.assertIn("AANA makes agents more auditable, safer, more grounded, and more controllable.", output)
        self.assertIn("validation: pass", output)

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

    def test_audit_manifest_and_verify_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "audit.jsonl"
            manifest = pathlib.Path(tmp) / "manifests" / "audit-integrity.json"
            check_code, _ = self.run_cli(
                [
                    "agent-check",
                    "--event",
                    "examples/agent_event_support_reply.json",
                    "--audit-log",
                    str(audit_log),
                ]
            )
            manifest_code, manifest_output = self.run_cli(
                [
                    "audit-manifest",
                    "--audit-log",
                    str(audit_log),
                    "--output",
                    str(manifest),
                ]
            )
            verify_code, verify_output = self.run_cli(["audit-verify", "--manifest", str(manifest)])

            self.assertEqual(check_code, 0)
            self.assertEqual(manifest_code, 0)
            self.assertEqual(verify_code, 0)
            self.assertTrue(manifest.exists())
            self.assertIn("AANA audit integrity manifest created", manifest_output)
            self.assertIn("AANA audit integrity verification: PASS", verify_output)

    def test_audit_metrics_command_writes_dashboard_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "audit.jsonl"
            metrics_path = pathlib.Path(tmp) / "metrics" / "aana-metrics.json"
            check_code, _ = self.run_cli(
                [
                    "agent-check",
                    "--event",
                    "examples/agent_event_support_reply.json",
                    "--audit-log",
                    str(audit_log),
                ]
            )
            metrics_code, metrics_output = self.run_cli(
                [
                    "audit-metrics",
                    "--audit-log",
                    str(audit_log),
                    "--output",
                    str(metrics_path),
                ]
            )

            self.assertEqual(check_code, 0)
            self.assertEqual(metrics_code, 0)
            self.assertTrue(metrics_path.exists())
            metrics_text = metrics_path.read_text(encoding="utf-8")
            self.assertIn("AANA audit metrics export", metrics_output)
            self.assertIn("aix_score_average", metrics_output)
            self.assertIn('"gate_decision_count.pass": 1', metrics_text)
            self.assertIn('"aix_decision_count.accept": 1', metrics_text)

    def test_audit_validate_drift_and_reviewer_report_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "audit.jsonl"
            metrics_path = pathlib.Path(tmp) / "aana-metrics.json"
            drift_path = pathlib.Path(tmp) / "aana-aix-drift.json"
            manifest_path = pathlib.Path(tmp) / "aana-integrity.json"
            reviewer_path = pathlib.Path(tmp) / "aana-reviewer-report.md"
            self.run_cli(
                [
                    "agent-check",
                    "--event",
                    "examples/agent_event_support_reply.json",
                    "--audit-log",
                    str(audit_log),
                ]
            )
            validate_code, validate_output = self.run_cli(["audit-validate", "--audit-log", str(audit_log)])
            metrics_code, _ = self.run_cli(["audit-metrics", "--audit-log", str(audit_log), "--output", str(metrics_path)])
            drift_code, drift_output = self.run_cli(["audit-drift", "--audit-log", str(audit_log), "--output", str(drift_path)])
            manifest_code, _ = self.run_cli(["audit-manifest", "--audit-log", str(audit_log), "--output", str(manifest_path)])
            reviewer_code, reviewer_output = self.run_cli(
                [
                    "audit-reviewer-report",
                    "--audit-log",
                    str(audit_log),
                    "--metrics",
                    str(metrics_path),
                    "--drift-report",
                    str(drift_path),
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(reviewer_path),
                ]
            )

            self.assertEqual(validate_code, 0)
            self.assertEqual(metrics_code, 0)
            self.assertEqual(drift_code, 0)
            self.assertEqual(manifest_code, 0)
            self.assertEqual(reviewer_code, 0)
            self.assertTrue(drift_path.exists())
            self.assertTrue(reviewer_path.exists())
            self.assertIn("AANA audit validation: valid", validate_output)
            self.assertIn("AANA AIx drift report: valid", drift_output)
            self.assertIn("AANA audit reviewer report created", reviewer_output)
            self.assertIn("# AANA Audit Reviewer Report", reviewer_path.read_text(encoding="utf-8"))

    def test_audit_verify_fails_after_log_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "audit.jsonl"
            manifest = pathlib.Path(tmp) / "audit-integrity.json"
            self.run_cli(
                [
                    "agent-check",
                    "--event",
                    "examples/agent_event_support_reply.json",
                    "--audit-log",
                    str(audit_log),
                ]
            )
            self.run_cli(["audit-manifest", "--audit-log", str(audit_log), "--output", str(manifest)])
            audit_log.write_text(audit_log.read_text(encoding="utf-8") + "\n", encoding="utf-8")

            verify_code, verify_output = self.run_cli(["audit-verify", "--manifest", str(manifest)])

            self.assertEqual(verify_code, 1)
            self.assertIn("AANA audit integrity verification: FAIL", verify_output)
            self.assertIn("Audit log SHA-256 does not match", verify_output)

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

    def test_shadow_mode_writes_would_action_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "shadow-audit.jsonl"
            metrics_path = pathlib.Path(tmp) / "shadow-metrics.json"
            code, output = self.run_cli(
                [
                    "agent-check",
                    "--event",
                    "examples/agent_event_support_reply.json",
                    "--audit-log",
                    str(audit_log),
                    "--shadow-mode",
                ]
            )
            metrics_code, metrics_output = self.run_cli(
                [
                    "audit-metrics",
                    "--audit-log",
                    str(audit_log),
                    "--output",
                    str(metrics_path),
                ]
            )

            self.assertEqual(code, 0)
            self.assertIn('"execution_mode": "shadow"', output)
            self.assertIn('"production_effect": "not_blocked"', output)
            self.assertEqual(metrics_code, 0)
            self.assertIn("shadow_would_revise_count: 1", metrics_output)
            metrics = aana_cli.agent_api.load_json_file(metrics_path)
            self.assertEqual(metrics["metrics"]["shadow_records_total"], 1)
            self.assertEqual(metrics["metrics"]["shadow_would_revise_count"], 1)

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
        self.assertIn("Workflow evidence is ready for production-readiness review", output)

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

    def test_scaffold_agent_event_dry_run_does_not_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, output = self.run_cli(["scaffold-agent-event", "support_reply", "--output-dir", tmp, "--dry-run"])
            report = json.loads(output)

            self.assertEqual(code, 0)
            self.assertTrue(report["dry_run"])
            self.assertEqual(report["event_preview"]["adapter_id"], "support_reply")
            self.assertFalse((pathlib.Path(tmp) / "support_reply.json").exists())

    def test_scaffold_agent_event_creates_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, output = self.run_cli(["scaffold-agent-event", "support_reply", "--output-dir", tmp])

            self.assertEqual(code, 0)
            self.assertIn("support_reply.json", output)
            self.assertTrue((pathlib.Path(tmp) / "support_reply.json").exists())


if __name__ == "__main__":
    unittest.main()
