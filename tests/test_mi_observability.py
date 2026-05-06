import json
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_benchmark import run_mi_benchmark, write_mi_benchmark_report
from eval_pipeline.mi_observability import (
    mi_dashboard_from_benchmark,
    mi_dashboard_from_benchmark_file,
    write_mi_dashboard,
    write_mi_dashboard_from_benchmark,
)


class MIObservabilityTests(unittest.TestCase):
    def test_dashboard_contains_required_mi_metrics(self):
        dashboard = mi_dashboard_from_benchmark(run_mi_benchmark())
        metrics = dashboard["metrics"]

        for key in (
            "handoff_pass_rate",
            "handoff_fail_rate",
            "propagated_error_rate",
            "correction_success_rate",
            "false_accept_rate",
            "false_refusal_rate",
            "global_aix_drift_average_delta",
        ):
            self.assertIn(key, metrics)

    def test_dashboard_rates_match_benchmark_truth(self):
        dashboard = mi_dashboard_from_benchmark(run_mi_benchmark())
        metrics = dashboard["metrics"]

        self.assertEqual(metrics["workflow_count"], 10)
        self.assertEqual(metrics["handoff_count"], 11)
        self.assertEqual(metrics["handoff_pass_count"], 8)
        self.assertEqual(metrics["handoff_fail_count"], 3)
        self.assertEqual(metrics["handoff_pass_rate"], 0.7273)
        self.assertEqual(metrics["propagated_error_rate"], 0.6)
        self.assertEqual(metrics["correction_success_rate"], 1.0)
        self.assertEqual(metrics["false_accept_rate"], 0.0)
        self.assertEqual(metrics["false_refusal_rate"], 0.0)

    def test_dashboard_panels_are_ready_for_ui(self):
        dashboard = mi_dashboard_from_benchmark(run_mi_benchmark())
        panels = dashboard["panels"]

        self.assertIn("handoff_health", panels)
        self.assertIn("propagated_error", panels)
        self.assertIn("correction", panels)
        self.assertIn("classification_quality", panels)
        self.assertIn("global_aix_drift", panels)
        self.assertEqual(panels["classification_quality"]["false_accept_rate"], 0.0)

    def test_writes_dashboard_from_benchmark_file(self):
        with tempfile.TemporaryDirectory() as directory:
            benchmark_path = Path(directory) / "benchmark.json"
            dashboard_path = Path(directory) / "dashboard.json"
            write_mi_benchmark_report(benchmark_path)
            dashboard = write_mi_dashboard_from_benchmark(benchmark_path, dashboard_path)
            loaded = json.loads(dashboard_path.read_text(encoding="utf-8"))
            loaded_from_benchmark = mi_dashboard_from_benchmark_file(benchmark_path)

        self.assertEqual(loaded, dashboard)
        self.assertEqual(loaded_from_benchmark["metrics"], dashboard["metrics"])

    def test_write_mi_dashboard(self):
        dashboard = mi_dashboard_from_benchmark(run_mi_benchmark())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dashboard.json"
            write_mi_dashboard(path, dashboard)
            loaded = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded["mi_observability_dashboard_version"], "0.1")


if __name__ == "__main__":
    unittest.main()
