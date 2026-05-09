import copy
import unittest
from pathlib import Path

from eval_pipeline import agent_api
from eval_pipeline.security_hardening import validate_security_hardening
from tests.test_audit_observability import sample_record


ROOT = Path(__file__).resolve().parents[1]


class SecurityHardeningTests(unittest.TestCase):
    def test_security_hardening_gate_passes(self):
        report = validate_security_hardening(ROOT)

        self.assertTrue(report["valid"], report["issues"])

    def test_audit_validator_rejects_raw_tokens_passwords_private_ids_and_full_args(self):
        record = sample_record()
        record["audit_metadata"] = {
            "token": "Bearer secret-token-123456789",
            "password": "correct-horse-battery-staple",
            "private_account_id": "acct_123456789abcdef",
            "proposed_arguments": {"to": "customer@example.com", "body": "raw message"},
        }

        report = agent_api.validate_audit_records([record])

        self.assertFalse(report["valid"])
        messages = "\n".join(issue["message"] for issue in report["issues"])
        paths = {issue["path"] for issue in report["issues"]}
        self.assertIn("raw secrets", messages)
        self.assertIn("$[0].audit_metadata.token", paths)
        self.assertIn("$[0].audit_metadata.password", paths)
        self.assertIn("$[0].audit_metadata.private_account_id", paths)
        self.assertIn("$[0].audit_metadata.proposed_arguments", paths)

    def test_security_gate_blocks_ci_without_dependency_audit(self):
        from eval_pipeline import security_hardening

        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8").replace("pip-audit", "pip_audit_removed")
        issues = security_hardening.validate_ci_security(ci)

        self.assertTrue(any("dependency audit" in issue["message"] for issue in issues))

    def test_security_gate_blocks_public_demo_if_side_effects_enabled(self):
        from eval_pipeline.security_hardening import validate_public_demo_safety
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs" / "demo").mkdir(parents=True)
            (root / "docs" / "tool-call-demo").mkdir(parents=True)
            manifest = copy.deepcopy(__import__("json").loads((ROOT / "docs" / "demo" / "scenarios.json").read_text(encoding="utf-8")))
            manifest["real_side_effects"] = True
            (root / "docs" / "demo" / "scenarios.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "docs" / "tool-call-demo" / "app.js").write_text(
                "const SAFE_DEMO_MODE = true;\nconst forbiddenExecutionActions = new Set(['send']);\n",
                encoding="utf-8",
            )

            issues = validate_public_demo_safety(root)

        self.assertTrue(any("real_side_effects" in issue["path"] for issue in issues))


if __name__ == "__main__":
    unittest.main()
