import datetime
import unittest

from eval_pipeline.evidence import evidence_object, validate_evidence_object, validate_evidence_objects


class EvidenceObjectTests(unittest.TestCase):
    def valid_item(self):
        return evidence_object(
            source_id="source-a",
            trust_tier="verified",
            retrieved_at="2026-05-05T00:00:00Z",
            redaction_status="redacted",
            text="Source A supports the claim.",
            retrieval_url="aana://evidence/source-a",
            supports=["narrow claim"],
        )

    def test_evidence_object_builder_outputs_required_metadata(self):
        item = self.valid_item()

        self.assertEqual(item["evidence_version"], "0.1")
        self.assertEqual(item["source_id"], "source-a")
        self.assertEqual(item["trust_tier"], "verified")
        self.assertEqual(item["redaction_status"], "redacted")
        self.assertEqual(item["retrieval_url"], "aana://evidence/source-a")

    def test_validate_evidence_object_accepts_valid_item(self):
        report = validate_evidence_object(
            self.valid_item(),
            now=datetime.datetime(2026, 5, 5, 1, tzinfo=datetime.timezone.utc),
            max_age_hours=24,
        )

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["production_ready"], report)

    def test_validate_evidence_object_requires_citation_or_retrieval_link(self):
        item = self.valid_item()
        item.pop("retrieval_url")

        report = validate_evidence_object(item)

        self.assertFalse(report["valid"])
        self.assertTrue(any("citation_url or retrieval_url" in issue["message"] for issue in report["issues"]))

    def test_validate_evidence_object_rejects_unredacted(self):
        item = self.valid_item()
        item["redaction_status"] = "unredacted"

        report = validate_evidence_object(item)

        self.assertFalse(report["valid"])
        self.assertTrue(any("must not be unredacted" in issue["message"] for issue in report["issues"]))

    def test_validate_evidence_object_rejects_stale_item(self):
        report = validate_evidence_object(
            self.valid_item(),
            now=datetime.datetime(2026, 5, 7, tzinfo=datetime.timezone.utc),
            max_age_hours=24,
        )

        self.assertFalse(report["valid"])
        self.assertTrue(any("stale" in issue["message"] for issue in report["issues"]))

    def test_validate_evidence_objects_requires_non_empty_array(self):
        report = validate_evidence_objects([])

        self.assertFalse(report["valid"])
        self.assertEqual(report["checked_evidence"], 0)


if __name__ == "__main__":
    unittest.main()
