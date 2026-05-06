import json
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_audit import append_mi_audit_jsonl, mi_audit_record
from eval_pipeline.mi_audit_integrity import (
    MI_AUDIT_INTEGRITY_MANIFEST_VERSION,
    mi_audit_integrity_manifest,
    validate_append_only_audit,
    validate_mi_audit_integrity_manifest,
    verify_mi_audit_integrity,
    write_mi_audit_integrity_manifest,
)
from eval_pipeline.mi_boundary_gate import mi_boundary_gate
from tests.test_handoff_gate import clean_handoff


def audit_record(handoff_id):
    handoff = clean_handoff()
    handoff["handoff_id"] = handoff_id
    handoff["sender"]["type"] = "agent"
    handoff["recipient"]["type"] = "tool"
    return mi_audit_record(mi_boundary_gate(handoff), created_at="2026-05-06T00:00:00Z", workflow_id="wf-1")


class MIAuditIntegrityTests(unittest.TestCase):
    def test_manifest_hashes_audit_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mi_audit.jsonl"
            append_mi_audit_jsonl(path, [audit_record("h1"), audit_record("h2")])
            manifest = mi_audit_integrity_manifest(path, created_at="2026-05-06T00:00:00Z")

        self.assertEqual(manifest["mi_audit_integrity_manifest_version"], MI_AUDIT_INTEGRITY_MANIFEST_VERSION)
        self.assertEqual(manifest["line_count"], 2)
        self.assertEqual(len(manifest["line_hashes"]), 2)
        self.assertTrue(validate_mi_audit_integrity_manifest(manifest)["valid"])

    def test_verify_manifest_detects_tampered_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mi_audit.jsonl"
            append_mi_audit_jsonl(path, [audit_record("h1"), audit_record("h2")])
            manifest = mi_audit_integrity_manifest(path, created_at="2026-05-06T00:00:00Z")
            lines = path.read_text(encoding="utf-8").splitlines()
            tampered = json.loads(lines[0])
            tampered["recommended_action"] = "refuse"
            lines[0] = json.dumps(tampered, sort_keys=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            report = verify_mi_audit_integrity(path, manifest)

        self.assertFalse(report["valid"])
        self.assertTrue(report["tampered"])
        self.assertTrue(any("does not match" in issue["message"] for issue in report["issues"]))

    def test_append_only_validation_accepts_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mi_audit.jsonl"
            append_mi_audit_jsonl(path, [audit_record("h1")])
            previous = mi_audit_integrity_manifest(path, created_at="2026-05-06T00:00:00Z")
            append_mi_audit_jsonl(path, [audit_record("h2")])
            report = validate_append_only_audit(previous, path)

        self.assertTrue(report["valid"], report["issues"])
        self.assertTrue(report["append_only"])
        self.assertEqual(report["appended_line_count"], 1)

    def test_append_only_validation_rejects_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mi_audit.jsonl"
            append_mi_audit_jsonl(path, [audit_record("h1")])
            previous = mi_audit_integrity_manifest(path, created_at="2026-05-06T00:00:00Z")
            record = audit_record("h1")
            record["gate_decision"] = "fail"
            path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
            report = validate_append_only_audit(previous, path)

        self.assertFalse(report["valid"])
        self.assertFalse(report["append_only"])
        self.assertTrue(any("changed a line" in issue["message"] for issue in report["issues"]))

    def test_write_manifest_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "mi_audit.jsonl"
            manifest_path = Path(directory) / "mi_audit.jsonl.sha256.json"
            append_mi_audit_jsonl(audit_path, [audit_record("h1")])
            result = write_mi_audit_integrity_manifest(
                audit_path,
                manifest_path,
                created_at="2026-05-06T00:00:00Z",
            )

        self.assertGreater(result["bytes"], 0)
        self.assertEqual(result["manifest"]["line_count"], 1)


if __name__ == "__main__":
    unittest.main()
