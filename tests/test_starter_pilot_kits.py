import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


starter_kits = load_script("run_starter_pilot_kit", ROOT / "scripts" / "run_starter_pilot_kit.py")


class StarterPilotKitTests(unittest.TestCase):
    def test_index_lists_required_starter_packs(self):
        index = starter_kits.load_index(ROOT / "examples" / "starter_pilot_kits" / "index.json")
        kit_ids = {kit["id"] for kit in index["kits"]}
        self.assertEqual(kit_ids, {"enterprise", "personal_productivity", "civic_government"})

    def test_each_kit_has_required_files_and_workflows(self):
        index = starter_kits.load_index(ROOT / "examples" / "starter_pilot_kits" / "index.json")
        for kit in index["kits"]:
            kit_path = ROOT / kit["path"]
            for filename in [
                "manifest.json",
                "adapter_config.json",
                "synthetic_data.json",
                "workflows.json",
                "expected_outcomes.json",
            ]:
                self.assertTrue((kit_path / filename).is_file(), f"{kit['id']} missing {filename}")
            bundle = starter_kits.load_kit_bundle(kit_path)
            self.assertGreater(len(bundle["workflows"]["workflows"]), 0)
            self.assertGreater(len(bundle["synthetic_data"]["records"]), 0)
            self.assertIn("default_expected", bundle["expected_outcomes"])
            self.assertIn("minimum_metrics", bundle["expected_outcomes"])

    def test_personal_productivity_kit_runs_with_redacted_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = starter_kits.parse_args(["--kit", "personal_productivity", "--output-root", temp_dir])
            report = starter_kits.run_selected(args)

            self.assertTrue(report["valid"])
            self.assertEqual(report["summary"]["kits"], 1)
            self.assertEqual(report["summary"]["workflows"], 7)
            self.assertEqual(report["summary"]["audit_records"], 7)

            kit_report = report["kits"][0]
            output_dir = pathlib.Path(temp_dir) / "personal_productivity"
            audit_log = output_dir / "audit.jsonl"
            metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
            materialized = json.loads((output_dir / "materialized_workflows.json").read_text(encoding="utf-8"))

            self.assertEqual(len(audit_log.read_text(encoding="utf-8").strip().splitlines()), 7)
            self.assertEqual(metrics["record_count"], 7)
            self.assertEqual(metrics["metrics"]["audit_records_total"], 7)
            self.assertEqual(metrics["metrics"]["recommended_action_count.revise"], 7)
            self.assertEqual(len(materialized["requests"]), 7)
            self.assertTrue((output_dir / "report.md").is_file())
            self.assertTrue((output_dir / "report.json").is_file())
            self.assertTrue(kit_report["minimum_metric_checks"]["audit_records_total"]["passed"])

    def test_all_starter_kits_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = starter_kits.parse_args(["--kit", "all", "--output-root", temp_dir])
            report = starter_kits.run_selected(args)

            self.assertTrue(report["valid"])
            self.assertEqual(report["summary"]["kits"], 3)
            self.assertEqual(report["summary"]["workflows"], 23)
            self.assertEqual(report["summary"]["audit_records"], 23)
            by_id = {kit["kit_id"]: kit for kit in report["kits"]}
            self.assertEqual(by_id["enterprise"]["summary"]["workflows"], 8)
            self.assertEqual(by_id["personal_productivity"]["summary"]["workflows"], 7)
            self.assertEqual(by_id["civic_government"]["summary"]["workflows"], 8)


if __name__ == "__main__":
    unittest.main()
