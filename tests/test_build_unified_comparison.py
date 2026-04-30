import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from build_unified_comparison import (
    load_rows,
    summary,
    validate_matched_rows,
    write_csv,
)


FIELDS = [
    "id",
    "block",
    "task_type",
    "model",
    "pressure",
    "correction",
    "capability_score",
    "alignment_score",
    "gap_score",
    "decision",
]


def row(task_id, pressure, correction, decision="pass"):
    return {
        "id": task_id,
        "block": "constraint_reasoning",
        "task_type": "constraint_reasoning",
        "model": "example",
        "pressure": pressure,
        "correction": correction,
        "capability_score": "0.9",
        "alignment_score": "0.95",
        "gap_score": "-0.05",
        "decision": decision,
    }


class BuildUnifiedComparisonTests(unittest.TestCase):
    def test_validate_matched_rows_accepts_balanced_conditions(self):
        rows = []
        for condition in ["baseline", "aana_loop"]:
            for task_id in ["task_1", "task_2"]:
                for pressure in ["low", "high"]:
                    rows.append(row(task_id, pressure, condition))

        matched = validate_matched_rows(rows, ["baseline", "aana_loop"], ["low", "high"])

        self.assertEqual(len(matched), 4)
        summary_rows = summary(rows)
        self.assertEqual(len(summary_rows), 4)

    def test_validate_matched_rows_rejects_missing_condition_row(self):
        rows = [
            row("task_1", "low", "baseline"),
            row("task_1", "high", "baseline"),
            row("task_1", "low", "aana_loop"),
        ]

        with self.assertRaises(ValueError):
            validate_matched_rows(rows, ["baseline", "aana_loop"], ["low", "high"])

    def test_load_rows_filters_to_requested_block_and_conditions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "judged.csv"
            write_csv(
                path,
                [
                    row("task_1", "low", "baseline"),
                    {**row("task_2", "low", "baseline"), "block": "truthfulness"},
                    row("task_1", "low", "strong"),
                ],
                FIELDS,
            )

            rows, sources = load_rows([path], ["baseline"], "constraint_reasoning")

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], "task_1")
            self.assertEqual(sources[0]["matched_rows"], 1)


if __name__ == "__main__":
    unittest.main()
