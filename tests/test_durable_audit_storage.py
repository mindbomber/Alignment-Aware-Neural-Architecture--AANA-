import json
import pathlib
import tempfile
import unittest

import aana
from eval_pipeline import agent_api, durable_audit_storage
from scripts import aana_cli


def sample_record():
    event = agent_api.load_json_file("examples/agent_event_support_reply.json")
    result = agent_api.check_event(event)
    return agent_api.audit_event_check(event, result, created_at="2026-05-05T00:00:00Z")


class DurableAuditStorageTests(unittest.TestCase):
    def test_config_validates_redacted_append_only_defaults(self):
        config = durable_audit_storage.durable_audit_storage_config()
        report = durable_audit_storage.validate_durable_audit_storage_config(config)

        self.assertTrue(report["valid"], report)
        self.assertTrue(config["redacted_records_only"])
        self.assertEqual(config["raw_payload_storage"], "disabled")
        self.assertTrue(config["append_only"])
        self.assertTrue(config["retention"]["production_remote_backend_required_for_go_live"])

    def test_local_durable_storage_appends_and_verifies_runtime_audit_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = pathlib.Path(temp_dir) / "aana-audit.jsonl"
            manifest_path = pathlib.Path(temp_dir) / "aana-audit.jsonl.sha256.json"
            storage = durable_audit_storage.LocalDurableAuditStorage(audit_path, manifest_path)

            first = storage.append(sample_record())
            second = storage.append(sample_record())
            verification = storage.verify()

        self.assertEqual(first["line_count"], 1)
        self.assertEqual(second["line_count"], 2)
        self.assertTrue(second["append_only"])
        self.assertTrue(verification["valid"], verification["issues"])
        self.assertTrue(verification["append_only_prefix_verified"])
        self.assertEqual(verification["record_count"], 2)

    def test_durable_storage_rejects_raw_or_invalid_audit_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = durable_audit_storage.LocalDurableAuditStorage(
                pathlib.Path(temp_dir) / "aana-audit.jsonl",
                pathlib.Path(temp_dir) / "aana-audit.jsonl.sha256.json",
            )
            record = sample_record()
            record["raw_prompt"] = "do not store this"

            with self.assertRaises(ValueError):
                storage.append(record)

    def test_durable_storage_detects_tamper_before_next_append(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = pathlib.Path(temp_dir) / "aana-audit.jsonl"
            storage = durable_audit_storage.LocalDurableAuditStorage(
                audit_path,
                pathlib.Path(temp_dir) / "aana-audit.jsonl.sha256.json",
            )
            storage.append(sample_record())
            row = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
            row["gate_decision"] = "fail"
            audit_path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                storage.append(sample_record())

            verification = storage.verify()

        self.assertFalse(verification["valid"])
        self.assertTrue(verification["issues"])

    def test_cli_imports_and_verifies_existing_audit_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = pathlib.Path(temp_dir) / "source.jsonl"
            durable = pathlib.Path(temp_dir) / "durable.jsonl"
            manifest = pathlib.Path(temp_dir) / "durable.jsonl.sha256.json"
            agent_api.append_audit_record(source, sample_record())

            import_code = aana_cli.main(
                [
                    "durable-audit-storage",
                    "--source-audit-log",
                    str(source),
                    "--audit-path",
                    str(durable),
                    "--manifest-path",
                    str(manifest),
                ]
            )
            verify_code = aana_cli.main(
                [
                    "durable-audit-storage",
                    "--verify",
                    "--audit-path",
                    str(durable),
                    "--manifest-path",
                    str(manifest),
                ]
            )

        self.assertEqual(import_code, 0)
        self.assertEqual(verify_code, 0)

    def test_public_exports_include_durable_audit_storage(self):
        config = aana.durable_audit_storage_config()

        self.assertEqual(aana.DURABLE_AUDIT_STORAGE_VERSION, "0.1")
        self.assertEqual(config["storage_type"], "aana_durable_audit_storage")
        self.assertTrue(aana.validate_durable_audit_storage_config(config)["valid"])


if __name__ == "__main__":
    unittest.main()
