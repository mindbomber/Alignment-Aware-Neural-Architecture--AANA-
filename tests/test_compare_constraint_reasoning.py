import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from compare_constraint_reasoning import CONDITIONS, build_summary, load_constraint_rows


class CompareConstraintReasoningTests(unittest.TestCase):
    def test_aana_structured_improves_pass_rate_and_capability_over_baseline(self):
        rows, by_condition_key = load_constraint_rows(
            [
                ROOT / "eval_outputs" / "heldout_v2" / "judged_outputs_v2.csv",
                ROOT / "eval_outputs" / "schema_ablation" / "hybrid_gate_judged.csv",
            ],
            CONDITIONS,
        )

        summary, paired = build_summary(rows, by_condition_key, CONDITIONS, iterations=200)
        by_condition = {row["condition"]: row for row in summary}
        paired_by_condition = {row["condition"]: row for row in paired}

        structured = by_condition["aana_tools_structured"]
        self.assertGreater(structured["pass_delta_vs_baseline"], 0.4)
        self.assertGreater(structured["capability_delta_vs_baseline"], 0.2)
        self.assertEqual(paired_by_condition["aana_tools_structured"]["base_pass_other_nonpass"], 0)
        self.assertGreater(paired_by_condition["aana_tools_structured"]["base_nonpass_other_pass"], 50)


if __name__ == "__main__":
    unittest.main()
