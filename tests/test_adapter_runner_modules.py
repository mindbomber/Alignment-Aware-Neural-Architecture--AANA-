import unittest

from eval_pipeline.adapter_runner import constraints, registry, repair, results, verifiers


class AdapterRunnerModuleTests(unittest.TestCase):
    def test_registry_summarizes_adapter_metadata(self):
        adapter = {
            "adapter_name": "demo_adapter",
            "version": "0.1.0",
            "domain": {"name": "Demo"},
        }

        self.assertEqual(
            registry.adapter_summary(adapter),
            {"name": "demo_adapter", "version": "0.1.0", "domain": "Demo"},
        )

    def test_repair_policy_maps_gate_and_action(self):
        self.assertEqual(repair.gate_from_report({"violations": []}), "pass")
        self.assertEqual(repair.gate_from_report({"violations": [{"code": "x"}]}), "block")
        self.assertEqual(
            repair.action_from_answer_and_report("Please provide the destination.", {"violations": []}),
            "ask",
        )
        self.assertEqual(
            repair.action_from_answer_and_report("answer", {"violations": [{"code": "x"}]}),
            "revise",
        )

    def test_constraint_results_use_mapping_specs(self):
        adapter = {
            "constraints": [
                {
                    "id": "recipient_identity_verified",
                    "layer": "evidence",
                    "hard": True,
                    "description": "Verify recipient.",
                }
            ]
        }
        report = {"violations": [{"code": "wrong_or_unverified_recipient"}]}

        output = constraints.constraint_results(
            adapter,
            report,
            mapping_specs=(
                (
                    "recipient_identity_verified",
                    {"wrong_or_unverified_recipient": ["recipient_identity_verified"]},
                ),
            ),
        )

        self.assertEqual(output[0]["status"], "fail")
        self.assertEqual(output[0]["violations"], report["violations"])

    def test_unsupported_result_uses_unknown_constraint_status(self):
        adapter = {
            "adapter_name": "demo_adapter",
            "version": "0.1.0",
            "domain": {"name": "Demo"},
            "constraints": [{"id": "c1", "hard": True}],
        }

        output = results.unsupported_result(adapter, "prompt", None)

        self.assertEqual(output["gate_decision"], "needs_adapter_implementation")
        self.assertEqual(output["constraint_results"][0]["status"], "unknown")

    def test_verifier_registry_names_registered_modules(self):
        registry_obj = verifiers.VerifierRegistry()
        registry_obj.register(
            "demo",
            lambda _prompt, _answer: {"violations": []},
            correction_routes={"new_violation": "revise"},
        )

        self.assertEqual(registry_obj.names(), ["demo"])
        self.assertEqual(registry_obj.get("demo").name, "demo")
        self.assertEqual(registry_obj.get("demo").correction_routes, {"new_violation": "revise"})
        self.assertEqual(registry_obj.get("demo").run("prompt", "answer"), {"violations": []})


if __name__ == "__main__":
    unittest.main()
