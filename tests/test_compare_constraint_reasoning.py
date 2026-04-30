import sys
import unittest
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from compare_constraint_reasoning import build_summary


class CompareConstraintReasoningTests(unittest.TestCase):
    def test_aana_structured_improves_pass_rate_and_capability_over_baseline(self):
        rows = []
        for idx in range(1, 5):
            for pressure in ["low", "high"]:
                base_pass = idx == 1
                rows.append(
                    {
                        "id": f"task_{idx}",
                        "pressure": pressure,
                        "correction": "baseline",
                        "decision": "pass" if base_pass else "fail",
                        "capability_score": "0.6",
                        "alignment_score": "0.7",
                        "gap_score": "-0.1",
                    }
                )
                rows.append(
                    {
                        "id": f"task_{idx}",
                        "pressure": pressure,
                        "correction": "aana_tools_structured",
                        "decision": "pass",
                        "capability_score": "0.9",
                        "alignment_score": "0.95",
                        "gap_score": "-0.05",
                    }
                )

        by_condition_key = {
            (row["correction"], (row["id"], row["pressure"])): row
            for row in rows
        }

        summary, paired = build_summary(
            rows,
            by_condition_key,
            ["baseline", "aana_tools_structured"],
            iterations=200,
        )
        by_condition = {row["condition"]: row for row in summary}
        paired_by_condition = {row["condition"]: row for row in paired}

        structured = by_condition["aana_tools_structured"]
        self.assertGreater(structured["pass_delta_vs_baseline"], 0.5)
        self.assertGreater(structured["capability_delta_vs_baseline"], 0.2)
        self.assertEqual(paired_by_condition["aana_tools_structured"]["base_pass_other_nonpass"], 0)
        self.assertEqual(paired_by_condition["aana_tools_structured"]["base_nonpass_other_pass"], 6)


if __name__ == "__main__":
    unittest.main()
