import unittest

from eval_pipeline.mi_contract_registry import (
    ACTIVE_MI_CONTRACT_VERSION,
    CORE_REQUIRED_CONSTRAINT_LAYERS,
    CORE_REQUIRED_FIELDS,
    CORE_REQUIRED_VERIFIER_LAYERS,
    MI_CONTRACT_REGISTRY_VERSION,
    check_contract_version_compatibility,
    contract_shape_for_boundary,
    infer_registered_boundary_type,
    mi_contract_registry,
    supported_boundaries,
    validate_mi_contract_compatibility,
)
from tests.test_mi_boundary_gate import boundary_handoff


class MIContractRegistryTests(unittest.TestCase):
    def test_registry_covers_required_boundary_types(self):
        registry = mi_contract_registry()
        boundaries = registry["boundaries"]

        self.assertEqual(registry["mi_contract_registry_version"], MI_CONTRACT_REGISTRY_VERSION)
        self.assertEqual(registry["active_contract_version"], ACTIVE_MI_CONTRACT_VERSION)
        self.assertEqual(
            set(boundaries),
            {
                "agent_to_agent",
                "agent_to_tool",
                "tool_to_agent",
                "plugin_to_agent",
                "workflow_step_to_workflow_step",
            },
        )

    def test_each_boundary_declares_required_shape(self):
        for boundary_type, (_, _) in supported_boundaries().items():
            with self.subTest(boundary_type=boundary_type):
                shape = contract_shape_for_boundary(boundary_type)
                self.assertIsNotNone(shape)
                self.assertEqual(set(CORE_REQUIRED_FIELDS), set(shape["required_fields"]))
                self.assertEqual(set(CORE_REQUIRED_CONSTRAINT_LAYERS), set(shape["required_constraint_layers"]))
                self.assertEqual(set(CORE_REQUIRED_VERIFIER_LAYERS), set(shape["required_verifier_layers"]))
                self.assertTrue(shape["evidence_required"])
                self.assertIn("0.1", shape["compatible_contract_versions"])

    def test_infers_registered_boundary_types(self):
        cases = [
            ("agent", "agent", "agent_to_agent"),
            ("agent", "tool", "agent_to_tool"),
            ("tool", "agent", "tool_to_agent"),
            ("plugin", "agent", "plugin_to_agent"),
            ("workflow_step", "workflow_step", "workflow_step_to_workflow_step"),
        ]

        for sender_type, recipient_type, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(infer_registered_boundary_type(boundary_handoff(sender_type, recipient_type)), expected)

    def test_validates_compatible_contract(self):
        report = validate_mi_contract_compatibility(boundary_handoff("agent", "tool"))

        self.assertTrue(report["compatible"])
        self.assertTrue(report["version_compatible"])
        self.assertEqual(report["boundary_type"], "agent_to_tool")
        self.assertFalse(report["violations"])

    def test_rejects_incompatible_contract_version(self):
        handoff = boundary_handoff("agent", "tool")
        handoff["contract_version"] = "9.9"

        report = validate_mi_contract_compatibility(handoff)
        version_report = check_contract_version_compatibility("9.9", "agent_to_tool")

        self.assertFalse(report["compatible"])
        self.assertFalse(report["version_compatible"])
        self.assertFalse(version_report["compatible"])
        self.assertTrue(any(violation["code"] == "incompatible_contract_version" for violation in report["violations"]))

    def test_rejects_missing_boundary_required_field(self):
        handoff = boundary_handoff("agent", "tool")
        handoff.pop("message_schema")

        report = validate_mi_contract_compatibility(handoff)

        self.assertFalse(report["compatible"])
        self.assertIn("message_schema", report["missing_fields"])
        self.assertTrue(any(violation["code"] == "missing_registry_required_field" for violation in report["violations"]))

    def test_rejects_declared_boundary_mismatch(self):
        handoff = boundary_handoff("agent", "tool", boundary_type="tool_to_agent")

        report = validate_mi_contract_compatibility(handoff)

        self.assertFalse(report["compatible"])
        self.assertEqual(report["boundary_type"], "tool_to_agent")
        self.assertTrue(any(violation["code"] == "boundary_type_mismatch" for violation in report["violations"]))


if __name__ == "__main__":
    unittest.main()
