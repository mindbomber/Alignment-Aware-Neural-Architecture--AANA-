import pathlib
import tempfile
import unittest

import aana
from eval_pipeline import enterprise_connector_readiness
from scripts import aana_cli


class EnterpriseConnectorReadinessTests(unittest.TestCase):
    def test_default_plan_covers_enterprise_ops_connectors(self):
        plan = enterprise_connector_readiness.enterprise_connector_readiness_plan()
        validation = enterprise_connector_readiness.validate_enterprise_connector_readiness_plan(plan)

        self.assertTrue(validation["valid"], validation)
        self.assertEqual({item["connector_id"] for item in plan["connectors"]}, set(enterprise_connector_readiness.REQUIRED_CONNECTOR_IDS))
        self.assertEqual(plan["summary"]["live_execution_enabled_count"], 0)
        for connector in plan["connectors"]:
            self.assertFalse(connector["live_execution_enabled"])
            self.assertEqual(connector["default_runtime_route_before_approval"], "defer")
            self.assertFalse(connector["auth_requirements"]["tokens_in_audit_logs"])
            self.assertFalse(connector["redaction_requirements"]["raw_private_content_allowed_in_audit"])
            self.assertTrue(connector["shadow_mode_requirements"]["write_operations_disabled"])

    def test_public_aana_exports_enterprise_connector_readiness(self):
        plan = aana.enterprise_connector_readiness_plan()

        self.assertTrue(aana.validate_enterprise_connector_readiness_plan(plan)["valid"])
        self.assertEqual(set(aana.REQUIRED_CONNECTOR_IDS), set(enterprise_connector_readiness.REQUIRED_CONNECTOR_IDS))

    def test_cli_writes_enterprise_connector_readiness(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = pathlib.Path(temp_dir) / "connectors.json"
            code = aana_cli.main(["enterprise-connectors", "--output", str(output)])

            self.assertEqual(code, 0)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
