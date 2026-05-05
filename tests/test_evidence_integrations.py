import copy
import datetime
import unittest

import aana
from eval_pipeline import agent_api, evidence, evidence_integrations


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
            "browser_cart_quote",
            "citation_source_registry",
            "local_approval",
            "security",
            "civic_program_rules",
            "civic_vendor_profiles",
            "public_law_policy_sources",
            "redaction_classification_registry",
            "civic_case_history",
            "benefits_claims",
            "civic_source_registry",
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

    def test_stubs_declare_connector_contract_fields(self):
        for stub in evidence_integrations.all_integration_stubs():
            self.assertTrue(stub.required_auth_scopes, stub.integration_id)
            self.assertIsInstance(stub.freshness_slo_hours, int)
            self.assertGreater(stub.freshness_slo_hours, 0)
            self.assertIn("redacted", stub.allowed_redaction_statuses)
            self.assertIn("unauthorized", stub.failure_modes)
            self.assertIn("stale_evidence", stub.failure_modes)
            self.assertIn("unredacted_evidence", stub.failure_modes)
            self.assertIn("missing_source", stub.failure_modes)

    def test_mock_connector_fixtures_cover_core_systems(self):
        fixtures = evidence_integrations.load_mock_connector_fixtures("examples/evidence_mock_connector_fixtures.json")
        connectors = fixtures["connectors"]
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
            "browser_cart_quote",
            "citation_source_registry",
            "local_approval",
            "civic_program_rules",
            "civic_vendor_profiles",
            "public_law_policy_sources",
            "redaction_classification_registry",
            "civic_case_history",
            "benefits_claims",
            "civic_source_registry",
        ]:
            stub = evidence_integrations.find_integration_stub(integration_id)
            self.assertIn(integration_id, connectors)
            records = connectors[integration_id]["records"]
            for source_id in stub.required_source_ids:
                self.assertIn(source_id, records)

    def test_mock_connectors_normalize_evidence_for_core_systems(self):
        fixtures = evidence_integrations.load_mock_connector_fixtures("examples/evidence_mock_connector_fixtures.json")
        registry = agent_api.load_evidence_registry("examples/evidence_registry.json")

        matrix = evidence_integrations.mock_connector_matrix(
            fixtures=fixtures,
            integration_ids=[
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
                "browser_cart_quote",
                "citation_source_registry",
                "local_approval",
            ],
            now="2026-05-05T01:00:00Z",
        )

        self.assertTrue(matrix["valid"], matrix)
        for report in matrix["reports"]:
            stub = evidence_integrations.find_integration_stub(report["integration_id"])
            self.assertEqual(len(report["evidence"]), len(stub.required_source_ids))
            self.assertEqual(set(report["request"]["auth"]["scopes"]), set(stub.required_auth_scopes))
            workflow = {
                "adapter": stub.adapter_ids[0],
                "request": "Check normalized mock evidence.",
                "candidate": "Draft candidate.",
                "evidence": report["evidence"],
            }
            validation = evidence.validate_workflow_evidence(
                workflow,
                registry,
                require_structured=True,
                now=datetime.datetime(2026, 5, 5, 1, 0, tzinfo=datetime.timezone.utc),
            )
            self.assertTrue(validation["valid"], validation)
            for item in report["evidence"]:
                self.assertEqual(item["redaction_status"], "redacted")
                self.assertEqual(item["trust_tier"], "verified")
                self.assertEqual(item["metadata"]["connector_contract_version"], "0.1")
                self.assertTrue(item["metadata"]["normalized"])

    def test_core_connectors_have_hardened_contracts(self):
        for integration_id in evidence_integrations.CORE_CONNECTOR_CONTRACT_IDS:
            stub = evidence_integrations.find_integration_stub(integration_id)
            contract = stub.connector_contract()

            self.assertEqual(contract["integration_id"], integration_id)
            self.assertTrue(contract["auth"]["required_scopes"])
            self.assertTrue(contract["auth"]["requires_tenant_scope"])
            self.assertFalse(contract["auth"]["action_execution_allowed"])
            self.assertTrue(contract["freshness"]["requires_retrieved_at"])
            self.assertIsInstance(contract["freshness"]["freshness_slo_hours"], int)
            self.assertFalse(contract["redaction"]["raw_records_allowed_in_aana"])
            self.assertIn("redacted", contract["redaction"]["allowed_redaction_statuses"])
            self.assertEqual(contract["source_scope"]["unknown_source_behavior"], "fail_closed")
            self.assertIn("unauthorized", contract["failure_routing"])
            self.assertIn("stale_evidence", contract["failure_routing"])
            self.assertIn("unredacted_evidence", contract["failure_routing"])

    def test_fetch_request_enforces_auth_and_source_scope(self):
        fixtures = evidence_integrations.load_mock_connector_fixtures("examples/evidence_mock_connector_fixtures.json")
        stub = evidence_integrations.find_integration_stub("workspace_files")
        request = stub.fetch_request(
            source_ids=["file-metadata", "unknown-file-source"],
            auth=evidence_integrations.EvidenceAuthContext(
                scopes=stub.required_auth_scopes,
                tenant_id="tenant-001",
                principal_id="user-001",
                request_id="req-001",
            ),
            now="2026-05-05T01:00:00Z",
            operation="read_diff_preview",
            adapter_id="file_operation_guardrail",
            subject_ref="workspace://project/path",
        )

        report = evidence_integrations.run_mock_connector(
            "workspace_files",
            fixtures=fixtures,
            request=request,
        )

        self.assertFalse(report["valid"])
        self.assertEqual(report["checks"]["auth_scopes"], "pass")
        self.assertEqual(report["checks"]["source_scope"], "fail")
        self.assertIn("unknown_source", {failure["code"] for failure in report["failures"]})
        self.assertEqual(report["request"]["auth"]["tenant_id"], "tenant-001")

    def test_mock_connector_rejects_missing_auth_scope(self):
        fixtures = evidence_integrations.load_mock_connector_fixtures("examples/evidence_mock_connector_fixtures.json")

        report = evidence_integrations.run_mock_connector(
            "email_send",
            fixtures=fixtures,
            auth_scopes=["email.draft.read"],
            now="2026-05-05T01:00:00Z",
        )

        self.assertFalse(report["valid"])
        self.assertEqual(report["failures"][0]["code"], "unauthorized")

    def test_mock_connector_rejects_unredacted_record(self):
        fixtures = evidence_integrations.load_mock_connector_fixtures("examples/evidence_mock_connector_fixtures.json")
        fixtures = copy.deepcopy(fixtures)
        fixtures["connectors"]["billing"]["records"]["invoice"]["redaction_status"] = "raw"

        report = evidence_integrations.run_mock_connector(
            "billing",
            fixtures=fixtures,
            now="2026-05-05T01:00:00Z",
        )

        self.assertFalse(report["valid"])
        self.assertIn("unredacted_evidence", {failure["code"] for failure in report["failures"]})

    def test_mock_connector_rejects_stale_record(self):
        fixtures = evidence_integrations.load_mock_connector_fixtures("examples/evidence_mock_connector_fixtures.json")
        fixtures = copy.deepcopy(fixtures)
        fixtures["connectors"]["deployment"]["records"]["deployment-manifest"]["retrieved_at"] = "2026-05-01T00:00:00Z"

        report = evidence_integrations.run_mock_connector(
            "deployment",
            fixtures=fixtures,
            now="2026-05-05T01:00:00Z",
        )

        self.assertFalse(report["valid"])
        self.assertIn("stale_evidence", {failure["code"] for failure in report["failures"]})
        self.assertEqual(report["checks"]["freshness"], "fail")

    def test_normalize_evidence_rejects_unknown_source(self):
        with self.assertRaises(evidence_integrations.EvidenceConnectorError):
            evidence_integrations.normalize_evidence_object(
                "crm_support",
                source_id="unknown-source",
                text="Verified summary.",
                retrieved_at="2026-05-05T00:00:00Z",
            )

    def test_sdk_exposes_mock_connector_helpers(self):
        fixtures = aana.load_evidence_mock_fixtures("examples/evidence_mock_connector_fixtures.json")

        report = aana.run_evidence_mock_connector(
            "crm_support",
            fixtures=fixtures,
            now="2026-05-05T01:00:00Z",
        )
        item = aana.normalize_evidence_object(
            "crm_support",
            source_id="crm-record",
            text="CRM summary.",
            retrieved_at="2026-05-05T00:00:00Z",
        )

        self.assertTrue(report["valid"], report)
        self.assertEqual(item["metadata"]["integration_id"], "crm_support")

    def test_sdk_exposes_connector_contract_helpers(self):
        contracts = aana.evidence_connector_contracts()
        auth = aana.EvidenceAuthContext(
            scopes=("calendar.freebusy.read", "calendar.attendees.read", "user_instruction.read"),
            tenant_id="tenant-001",
            principal_id="user-001",
        )
        request = aana.EvidenceFetchRequest(
            integration_id="calendar",
            source_ids=("calendar-freebusy",),
            auth=auth,
            now="2026-05-05T01:00:00Z",
        )

        self.assertIn("workspace_files", aana.CORE_CONNECTOR_CONTRACT_IDS)
        self.assertTrue(any(contract["integration_id"] == "calendar" for contract in contracts))
        self.assertEqual(request.to_dict()["auth"]["principal_id"], "user-001")

    def test_connector_marketplace_exposes_family_contract_shape(self):
        marketplace = evidence_integrations.connector_marketplace()

        self.assertEqual(marketplace["connector_marketplace_version"], "0.1")
        self.assertIn("enterprise", marketplace["filters"]["families"])
        self.assertIn("government_civic", marketplace["filters"]["families"])
        crm = next(item for item in marketplace["connectors"] if item["connector_id"] == "crm_support")
        self.assertIn("crm-record", crm["source_ids"]["required"])
        self.assertIn("crm.account.read", crm["auth_boundary"]["required_scopes"])
        self.assertFalse(crm["auth_boundary"]["action_execution_allowed"])
        self.assertTrue(crm["freshness_slo"]["requires_retrieved_at"])
        self.assertFalse(crm["redaction_behavior"]["raw_records_allowed_in_aana"])
        self.assertIn("unauthorized", crm["failure_modes"])
        self.assertIn("required_fields", crm["evidence_normalization"])
        self.assertTrue(aana.evidence_connector_marketplace()["connector_count"])

    def test_personal_connectors_have_hardened_contracts(self):
        for integration_id in evidence_integrations.PERSONAL_CONNECTOR_CONTRACT_IDS:
            stub = evidence_integrations.find_integration_stub(integration_id)
            contract = stub.connector_contract()

            self.assertEqual(contract["integration_id"], integration_id)
            self.assertFalse(contract["auth"]["action_execution_allowed"])
            self.assertTrue(contract["auth"]["required_scopes"])
            self.assertIn("redacted", contract["redaction"]["allowed_redaction_statuses"])

    def test_personal_mock_connectors_normalize_redacted_evidence(self):
        fixtures = evidence_integrations.load_mock_connector_fixtures("examples/evidence_mock_connector_fixtures.json")

        matrix = evidence_integrations.mock_connector_matrix(
            fixtures=fixtures,
            integration_ids=evidence_integrations.PERSONAL_CONNECTOR_CONTRACT_IDS,
            now="2026-05-05T01:00:00Z",
        )

        self.assertTrue(matrix["valid"], matrix)
        self.assertEqual(matrix["connector_count"], len(evidence_integrations.PERSONAL_CONNECTOR_CONTRACT_IDS))

    def test_civic_connectors_have_hardened_contracts(self):
        for integration_id in evidence_integrations.CIVIC_CONNECTOR_CONTRACT_IDS:
            stub = evidence_integrations.find_integration_stub(integration_id)
            contract = stub.connector_contract()

            self.assertEqual(contract["integration_id"], integration_id)
            self.assertFalse(contract["auth"]["action_execution_allowed"])
            self.assertTrue(contract["auth"]["required_scopes"])
            self.assertIn("redacted", contract["redaction"]["allowed_redaction_statuses"])

    def test_civic_mock_connectors_normalize_redacted_evidence(self):
        fixtures = evidence_integrations.load_mock_connector_fixtures("examples/evidence_mock_connector_fixtures.json")

        matrix = evidence_integrations.mock_connector_matrix(
            fixtures=fixtures,
            integration_ids=evidence_integrations.CIVIC_CONNECTOR_CONTRACT_IDS,
            now="2026-05-05T01:00:00Z",
        )

        self.assertTrue(matrix["valid"], matrix)
        self.assertEqual(matrix["connector_count"], len(evidence_integrations.CIVIC_CONNECTOR_CONTRACT_IDS))
        self.assertIn("civic_program_rules", aana.CIVIC_CONNECTOR_CONTRACT_IDS)


if __name__ == "__main__":
    unittest.main()
