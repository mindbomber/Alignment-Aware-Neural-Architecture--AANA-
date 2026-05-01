import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_adapter.py"
TRAVEL_ADAPTER = ROOT / "examples" / "travel_adapter.json"
MEAL_ADAPTER = ROOT / "examples" / "meal_planning_adapter.json"
SUPPORT_ADAPTER = ROOT / "examples" / "support_reply_adapter.json"

spec = importlib.util.spec_from_file_location("run_adapter", RUNNER_PATH)
run_adapter_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_adapter_module)


class RunAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = run_adapter_module.load_adapter(TRAVEL_ADAPTER)
        self.prompt = (
            "Plan a one-day San Diego museum outing for two adults with a hard "
            "$110 total budget, public transit only, lunch included, and no "
            "single ticket above $25."
        )

    def test_travel_adapter_generates_gated_answer_without_candidate(self):
        result = run_adapter_module.run_adapter(self.adapter, self.prompt)

        self.assertEqual(result["adapter"]["name"], "travel_planner_aana_adapter")
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "accept")
        self.assertIn("San Diego", result["final_answer"])
        self.assertIn("lunch", result["final_answer"].lower())
        self.assertFalse(result["tool_report"]["violations"])
        self.assertTrue(all(item["status"] == "pass" for item in result["constraint_results"]))

    def test_travel_adapter_blocks_and_repairs_bad_candidate(self):
        candidate = "Use rideshare, skip lunch, buy a $40 ticket, and spend $150 total."

        result = run_adapter_module.run_adapter(self.adapter, self.prompt, candidate)

        self.assertEqual(result["candidate_gate"], "block")
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "revise")
        self.assertGreater(len(result["candidate_tool_report"]["violations"]), 0)
        self.assertFalse(result["tool_report"]["violations"])

    def test_blank_adapter_loads_but_defers_execution(self):
        adapter = run_adapter_module.load_adapter(ROOT / "examples" / "domain_adapter_template.json")

        result = run_adapter_module.run_adapter(adapter, self.prompt)

        self.assertEqual(result["recommended_action"], "defer")
        self.assertEqual(result["gate_decision"], "needs_adapter_implementation")
        self.assertTrue(result["constraint_results"])
        self.assertTrue(all(item["status"] == "unknown" for item in result["constraint_results"]))

    def test_meal_adapter_generates_gated_answer_without_candidate(self):
        adapter = run_adapter_module.load_adapter(MEAL_ADAPTER)
        prompt = (
            "Create a weekly gluten-free, dairy-free meal plan for one person "
            "with a $70 grocery budget."
        )

        result = run_adapter_module.run_adapter(adapter, prompt)

        self.assertEqual(result["adapter"]["name"], "meal_planning_aana_adapter")
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "accept")
        self.assertIn("gluten-free", result["final_answer"].lower())
        self.assertIn("no dairy", result["final_answer"].lower())
        self.assertFalse(result["tool_report"]["violations"])

    def test_meal_adapter_blocks_and_repairs_bad_candidate(self):
        adapter = run_adapter_module.load_adapter(MEAL_ADAPTER)
        prompt = (
            "Create a weekly gluten-free, dairy-free meal plan for one person "
            "with a $70 grocery budget."
        )
        candidate = (
            "Buy regular pasta, wheat bread, cheese, and milk for $95 total. "
            "Monday: pasta. Tuesday: cheese sandwiches."
        )

        result = run_adapter_module.run_adapter(adapter, prompt, candidate)

        self.assertEqual(result["candidate_gate"], "block")
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "revise")
        self.assertGreater(len(result["candidate_tool_report"]["violations"]), 0)
        self.assertFalse(result["tool_report"]["violations"])

    def test_support_adapter_generates_secure_ask_without_candidate(self):
        adapter = run_adapter_module.load_adapter(SUPPORT_ADAPTER)
        prompt = (
            "Draft a customer-support reply for a refund request. Use only verified facts: "
            "customer name is Maya Chen, order ID and refund eligibility are not available, "
            "and do not include private account details or invent policy promises."
        )

        result = run_adapter_module.run_adapter(adapter, prompt)

        self.assertEqual(result["adapter"]["name"], "support_reply_aana_adapter")
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "ask")
        self.assertIn("Maya", result["final_answer"])
        self.assertIn("cannot confirm", result["final_answer"].lower())
        self.assertIn("order ID", result["final_answer"])
        self.assertFalse(result["tool_report"]["violations"])

    def test_support_adapter_blocks_private_and_invented_candidate(self):
        adapter = run_adapter_module.load_adapter(SUPPORT_ADAPTER)
        prompt = (
            "Draft a customer-support reply for a refund request. Use only verified facts: "
            "customer name is Maya Chen, order ID and refund eligibility are not available, "
            "and do not include private account details or invent policy promises."
        )
        candidate = (
            "Hi Maya, order #A1842 is eligible for a full refund and your card "
            "ending 4242 will be credited in 3 days."
        )

        result = run_adapter_module.run_adapter(adapter, prompt, candidate)

        self.assertEqual(result["candidate_gate"], "block")
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "revise")
        self.assertGreater(len(result["candidate_tool_report"]["violations"]), 0)
        self.assertFalse(result["tool_report"]["violations"])


if __name__ == "__main__":
    unittest.main()
