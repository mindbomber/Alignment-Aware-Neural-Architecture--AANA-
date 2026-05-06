import json
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_audit import (
    append_mi_audit_jsonl,
    load_mi_audit_jsonl,
    mi_audit_record,
    mi_audit_records,
    validate_mi_audit_record,
    validate_mi_audit_records,
)
from eval_pipeline.mi_boundary_gate import mi_boundary_batch, mi_boundary_gate
from tests.test_handoff_gate import clean_handoff


class MIAuditTests(unittest.TestCase):
    def test_mi_audit_record_preserves_decision_metadata_without_raw_content(self):
        handoff = clean_handoff()
        handoff["message"]["summary"] = "PRIVATE raw summary that must not be logged."
        handoff["message"]["claims"] = ["PRIVATE claim that must not be logged."]
        handoff["evidence"][0]["text"] = "PRIVATE evidence text that must not be logged."
        handoff["sender"]["type"] = "agent"
        handoff["recipient"]["type"] = "tool"
        result = mi_boundary_gate(handoff)

        record = mi_audit_record(result, created_at="2026-05-06T00:00:00Z", workflow_id="wf-1")
        encoded = json.dumps(record, sort_keys=True)

        self.assertEqual(record["record_type"], "mi_handoff_decision")
        self.assertEqual(record["sender"]["id"], "research_agent")
        self.assertEqual(record["recipient"]["id"], "publication_checker")
        self.assertEqual(record["gate_decision"], result["gate_decision"])
        self.assertIn("score", record["aix"])
        self.assertIn("message", record["fingerprints"])
        self.assertNotIn("PRIVATE raw summary", encoded)
        self.assertNotIn("PRIVATE claim", encoded)
        self.assertNotIn("PRIVATE evidence text", encoded)
        self.assertTrue(validate_mi_audit_record(record)["valid"])

    def test_mi_audit_records_from_batch_match_handoffs(self):
        h1 = clean_handoff()
        h1["handoff_id"] = "h1"
        h1["sender"]["type"] = "agent"
        h1["recipient"]["type"] = "tool"
        h2 = clean_handoff()
        h2["handoff_id"] = "h2"
        h2["sender"]["type"] = "tool"
        h2["recipient"]["type"] = "agent"

        batch = mi_boundary_batch([h1, h2])

        self.assertEqual(batch["summary"]["mi_audit_record_count"], 2)
        self.assertEqual(len(batch["mi_audit_records"]), 2)
        self.assertEqual([record["handoff_id"] for record in batch["mi_audit_records"]], ["h1", "h2"])
        self.assertTrue(validate_mi_audit_records(batch["mi_audit_records"])["valid"])

    def test_append_and_load_mi_audit_jsonl(self):
        result = mi_boundary_gate(clean_handoff())
        records = mi_audit_records([result], created_at="2026-05-06T00:00:00Z")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mi_audit.jsonl"
            append_mi_audit_jsonl(path, records)
            loaded = load_mi_audit_jsonl(path)
            raw_text = path.read_text(encoding="utf-8")

        self.assertEqual(loaded, records)
        self.assertEqual(len(raw_text.strip().splitlines()), 1)
        self.assertNotIn("Candidate summary only claims", raw_text)
        self.assertNotIn("Source A supports the narrow claim", raw_text)

    def test_validator_rejects_raw_content_fields(self):
        record = mi_audit_record(mi_boundary_gate(clean_handoff()))
        record["message"] = {"summary": "raw content"}

        report = validate_mi_audit_record(record)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "$.message" for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
