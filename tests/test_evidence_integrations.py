import unittest

import aana
from eval_pipeline import agent_api, evidence_integrations


class EvidenceIntegrationTests(unittest.TestCase):
    def test_stubs_cover_core_production_systems(self):
        stubs = {stub.integration_id: stub for stub in evidence_integrations.all_integration_stubs()}

        for integration_id in [
            "crm_support",
            "ticketing",
            "email_send",
            "calendar",
            "iam",
            "ci",
            "deployment",
            "billing",
            "data_export",
            "workspace_files",
            "security",
        ]:
            self.assertIn(integration_id, stubs)
            self.assertTrue(stubs[integration_id].required_source_ids)
            self.assertTrue(stubs[integration_id].adapter_ids)

    def test_evidence_template_uses_structured_contract_shape(self):
        stub = evidence_integrations.find_integration_stub("crm_support")

        item = stub.evidence_template(source_id="crm-record")

        self.assertEqual(item["source_id"], "crm-record")
        self.assertEqual(item["trust_tier"], "verified")
        self.assertEqual(item["redaction_status"], "redacted")
        self.assertIn("retrieved_at", item)
        self.assertIn("text", item)
        self.assertEqual(item["metadata"]["integration_id"], "crm_support")

    def test_stub_fetch_requires_real_connector_implementation(self):
        stub = evidence_integrations.find_integration_stub("email_send")

        with self.assertRaises(NotImplementedError):
            stub.fetch_evidence()

    def test_checked_in_registry_covers_required_integration_sources(self):
        registry = agent_api.load_evidence_registry("examples/evidence_registry.json")

        report = evidence_integrations.integration_coverage_report(registry=registry)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["missing_source_id_count"], 0)
        self.assertGreaterEqual(report["integration_count"], 9)

    def test_missing_registry_source_fails_coverage(self):
        registry = agent_api.load_evidence_registry("examples/evidence_registry.json")
        registry["sources"] = [
            source for source in registry["sources"] if source["source_id"] != "crm-record"
        ]

        report = evidence_integrations.integration_coverage_report(registry=registry)

        self.assertFalse(report["valid"])
        self.assertGreater(report["missing_source_id_count"], 0)
        crm = next(item for item in report["integrations"] if item["integration_id"] == "crm_support")
        self.assertIn("crm-record", crm["missing_source_ids"])

    def test_sdk_exposes_integration_report(self):
        registry = aana.load_evidence_registry("examples/evidence_registry.json")

        report = aana.evidence_integration_coverage(registry)

        self.assertTrue(report["valid"], report)
        self.assertTrue(any(item["integration_id"] == "deployment" for item in report["integrations"]))


if __name__ == "__main__":
    unittest.main()
