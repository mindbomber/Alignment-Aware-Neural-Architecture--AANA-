import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from plot_results import read_csv, svg_report_plots


class PlotResultsTests(unittest.TestCase):
    def test_svg_report_plots_create_gap_and_pass_rate_visuals(self):
        rows = read_csv(ROOT / "docs" / "evidence" / "constraint_reasoning_aana_pressure_breakdown.csv")
        for row in rows:
            row["model"] = "example"
            row["correction"] = row["condition"]
            row["block"] = "constraint_reasoning"
            row["partial_rate"] = 0.0

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = pathlib.Path(tmp)
            svg_report_plots(rows, output_dir)

            expected = [
                "paper_gap_by_pressure.svg",
                "paper_gap_by_correction.svg",
                "paper_gap_heatmap_by_block.svg",
                "paper_pass_rate_heatmap_by_block.svg",
            ]
            for name in expected:
                path = output_dir / name
                self.assertTrue(path.exists(), name)
                self.assertIn("<svg", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
