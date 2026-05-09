import subprocess
import unittest
from unittest import mock

from scripts import validate_aana_platform


class ValidateAANAPlatformTests(unittest.TestCase):
    def test_platform_gates_cover_standardization_surfaces(self):
        gates = validate_aana_platform.platform_gates()
        names = [gate.name for gate in gates]

        self.assertEqual(
            names,
            [
                "adapter_layout",
                "canonical_ids",
                "contract_freeze",
                "agent_integrations",
                "hf_dataset_registry",
                "hf_calibration",
                "hf_dataset_proof",
                "privacy_pii_adapter_eval",
                "grounded_qa_adapter_eval",
                "agent_tool_use_control_eval",
                "adapter_generalization",
                "benchmark_fit_lint",
                "benchmark_reporting",
                "cross_domain_adapter_families",
                "production_candidate_evidence_pack",
                "standard_publication",
                "security_hardening",
                "packaging_hardening",
                "versioning_migration",
            ],
        )
        categories = {gate.category for gate in gates}
        self.assertTrue(
            {
                "architecture",
                "contracts",
                "integrations",
                "data",
                "adapters",
                "claims",
                "publication",
                "security",
                "packaging",
            }.issubset(categories)
        )

    def test_platform_gates_can_skip_integrations(self):
        names = [gate.name for gate in validate_aana_platform.platform_gates(include_agent_integrations=False)]

        self.assertNotIn("agent_integrations", names)

    def test_platform_gates_use_require_existing_artifacts_by_default(self):
        commands = [" ".join(gate.command) for gate in validate_aana_platform.platform_gates()]

        self.assertTrue(any("validate_adapter_generalization.py --require-existing-artifacts" in command for command in commands))
        self.assertTrue(any("validate_hf_dataset_proof.py --require-existing-artifacts" in command for command in commands))
        self.assertTrue(any("validate_packaging_hardening.py --require-existing-artifacts" in command for command in commands))

    def test_validate_platform_reports_failure_and_fail_fast(self):
        def fake_run(gate, *, timeout):
            return {
                "name": gate.name,
                "category": gate.category,
                "description": gate.description,
                "command": gate.command,
                "valid": gate.name != "contract_freeze",
                "returncode": 0 if gate.name != "contract_freeze" else 1,
                "latency_ms": 1.0,
                "stdout": "",
                "stderr": "failed",
            }

        with mock.patch.object(validate_aana_platform, "run_gate", side_effect=fake_run):
            report = validate_aana_platform.validate_platform(fail_fast=True)

        self.assertFalse(report["valid"])
        self.assertEqual(report["total"], 3)
        self.assertEqual(report["passed"], 2)
        self.assertEqual(report["checks"][-1]["name"], "contract_freeze")

    def test_main_returns_nonzero_on_failed_gate(self):
        report = {"valid": False, "passed": 0, "total": 1, "checks": []}
        with mock.patch.object(validate_aana_platform, "validate_platform", return_value=report):
            self.assertEqual(validate_aana_platform.main([]), 1)

    def test_run_gate_captures_nonzero_subprocess(self):
        gate = validate_aana_platform.PlatformGate(
            name="demo",
            category="test",
            command=["python", "-c", "raise SystemExit(2)"],
            description="demo",
        )
        completed = subprocess.CompletedProcess(gate.command, 2, stdout="out", stderr="err")
        with mock.patch.object(validate_aana_platform.subprocess, "run", return_value=completed):
            result = validate_aana_platform.run_gate(gate, timeout=10)

        self.assertFalse(result["valid"])
        self.assertEqual(result["returncode"], 2)
        self.assertEqual(result["stdout"], "out")
        self.assertEqual(result["stderr"], "err")


if __name__ == "__main__":
    unittest.main()
