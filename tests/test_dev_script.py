import contextlib
import importlib.util
import io
import pathlib
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dev = load_script("dev", ROOT / "scripts" / "dev.py")


class DevScriptTests(unittest.TestCase):
    def test_release_gates_name_hardened_core_categories(self):
        gates = dev.release_gates(
            audit_log_path="eval_outputs/audit/test/aana-audit.jsonl",
            metrics_output="eval_outputs/audit/test/aana-metrics.json",
        )
        names = [gate.name for gate in gates]
        categories = {gate.category for gate in gates}

        self.assertEqual(
            names,
            [
                "compile",
                "unit_tests",
                "contract_freeze",
                "versioning_migration",
                "verifier_boundaries",
                "golden_outputs",
                "adapter_baseline_comparison",
                "adapter_heldout_validation",
                "benchmark_fit_lint",
                "benchmark_reporting",
                "adapter_generalization",
                "hf_dataset_registry",
                "hf_calibration",
                "hf_dataset_proof",
                "privacy_pii_adapter",
                "grounded_qa_adapter",
                "agent_tool_use_control",
                "cross_domain_adapter_families",
                "production_candidate_evidence_pack",
                "gallery_metadata",
                "support_adapter_expansion",
                "adapter_examples",
                "audit_redaction",
                "audit_validate",
                "aix_tuning",
                "production_profiles",
                "security_privacy_review",
                "secrets_scan",
                "security_hardening",
                "packaging_hardening",
                "audit_retention_policy",
                "incident_response_plan",
                "support_domain_signoff",
                "production_readiness_boundary",
                "support_sla_failure_policy",
                "first_deployable_baseline",
                "production_readiness_review",
                "internal_pilot_plan",
                "docs_link_validation",
            ],
        )
        self.assertTrue({"api", "adapter", "catalog", "audit", "data", "docs", "production-profile", "publication"}.issubset(categories))
        production_command = next(gate.command for gate in gates if gate.name == "production_profiles")
        self.assertIn("--audit-log", production_command)
        self.assertIn("eval_outputs/audit/test/aana-audit.jsonl", production_command)
        self.assertIn("--metrics-output", production_command)
        self.assertIn("eval_outputs/audit/test/aana-metrics.json", production_command)

    def test_release_gate_wraps_failures_with_category_annotation(self):
        gate = dev.ReleaseGate(
            name="contract_freeze",
            category="api",
            command=[dev.PYTHON, "-c", "raise SystemExit(1)"],
            description="fail for test",
        )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with mock.patch.object(dev, "run", side_effect=dev.subprocess.CalledProcessError(1, gate.command)):
                with self.assertRaises(dev.subprocess.CalledProcessError):
                    dev.run_gate(gate)

        self.assertIn("AANA release gate [api] contract_freeze", output.getvalue())
        self.assertIn("::error title=AANA api gate failed::contract_freeze failed", output.getvalue())

    def test_release_gate_runs_all_hardened_core_gates(self):
        commands = []

        def capture(gate):
            commands.append(gate)

        with mock.patch.object(dev, "run_gate", side_effect=capture):
            dev.release_gate(
                audit_log="eval_outputs/audit/test/aana-audit.jsonl",
                metrics_output="eval_outputs/audit/test/aana-metrics.json",
            )

        self.assertEqual(
            [gate.name for gate in commands],
            [
                "compile",
                "unit_tests",
                "contract_freeze",
                "versioning_migration",
                "verifier_boundaries",
                "golden_outputs",
                "adapter_baseline_comparison",
                "adapter_heldout_validation",
                "benchmark_fit_lint",
                "benchmark_reporting",
                "adapter_generalization",
                "hf_dataset_registry",
                "hf_calibration",
                "hf_dataset_proof",
                "privacy_pii_adapter",
                "grounded_qa_adapter",
                "agent_tool_use_control",
                "cross_domain_adapter_families",
                "production_candidate_evidence_pack",
                "gallery_metadata",
                "support_adapter_expansion",
                "adapter_examples",
                "audit_redaction",
                "audit_validate",
                "aix_tuning",
                "production_profiles",
                "security_privacy_review",
                "secrets_scan",
                "security_hardening",
                "packaging_hardening",
                "audit_retention_policy",
                "incident_response_plan",
                "support_domain_signoff",
                "production_readiness_boundary",
                "support_sla_failure_policy",
                "first_deployable_baseline",
                "production_readiness_review",
                "internal_pilot_plan",
                "docs_link_validation",
            ],
        )

    def test_ci_workflow_uses_hardened_release_gate_and_artifact_profile(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("python scripts/dev.py release-gate", workflow)
        self.assertIn("--audit-log eval_outputs/audit/ci/aana-ci-audit.jsonl", workflow)
        self.assertIn("--metrics-output eval_outputs/audit/ci/aana-ci-metrics.json", workflow)
        self.assertNotIn("python scripts/dev.py production-profiles", workflow)
        self.assertIn("aana-production-profile-audit-artifacts", workflow)

    def test_production_profiles_runs_internal_pilot_profile_guard(self):
        commands = []

        def capture(command):
            commands.append(command)

        with mock.patch.object(dev, "run", side_effect=capture):
            dev.production_profiles()

        joined = [" ".join(str(part) for part in command) for command in commands]
        self.assertTrue(any("validate-gallery --run-examples" in command for command in joined))
        self.assertTrue(any("scripts/validate_support_adapter_expansion.py" in command for command in joined))
        self.assertTrue(any("pilot-certify" in command for command in joined))
        self.assertTrue(any("contract-freeze --evidence-registry examples/evidence_registry.json" in command for command in joined))
        self.assertTrue(any("scripts/validate_versioning_migration.py" in command for command in joined))
        self.assertTrue(any("aix-tuning" in command for command in joined))
        self.assertTrue(any("validate-deployment --deployment-manifest examples/production_deployment_internal_pilot.json" in command for command in joined))
        self.assertTrue(any("scripts/validate_internal_pilot_plan.py" in command for command in joined))
        self.assertTrue(any("scripts/validate_audit_retention_policy.py" in command for command in joined))
        self.assertTrue(any("scripts/validate_support_domain_signoff.py" in command for command in joined))
        self.assertTrue(any("scripts/validate_production_readiness_boundary.py" in command for command in joined))
        self.assertTrue(any("scripts/validate_support_sla_failure_policy.py" in command for command in joined))
        self.assertTrue(any("scripts/validate_first_deployable_baseline.py" in command for command in joined))
        self.assertTrue(
            any(
                "scripts/validate_first_deployable_baseline.py --baseline examples/first_deployable_support_baseline.internal_pilot.json --require-reached"
                in command
                for command in joined
            )
        )
        self.assertTrue(any("scripts/validate_production_readiness_review.py" in command for command in joined))
        self.assertTrue(any("scripts/validate_security_privacy_review.py" in command for command in joined))
        self.assertTrue(any("scripts/validate_secrets_scan.py" in command for command in joined))
        self.assertTrue(any("scripts/validate_incident_response_plan.py" in command for command in joined))
        self.assertTrue(any("validate-governance --governance-policy examples/human_governance_policy_internal_pilot.json" in command for command in joined))
        self.assertTrue(any("validate-observability --observability-policy examples/observability_policy_internal_pilot.json" in command for command in joined))
        self.assertTrue(any("validate-evidence-registry --evidence-registry examples/evidence_registry.json" in command for command in joined))
        self.assertTrue(any("evidence-integrations --evidence-registry examples/evidence_registry.json --mock-fixtures examples/evidence_mock_connector_fixtures.json" in command for command in joined))
        self.assertTrue(any("agent-check --event examples/agent_event_support_reply.json" in command for command in joined))
        self.assertTrue(any("agent-check --event examples/agent_event_support_reply.json" in command and "--shadow-mode" in command for command in joined))
        self.assertTrue(any("audit-validate --audit-log" in command for command in joined))
        self.assertTrue(any("audit-metrics --audit-log" in command for command in joined))
        self.assertTrue(any("audit-drift --audit-log" in command for command in joined))
        self.assertTrue(any("audit-manifest --audit-log" in command for command in joined))
        self.assertTrue(any("audit-reviewer-report --audit-log" in command for command in joined))
        self.assertTrue(any("release-check --skip-local-check" in command for command in joined))
        self.assertTrue(any("--audit-log" in command for command in joined))

    def test_production_profiles_accepts_ci_artifact_paths(self):
        commands = []
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "ci" / "aana-ci-audit.jsonl"
            metrics_output = pathlib.Path(temp_dir) / "ci" / "aana-ci-metrics.json"

            def capture(command):
                commands.append(command)

            with mock.patch.object(dev, "run", side_effect=capture):
                dev.production_profiles(audit_log=audit_log, metrics_output=metrics_output)

            metrics_commands = [command for command in commands if "audit-metrics" in command]
            drift_commands = [command for command in commands if "audit-drift" in command]
            reviewer_commands = [command for command in commands if "audit-reviewer-report" in command]
            release_commands = [command for command in commands if "release-check" in command]

            self.assertEqual(len(metrics_commands), 1)
            self.assertEqual(len(drift_commands), 1)
            self.assertEqual(len(reviewer_commands), 1)
            self.assertEqual(len(release_commands), 1)
            self.assertIn(str(audit_log), metrics_commands[0])
            self.assertIn(str(metrics_output), metrics_commands[0])
            self.assertIn(str(audit_log), drift_commands[0])
            self.assertIn(str(audit_log), reviewer_commands[0])
            self.assertIn(str(metrics_output), reviewer_commands[0])
            self.assertIn(str(audit_log), release_commands[0])
            self.assertEqual(audit_log.read_text(encoding="utf-8"), "")

    def test_pilot_bundle_runs_e2e_bundle_script(self):
        commands = []

        def capture(command):
            commands.append(command)

        with mock.patch.object(dev, "run", side_effect=capture):
            dev.pilot_bundle()

        joined = [" ".join(str(part) for part in command) for command in commands]
        self.assertTrue(any("scripts/run_e2e_pilot_bundle.py" in command for command in joined))

    def test_contract_freeze_runs_contract_freeze_command(self):
        commands = []

        def capture(command):
            commands.append(command)

        with mock.patch.object(dev, "run", side_effect=capture):
            dev.contract_freeze()

        joined = [" ".join(str(part) for part in command) for command in commands]
        self.assertTrue(any("scripts/aana_cli.py contract-freeze" in command for command in joined))

    def test_pilot_certify_runs_certification_command(self):
        commands = []

        def capture(command):
            commands.append(command)

        with mock.patch.object(dev, "run", side_effect=capture):
            dev.pilot_certify()

        joined = [" ".join(str(part) for part in command) for command in commands]
        self.assertTrue(any("scripts/aana_cli.py pilot-certify" in command for command in joined))

    def test_pilot_eval_runs_evaluation_kit_script(self):
        commands = []

        def capture(command):
            commands.append(command)

        with mock.patch.object(dev, "run", side_effect=capture):
            dev.pilot_eval()

        joined = [" ".join(str(part) for part in command) for command in commands]
        self.assertTrue(any("scripts/run_pilot_evaluation_kit.py" in command for command in joined))

    def test_starter_kits_runs_starter_pilot_kit_script(self):
        commands = []

        def capture(command):
            commands.append(command)

        with mock.patch.object(dev, "run", side_effect=capture):
            dev.starter_kits()

        joined = [" ".join(str(part) for part in command) for command in commands]
        self.assertTrue(any("scripts/run_starter_pilot_kit.py --kit all" in command for command in joined))

    def test_github_guardrails_runs_github_action_guardrail_script(self):
        commands = []

        def capture(command):
            commands.append(command)

        with mock.patch.object(dev, "run", side_effect=capture):
            dev.github_guardrails()

        joined = [" ".join(str(part) for part in command) for command in commands]
        self.assertTrue(any("scripts/run_github_action_guardrails.py --force --fail-on never" in command for command in joined))


if __name__ == "__main__":
    unittest.main()
