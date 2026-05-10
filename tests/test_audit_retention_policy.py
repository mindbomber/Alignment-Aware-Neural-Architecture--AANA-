import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "examples" / "audit_retention_policy_internal_pilot.json"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit_retention = load_script("validate_audit_retention_policy", ROOT / "scripts" / "validation" / "validate_audit_retention_policy.py")


def _policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


class AuditRetentionPolicyTests(unittest.TestCase):
    def test_policy_validates_append_only_immutable_storage(self):
        report = audit_retention.validate_policy(POLICY_PATH)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["status"], "approved_for_internal_pilot")
        self.assertTrue(report["append_only"])
        self.assertTrue(report["immutable"])
        self.assertEqual(report["retention_days"], 730)
        self.assertTrue(report["storage_sink"].startswith("immutable-audit://"))
        self.assertTrue(report["redaction_proof"]["schema_valid"], report)
        self.assertTrue(report["redaction_proof"]["redacted"], report)
        self.assertGreater(report["redaction_proof"]["record_count"], 0)

    def test_policy_declares_retention_legal_hold_access_and_integrity(self):
        policy = _policy()

        self.assertGreaterEqual(policy["retention"]["minimum_days"], 365)
        self.assertTrue(policy["retention"]["legal_hold"]["supported"])
        self.assertIn("legal hold", policy["retention"]["delete_after_expiration"].lower())
        self.assertTrue(policy["access_control"]["mfa_required"])
        self.assertTrue(policy["access_control"]["least_privilege"])
        self.assertIn("public", policy["access_control"]["denied"])
        self.assertIn("unauthenticated", policy["access_control"]["denied"])
        self.assertEqual(policy["integrity_checks"]["hash_algorithm"], "sha256")
        self.assertTrue(policy["integrity_checks"]["manifest_chain_required"])
        self.assertIn("audit-verify", policy["integrity_checks"]["verification_command"])

    def test_policy_rejects_local_jsonl_as_production_sink(self):
        policy = _policy()
        policy["storage"]["sink_uri"] = "jsonl://C:/ProgramData/AANA/audit/aana-audit.jsonl"

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = pathlib.Path(temp_dir) / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            report = audit_retention.validate_policy(policy_path)

        self.assertFalse(report["valid"])
        self.assertTrue(any("local JSONL" in error for error in report["errors"]), report)

    def test_policy_rejects_missing_legal_hold_and_access_controls(self):
        policy = _policy()
        policy["retention"]["legal_hold"]["supported"] = False
        policy["access_control"]["denied"] = ["public"]
        policy["integrity_checks"]["manifest_chain_required"] = False

        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = pathlib.Path(temp_dir) / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            report = audit_retention.validate_policy(policy_path)

        self.assertFalse(report["valid"])
        joined = "\n".join(report["errors"])
        self.assertIn("legal_hold", joined)
        self.assertIn("unauthenticated", joined)
        self.assertIn("manifest_chain_required", joined)

    def test_redaction_proof_fails_if_raw_support_data_is_stored(self):
        case = json.loads((ROOT / "examples" / "support_workflow_contract_examples.json").read_text(encoding="utf-8"))["cases"][0]
        forbidden = audit_retention._raw_forbidden_terms(case)
        raw_record = {
            "audit_record_version": "0.1",
            "record_type": "workflow_check",
            "created_at": "2026-05-05T12:00:00+00:00",
            "adapter_id": case["workflow_request"]["adapter"],
            "gate_decision": "pass",
            "recommended_action": "revise",
            "violation_codes": [],
            "raw_prompt": case["workflow_request"]["request"],
        }

        from eval_pipeline import agent_api

        report = agent_api.audit_redaction_report([raw_record], forbidden_terms=forbidden)

        self.assertFalse(report["redacted"])
        self.assertGreater(report["errors"], 0)

    def test_deployment_manifest_references_policy_sink(self):
        deployment = json.loads((ROOT / "examples" / "production_deployment_internal_pilot.json").read_text(encoding="utf-8"))

        self.assertEqual(deployment["audit"]["policy_ref"], "examples/audit_retention_policy_internal_pilot.json")
        self.assertEqual(deployment["audit"]["sink"], _policy()["storage"]["sink_uri"])
        self.assertTrue(deployment["audit"]["append_only"])
        self.assertTrue(deployment["audit"]["immutable"])
        self.assertEqual(deployment["audit"]["raw_artifact_store"], "none")


if __name__ == "__main__":
    unittest.main()
