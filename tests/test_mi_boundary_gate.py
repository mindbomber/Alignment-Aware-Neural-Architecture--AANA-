import unittest

from eval_pipeline.mi_boundary_gate import infer_boundary_type, mi_boundary_batch, mi_boundary_gate
from tests.test_handoff_gate import clean_handoff


def boundary_handoff(sender_type, recipient_type, boundary_type=None):
    handoff = clean_handoff()
    handoff["handoff_id"] = f"{sender_type}-to-{recipient_type}-001"
    handoff["sender"] = {"id": f"{sender_type}_sender", "type": sender_type, "trust_tier": "system"}
    handoff["recipient"] = {"id": f"{recipient_type}_recipient", "type": recipient_type, "trust_tier": "system"}
    handoff["metadata"] = dict(handoff.get("metadata", {}))
    if boundary_type:
        handoff["metadata"]["boundary_type"] = boundary_type
    return handoff


class MIBoundaryGateTests(unittest.TestCase):
    def test_infers_requested_boundary_types(self):
        cases = [
            ("agent", "agent", "agent_to_agent"),
            ("agent", "tool", "agent_to_tool"),
            ("tool", "agent", "tool_to_agent"),
            ("plugin", "agent", "plugin_to_agent"),
            ("workflow_step", "workflow_step", "workflow_step_to_workflow_step"),
        ]

        for sender_type, recipient_type, expected in cases:
            with self.subTest(expected=expected):
                handoff = boundary_handoff(sender_type, recipient_type)
                self.assertEqual(infer_boundary_type(handoff), expected)
                result = mi_boundary_gate(handoff)
                self.assertEqual(result["boundary_type"], expected)
                self.assertTrue(result["boundary_supported"])
                self.assertEqual(result["gate_decision"], "pass")
                self.assertEqual(result["recommended_action"], "accept")

    def test_agent_to_connector_counts_as_agent_to_tool_boundary(self):
        result = mi_boundary_gate(boundary_handoff("agent", "connector"))

        self.assertEqual(result["boundary_type"], "agent_to_tool")
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "accept")

    def test_unsupported_boundary_fails_closed(self):
        result = mi_boundary_gate(boundary_handoff("human_review", "plugin"))

        self.assertFalse(result["boundary_supported"])
        self.assertEqual(result["gate_decision"], "fail")
        self.assertEqual(result["recommended_action"], "defer")
        self.assertTrue(any(violation["code"] == "unsupported_endpoint_boundary" for violation in result["violations"]))

    def test_declared_boundary_mismatch_fails_closed(self):
        result = mi_boundary_gate(boundary_handoff("agent", "tool", boundary_type="tool_to_agent"))

        self.assertFalse(result["boundary_supported"])
        self.assertEqual(result["gate_decision"], "fail")
        self.assertEqual(result["recommended_action"], "defer")
        self.assertTrue(any(violation["code"] == "boundary_type_mismatch" for violation in result["violations"]))

    def test_incompatible_contract_version_fails_closed(self):
        handoff = boundary_handoff("agent", "tool")
        handoff["contract_version"] = "9.9"

        result = mi_boundary_gate(handoff)

        self.assertFalse(result["boundary_supported"])
        self.assertFalse(result["mi_contract_compatibility"]["version_compatible"])
        self.assertEqual(result["gate_decision"], "fail")
        self.assertTrue(any(violation["code"] == "incompatible_contract_version" for violation in result["violations"]))

    def test_preserves_handoff_gate_routes(self):
        handoff = boundary_handoff("agent", "tool")
        handoff["evidence"] = []

        result = mi_boundary_gate(handoff)

        self.assertTrue(result["boundary_supported"])
        self.assertEqual(result["boundary_type"], "agent_to_tool")
        self.assertEqual(result["gate_decision"], "block")
        self.assertEqual(result["recommended_action"], "retrieve")

    def test_batch_summarizes_boundary_routes(self):
        batch = mi_boundary_batch(
            [
                boundary_handoff("agent", "agent"),
                boundary_handoff("plugin", "agent"),
                boundary_handoff("human_review", "plugin"),
            ]
        )

        self.assertEqual(batch["summary"]["total"], 3)
        self.assertEqual(batch["summary"]["recommended_actions"]["accept"], 2)
        self.assertEqual(batch["summary"]["recommended_actions"]["defer"], 1)
        self.assertEqual(batch["summary"]["blocked"], 1)


if __name__ == "__main__":
    unittest.main()
