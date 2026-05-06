import pathlib
import unittest

from eval_pipeline import agent_contract, contract_freeze, workflow_contract


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PublicApiFreezeTests(unittest.TestCase):
    def test_primary_public_api_inventory_is_explicit(self):
        inventory = {item["id"]: item for item in contract_freeze.contract_inventory()}

        for contract_id in contract_freeze.PRIMARY_PUBLIC_CONTRACTS:
            self.assertIn(contract_id, inventory)
            self.assertTrue(inventory[contract_id]["public_api"])
            self.assertEqual(inventory[contract_id]["boundary"], "primary_public_api")

        self.assertFalse(inventory["adapter_contract"]["public_api"])
        self.assertNotEqual(inventory["adapter_contract"]["boundary"], "primary_public_api")

    def test_workflow_contract_required_fields_are_frozen(self):
        self.assertEqual(workflow_contract.WORKFLOW_CONTRACT_VERSION, "0.1")

        expected_required = {
            "workflow_request": ["adapter", "request"],
            "workflow_batch_request": ["requests"],
            "workflow_result": ["contract_version", "adapter", "gate_decision", "recommended_action", "output", "audit_summary"],
            "workflow_batch_result": ["contract_version", "summary", "results"],
        }
        catalog = workflow_contract.schema_catalog()
        for schema_name, required in expected_required.items():
            self.assertEqual(catalog[schema_name]["required"], required)

    def test_workflow_contract_public_properties_are_frozen(self):
        expected_properties = {
            "workflow_request": {
                "contract_version",
                "workflow_id",
                "adapter",
                "request",
                "candidate",
                "evidence",
                "constraints",
                "allowed_actions",
                "metadata",
            },
            "workflow_batch_request": {"contract_version", "batch_id", "requests"},
            "workflow_result": {
                "contract_version",
                "workflow_id",
                "adapter",
                "workflow",
                "gate_decision",
                "recommended_action",
                "candidate_gate",
                "aix",
                "candidate_aix",
                "violations",
                "output",
                "audit_summary",
                "raw_result",
            },
            "workflow_batch_result": {"contract_version", "batch_id", "summary", "results"},
        }
        catalog = workflow_contract.schema_catalog()
        for schema_name, properties in expected_properties.items():
            self.assertTrue(properties.issubset(catalog[schema_name]["properties"]))

    def test_agent_contract_required_fields_are_frozen(self):
        self.assertEqual(agent_contract.AGENT_EVENT_VERSION, "0.1")

        self.assertEqual(agent_contract.AGENT_EVENT_SCHEMA["required"], ["user_request"])
        self.assertEqual(
            agent_contract.AGENT_CHECK_RESULT_SCHEMA["required"],
            ["agent_check_version", "adapter_id", "gate_decision", "recommended_action", "safe_response", "audit_summary"],
        )

    def test_agent_contract_public_properties_are_frozen(self):
        expected_event_properties = {
            "event_version",
            "event_id",
            "agent",
            "adapter_id",
            "workflow",
            "user_request",
            "prompt",
            "candidate_action",
            "candidate_answer",
            "draft_response",
            "available_evidence",
            "allowed_actions",
            "metadata",
        }
        expected_result_properties = {
            "agent_check_version",
            "agent",
            "adapter_id",
            "workflow",
            "event_id",
            "gate_decision",
            "recommended_action",
            "candidate_gate",
            "aix",
            "candidate_aix",
            "violations",
            "safe_response",
            "audit_summary",
            "adapter_result",
        }

        self.assertTrue(expected_event_properties.issubset(agent_contract.AGENT_EVENT_SCHEMA["properties"]))
        self.assertTrue(expected_result_properties.issubset(agent_contract.AGENT_CHECK_RESULT_SCHEMA["properties"]))

    def test_public_api_docs_mark_runner_internals_as_implementation_detail(self):
        docs = "\n".join(
            [
                (ROOT / "docs" / "aana-workflow-contract.md").read_text(encoding="utf-8"),
                (ROOT / "docs" / "agent-integration.md").read_text(encoding="utf-8"),
            ]
        )

        for phrase in ("runtime.py", "legacy_runner.py", "verifier modules", "adapter JSON internals", "implementation details"):
            self.assertIn(phrase, docs)

    def test_public_result_schemas_require_common_runtime_surface(self):
        expected_common = {
            "gate_decision",
            "recommended_action",
            "violations",
            "aix",
            "candidate_aix",
            "audit_summary",
        }

        workflow_result = workflow_contract.WORKFLOW_RESULT_SCHEMA
        agent_result = agent_contract.AGENT_CHECK_RESULT_SCHEMA

        self.assertTrue(expected_common.issubset(workflow_result["properties"]))
        self.assertTrue(expected_common.issubset(agent_result["properties"]))
        self.assertIn("output", workflow_result["required"])
        self.assertIn("safe_response", agent_result["required"])
        for field in expected_common:
            if field in {"aix", "candidate_aix", "violations"}:
                continue
            self.assertIn(field, workflow_result["required"])
            self.assertIn(field, agent_result["required"])


if __name__ == "__main__":
    unittest.main()
