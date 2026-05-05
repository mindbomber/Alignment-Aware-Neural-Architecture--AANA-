import datetime
import unittest

from eval_pipeline import evidence


class EvidenceRegistryTests(unittest.TestCase):
    def registry(self):
        return {
            "registry_version": "0.1",
            "sources": [
                {
                    "source_id": "source-a",
                    "owner": "AANA Maintainers",
                    "enabled": True,
                    "allowed_trust_tiers": ["verified"],
                    "allowed_redaction_statuses": ["public", "redacted"],
                    "max_age_hours": 24,
                }
            ],
        }

    def workflow(self):
        return {
            "adapter": "research_summary",
            "request": "Summarize Source A.",
            "evidence": [
                {
                    "source_id": "source-a",
                    "retrieved_at": "2026-05-05T00:00:00Z",
                    "trust_tier": "verified",
                    "redaction_status": "public",
                    "text": "Source A: verified.",
                }
            ],
        }

    def test_validate_registry_accepts_valid_registry(self):
        report = evidence.validate_registry(self.registry())

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["production_ready"], report)

    def test_validate_workflow_evidence_accepts_authorized_source(self):
        report = evidence.validate_workflow_evidence(
            self.workflow(),
            self.registry(),
            require_structured=True,
            now=datetime.datetime(2026, 5, 5, 1, tzinfo=datetime.timezone.utc),
        )

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["production_ready"], report)
        self.assertEqual(report["structured_evidence"], 1)

    def test_validate_workflow_evidence_rejects_unapproved_source(self):
        workflow = self.workflow()
        workflow["evidence"][0]["source_id"] = "unknown-source"

        report = evidence.validate_workflow_evidence(workflow, self.registry(), require_structured=True)

        self.assertFalse(report["valid"])
        self.assertEqual(report["issues"][0]["path"], "$.evidence[0].source_id")

    def test_validate_workflow_evidence_rejects_stale_evidence(self):
        report = evidence.validate_workflow_evidence(
            self.workflow(),
            self.registry(),
            require_structured=True,
            now=datetime.datetime(2026, 5, 7, tzinfo=datetime.timezone.utc),
        )

        self.assertFalse(report["valid"])
        self.assertTrue(any("stale" in issue["message"] for issue in report["issues"]))

    def test_validate_workflow_evidence_warns_on_unstructured_evidence(self):
        workflow = {"evidence": ["Source A: verified."]}

        report = evidence.validate_workflow_evidence(workflow, self.registry())

        self.assertTrue(report["valid"], report)
        self.assertFalse(report["production_ready"])
        self.assertEqual(report["warnings"], 1)


if __name__ == "__main__":
    unittest.main()
