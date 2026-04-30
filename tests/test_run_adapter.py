import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_adapter.py"
TRAVEL_ADAPTER = ROOT / "examples" / "travel_adapter.json"

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


if __name__ == "__main__":
    unittest.main()
