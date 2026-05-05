import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_adapter.py"

spec = importlib.util.spec_from_file_location("run_adapter", RUNNER_PATH)
run_adapter_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_adapter_module)


def decision_snapshot(result):
    return {
        "adapter": result["adapter"]["name"],
        "candidate_gate": result.get("candidate_gate"),
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "aix_decision": result.get("aix", {}).get("decision"),
        "candidate_aix_decision": result.get("candidate_aix", {}).get("decision"),
        "tool_violations": [
            violation.get("code")
            for violation in (result.get("tool_report") or {}).get("violations", [])
        ],
        "candidate_violations": [
            violation.get("code")
            for violation in (result.get("candidate_tool_report") or {}).get("violations", [])
        ],
        "failed_constraints": [
            constraint.get("id")
            for constraint in result.get("constraint_results", [])
            if constraint.get("status") == "fail"
        ],
    }


class AdapterRunnerGoldenOutputTests(unittest.TestCase):
    def test_support_reply_golden_decision_surface(self):
        adapter = run_adapter_module.load_adapter(ROOT / "examples" / "support_reply_adapter.json")
        prompt = (
            "Draft a customer-support reply for a refund request. Use only verified facts: "
            "customer name is Maya Chen, order ID and refund eligibility are not available, "
            "and do not include private account details or invent policy promises."
        )

        result = run_adapter_module.run_adapter(adapter, prompt)

        self.assertEqual(
            decision_snapshot(result),
            {
                "adapter": "support_reply_aana_adapter",
                "candidate_gate": None,
                "gate_decision": "pass",
                "recommended_action": "ask",
                "aix_decision": "accept",
                "candidate_aix_decision": None,
                "tool_violations": [],
                "candidate_violations": [],
                "failed_constraints": [],
            },
        )

    def test_research_summary_golden_decision_surface(self):
        adapter = run_adapter_module.load_adapter(ROOT / "examples" / "research_summary_adapter.json")
        prompt = (
            "Summarize the evidence for remote work productivity using only the provided "
            "source notes, cite source A and source B, and label uncertainty."
        )

        result = run_adapter_module.run_adapter(adapter, prompt)

        self.assertEqual(
            decision_snapshot(result),
            {
                "adapter": "research_summary_aana_adapter",
                "candidate_gate": None,
                "gate_decision": "pass",
                "recommended_action": "accept",
                "aix_decision": "accept",
                "candidate_aix_decision": None,
                "tool_violations": [],
                "candidate_violations": [],
                "failed_constraints": [],
            },
        )

    def test_travel_bad_candidate_golden_decision_surface(self):
        adapter = run_adapter_module.load_adapter(ROOT / "examples" / "travel_adapter.json")
        prompt = (
            "Plan a one-day San Diego museum outing for two adults with a hard "
            "$110 total budget, public transit only, lunch included, and no "
            "single ticket above $25."
        )
        candidate = "Use rideshare, skip lunch, buy a $40 ticket, and spend $150 total."

        result = run_adapter_module.run_adapter(adapter, prompt, candidate)

        self.assertEqual(
            decision_snapshot(result),
            {
                "adapter": "travel_planner_aana_adapter",
                "candidate_gate": "block",
                "gate_decision": "pass",
                "recommended_action": "revise",
                "aix_decision": "accept",
                "candidate_aix_decision": "refuse",
                "tool_violations": [],
                "candidate_violations": [
                    "missing_explicit_total",
                    "incomplete_day_plan",
                    "paid_item_cap_violation",
                    "public_transit_only_violation",
                ],
                "failed_constraints": [],
            },
        )


if __name__ == "__main__":
    unittest.main()

