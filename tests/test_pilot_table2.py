import csv
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from generate_pilot_tasks import build_tasks
from judge_pilot_outputs import normalize
from run_pilot_conditions import CONDITIONS
from summarize_pilot_results import write_report


class PilotTable2Tests(unittest.TestCase):
    def test_build_tasks_has_five_blocks_and_forty_prompts(self):
        tasks = build_tasks()
        blocks = {}
        for task in tasks:
            blocks.setdefault(task["block"], 0)
            blocks[task["block"]] += 1

        self.assertEqual(len(tasks), 40)
        self.assertEqual(set(blocks.values()), {8})
        self.assertEqual(len(blocks), 5)

    def test_conditions_match_pilot_design(self):
        self.assertEqual(CONDITIONS["baseline"]["pressure"], "low")
        self.assertEqual(CONDITIONS["pressure_only"]["pressure"], "high")
        self.assertEqual(CONDITIONS["weak_correction"]["pressure"], "high")
        self.assertEqual(CONDITIONS["strong_aana"]["pressure"], "high")

    def test_normalize_computes_alignment_and_delta(self):
        result = normalize(
            {
                "capability_score": 0.8,
                "P_truth_grounding": 1.0,
                "B_constraint_adherence": 0.5,
                "C_task_coherence": 0.75,
                "F_feedback_awareness": 0.25,
                "constraint_violation": 0,
                "failure_mode": "none",
            }
        )

        self.assertEqual(result["alignment_score"], 0.625)
        self.assertEqual(result["delta_score"], 0.175)

    def test_report_writes_directional_tests(self):
        rows = [
            {"condition": "baseline", "pressure": "low", "n": "40", "capability_score": "0.8", "alignment_score": "0.7", "delta_score": "0.1", "violation_rate": "0.2"},
            {"condition": "pressure_only", "pressure": "high", "n": "40", "capability_score": "0.9", "alignment_score": "0.6", "delta_score": "0.3", "violation_rate": "0.4"},
            {"condition": "weak_correction", "pressure": "high", "n": "40", "capability_score": "0.85", "alignment_score": "0.7", "delta_score": "0.15", "violation_rate": "0.2"},
            {"condition": "strong_aana", "pressure": "high", "n": "40", "capability_score": "0.86", "alignment_score": "0.82", "delta_score": "0.04", "violation_rate": "0.1"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "report.md"
            write_report(path, rows)
            text = path.read_text(encoding="utf-8")

        self.assertIn("Delta pressure-only > baseline", text)
        self.assertIn("`True`", text)


if __name__ == "__main__":
    unittest.main()
