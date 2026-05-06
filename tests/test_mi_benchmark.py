import json
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_benchmark import (
    BENCHMARK_MODES,
    benchmark_workflows,
    run_mi_benchmark,
    write_mi_benchmark_report,
    write_mi_benchmark_workflows,
)


class MIBenchmarkTests(unittest.TestCase):
    def test_benchmark_workflows_cover_propagation_and_global_cases(self):
        workflows = benchmark_workflows()
        ids = {workflow["workflow_id"] for workflow in workflows}
        domains = {workflow["workflow_domain"] for workflow in workflows}

        self.assertIn("mi-propagated-premise", ids)
        self.assertIn("mi-boundary-mismatch", ids)
        self.assertIn("mi-irreversible-capacity-gap", ids)
        self.assertIn("mi-file-edit-workspace-scope", ids)
        self.assertIn("mi-deployment-release-strict", ids)
        self.assertIn("mi-email-calendar-stale-context", ids)
        self.assertIn("mi-research-citation-unsupported", ids)
        self.assertIn("file_edit", domains)
        self.assertIn("deployment_release", domains)
        self.assertIn("email_calendar", domains)
        self.assertIn("research_citation", domains)
        self.assertTrue(all(isinstance(workflow.get("handoffs"), list) for workflow in workflows))

    def test_benchmark_compares_all_modes(self):
        report = run_mi_benchmark()

        self.assertEqual(report["mode_order"], list(BENCHMARK_MODES))
        self.assertEqual(report["workflow_count"], len(benchmark_workflows()))
        for workflow in report["workflows"]:
            self.assertEqual([mode["mode"] for mode in workflow["modes"]], list(BENCHMARK_MODES))

    def test_full_global_gate_detects_more_propagation_than_local_gate(self):
        report = run_mi_benchmark()
        local = report["metrics"]["local_aana_gate"]
        full = report["metrics"]["full_global_aana_gate"]

        self.assertLess(local["detection_rate"], full["detection_rate"])
        self.assertEqual(full["false_negative"], 0)
        self.assertEqual(full["false_positive"], 0)

    def test_expected_mode_behavior_for_key_workflows(self):
        report = run_mi_benchmark()
        by_id = {workflow["workflow_id"]: workflow for workflow in report["workflows"]}
        propagated = {mode["mode"]: mode for mode in by_id["mi-propagated-premise"]["modes"]}
        boundary = {mode["mode"]: mode for mode in by_id["mi-boundary-mismatch"]["modes"]}
        irreversible = {mode["mode"]: mode for mode in by_id["mi-irreversible-capacity-gap"]["modes"]}
        file_edit = {mode["mode"]: mode for mode in by_id["mi-file-edit-workspace-scope"]["modes"]}
        deployment = {mode["mode"]: mode for mode in by_id["mi-deployment-release-strict"]["modes"]}
        email_calendar = {mode["mode"]: mode for mode in by_id["mi-email-calendar-stale-context"]["modes"]}
        research = {mode["mode"]: mode for mode in by_id["mi-research-citation-unsupported"]["modes"]}

        self.assertFalse(propagated["schema_only_interoperability"]["detected"])
        self.assertFalse(propagated["local_aana_gate"]["detected"])
        self.assertFalse(propagated["mi_boundary_gate"]["detected"])
        self.assertTrue(propagated["full_global_aana_gate"]["detected"])
        self.assertIn("uncertain_output_became_premise", propagated["full_global_aana_gate"]["signals"])

        self.assertFalse(boundary["local_aana_gate"]["detected"])
        self.assertTrue(boundary["mi_boundary_gate"]["detected"])
        self.assertIn("boundary_type_mismatch", boundary["mi_boundary_gate"]["signals"])

        self.assertFalse(irreversible["mi_boundary_gate"]["detected"])
        self.assertTrue(irreversible["full_global_aana_gate"]["detected"])
        self.assertIn("insufficient_correction_capacity", irreversible["full_global_aana_gate"]["signals"])

        self.assertTrue(file_edit["local_aana_gate"]["detected"])
        self.assertIn("C_verifier_failed", file_edit["local_aana_gate"]["signals"])
        self.assertFalse(deployment["mi_boundary_gate"]["detected"])
        self.assertTrue(deployment["full_global_aana_gate"]["detected"])
        self.assertFalse(email_calendar["mi_boundary_gate"]["detected"])
        self.assertTrue(email_calendar["full_global_aana_gate"]["detected"])
        self.assertIn("stale_evidence", email_calendar["full_global_aana_gate"]["signals"])
        self.assertFalse(research["schema_only_interoperability"]["detected"])
        self.assertTrue(research["full_global_aana_gate"]["detected"])

    def test_writes_reproducible_fixture_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            workflows_path = Path(directory) / "workflows.json"
            report_path = Path(directory) / "report.json"
            write_mi_benchmark_workflows(workflows_path)
            write_mi_benchmark_report(report_path)

            workflows_payload = json.loads(workflows_path.read_text(encoding="utf-8"))
            report_payload = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(len(workflows_payload["workflows"]), len(benchmark_workflows()))
        self.assertEqual(report_payload["workflow_count"], len(benchmark_workflows()))


if __name__ == "__main__":
    unittest.main()
