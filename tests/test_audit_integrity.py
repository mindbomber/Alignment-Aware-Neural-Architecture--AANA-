import pathlib
import tempfile
import unittest

from eval_pipeline import agent_api


class AuditIntegrityTests(unittest.TestCase):
    def test_integrity_manifest_verifies_current_audit_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            manifest_path = pathlib.Path(temp_dir) / "manifests" / "audit-integrity.json"
            record = {
                "audit_record_version": "0.1",
                "record_type": "agent_check",
                "created_at": "2026-05-05T00:00:00+00:00",
                "gate_decision": "pass",
                "recommended_action": "revise",
            }
            agent_api.append_audit_record(audit_log, record)

            manifest = agent_api.create_audit_integrity_manifest(audit_log, manifest_path=manifest_path)
            report = agent_api.verify_audit_integrity_manifest(manifest_path)

            self.assertTrue(manifest_path.exists())
            self.assertEqual(manifest["record_count"], 1)
            self.assertTrue(report["valid"], report)
            self.assertEqual(report["record_count"], 1)

    def test_integrity_manifest_detects_audit_log_tampering(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            manifest_path = pathlib.Path(temp_dir) / "audit-integrity.json"
            agent_api.append_audit_record(
                audit_log,
                {
                    "audit_record_version": "0.1",
                    "record_type": "agent_check",
                    "created_at": "2026-05-05T00:00:00+00:00",
                    "gate_decision": "pass",
                },
            )
            agent_api.create_audit_integrity_manifest(audit_log, manifest_path=manifest_path)
            audit_log.write_text(audit_log.read_text(encoding="utf-8") + "\n", encoding="utf-8")

            report = agent_api.verify_audit_integrity_manifest(manifest_path)

            self.assertFalse(report["valid"])
            paths = {issue["path"] for issue in report["issues"]}
            self.assertIn("$.audit_log_sha256", paths)
            self.assertIn("$.audit_log_size_bytes", paths)

    def test_integrity_manifest_chains_previous_manifest_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            first_manifest = pathlib.Path(temp_dir) / "manifest-1.json"
            second_manifest = pathlib.Path(temp_dir) / "manifest-2.json"
            agent_api.append_audit_record(audit_log, {"record_type": "agent_check", "gate_decision": "pass"})
            agent_api.create_audit_integrity_manifest(audit_log, manifest_path=first_manifest)

            manifest = agent_api.create_audit_integrity_manifest(
                audit_log,
                manifest_path=second_manifest,
                previous_manifest_path=first_manifest,
            )
            report = agent_api.verify_audit_integrity_manifest(second_manifest)

            self.assertIn("previous_manifest_sha256", manifest)
            self.assertTrue(report["valid"], report)


if __name__ == "__main__":
    unittest.main()
