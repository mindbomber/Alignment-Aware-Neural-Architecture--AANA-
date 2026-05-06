import json
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.immutable_audit_storage import (
    IMMUTABLE_AUDIT_STORAGE_VERSION,
    LocalImmutableAuditStorage,
    immutable_audit_storage_contract,
    write_immutable_audit_storage_contract,
)
from eval_pipeline.mi_audit import load_mi_audit_jsonl, mi_audit_record
from eval_pipeline.mi_boundary_gate import mi_boundary_gate
from tests.test_handoff_gate import clean_handoff


def audit_record(handoff_id: str):
    handoff = clean_handoff()
    handoff["handoff_id"] = handoff_id
    handoff["sender"]["type"] = "agent"
    handoff["recipient"]["type"] = "tool"
    return mi_audit_record(mi_boundary_gate(handoff), created_at="2026-05-06T00:00:00Z", workflow_id="wf-1")


class ImmutableAuditStorageTests(unittest.TestCase):
    def test_contract_declares_local_stub_and_remote_boundary(self):
        contract = immutable_audit_storage_contract()

        self.assertEqual(contract["immutable_audit_storage_version"], IMMUTABLE_AUDIT_STORAGE_VERSION)
        self.assertEqual(contract["current_mode"], "local_append_only_stub")
        self.assertFalse(contract["remote_storage_enabled"])
        self.assertEqual(contract["production_boundary"]["status"], "not_configured")
        self.assertTrue(contract["production_boundary"]["required_before_live_production"])

    def test_local_storage_appends_records_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "mi_audit.jsonl"
            manifest_path = Path(directory) / "mi_audit.jsonl.sha256.json"
            storage = LocalImmutableAuditStorage(audit_path, manifest_path)

            receipt = storage.append([audit_record("h1"), audit_record("h2")])
            verification = storage.verify()
            records = load_mi_audit_jsonl(audit_path)

        self.assertEqual(receipt["storage_mode"], "local_append_only_stub")
        self.assertEqual(receipt["record_count"], 2)
        self.assertTrue(receipt["append_only"])
        self.assertEqual(receipt["line_count"], 2)
        self.assertTrue(verification["valid"], verification["issues"])
        self.assertEqual(len(records), 2)

    def test_local_storage_preserves_append_only_chain_across_appends(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalImmutableAuditStorage(
                Path(directory) / "mi_audit.jsonl",
                Path(directory) / "mi_audit.jsonl.sha256.json",
            )

            first = storage.append(audit_record("h1"))
            second = storage.append(audit_record("h2"))

        self.assertEqual(first["line_count"], 1)
        self.assertEqual(second["line_count"], 2)
        self.assertTrue(second["append_only"])
        self.assertNotEqual(first["final_chain_sha256"], second["final_chain_sha256"])

    def test_local_storage_rejects_raw_or_invalid_audit_records(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalImmutableAuditStorage(
                Path(directory) / "mi_audit.jsonl",
                Path(directory) / "mi_audit.jsonl.sha256.json",
            )
            record = audit_record("h1")
            record["message"] = {"summary": "raw content"}

            with self.assertRaises(ValueError):
                storage.append(record)

    def test_local_storage_detects_tamper_before_next_append(self):
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "mi_audit.jsonl"
            storage = LocalImmutableAuditStorage(audit_path, Path(directory) / "mi_audit.jsonl.sha256.json")
            storage.append(audit_record("h1"))
            lines = audit_path.read_text(encoding="utf-8").splitlines()
            tampered = json.loads(lines[0])
            tampered["gate_decision"] = "fail"
            audit_path.write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                storage.append(audit_record("h2"))

            verification = storage.verify()

        self.assertFalse(verification["valid"])
        self.assertTrue(verification["issues"])

    def test_write_contract_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "immutable_audit_storage_contract.json"
            result = write_immutable_audit_storage_contract(path)
            loaded = json.loads(path.read_text(encoding="utf-8"))

        self.assertGreater(result["bytes"], 0)
        self.assertEqual(loaded["current_mode"], "local_append_only_stub")


if __name__ == "__main__":
    unittest.main()
