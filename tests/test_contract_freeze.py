import unittest

from eval_pipeline import contract_freeze


class ContractFreezeTests(unittest.TestCase):
    def test_contract_inventory_declares_required_public_surfaces(self):
        inventory = {item["id"]: item for item in contract_freeze.contract_inventory()}

        for contract_id in [
            "adapter_contract",
            "agent_event",
            "agent_check_result",
            "workflow_request",
            "workflow_batch_request",
            "workflow_result",
            "workflow_batch_result",
            "aix",
            "evidence_object",
            "evidence_registry",
            "audit_record",
            "audit_metrics_export",
            "audit_integrity_manifest",
        ]:
            self.assertIn(contract_id, inventory)
            self.assertEqual(inventory[contract_id]["stability"], "frozen")
            self.assertTrue(inventory[contract_id]["version"])
            self.assertTrue(inventory[contract_id]["breaking_change_requires"])

    def test_schema_catalog_contains_contract_freeze_schemas(self):
        report = contract_freeze.validate_schema_catalog()

        self.assertTrue(report["valid"], report)
        self.assertGreaterEqual(report["schema_count"], report["required_schema_count"])

    def test_contract_freeze_report_passes_current_fixtures(self):
        report = contract_freeze.contract_freeze_report()

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["frozen"], report)
        self.assertEqual(report["summary"]["status"], "pass")
        self.assertGreaterEqual(report["summary"]["contracts"], 13)


if __name__ == "__main__":
    unittest.main()
