import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import aana
from eval_pipeline import mlcommons_aix


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MLCommonsAIxTests(unittest.TestCase):
    def test_default_profile_covers_priority_mlcommons_surfaces(self):
        profile = mlcommons_aix.default_mlcommons_aix_profile()
        validation = mlcommons_aix.validate_mlcommons_aix_profile(profile)

        self.assertTrue(validation["valid"], validation)
        surfaces = {surface["surface_id"] for surface in profile["surfaces"]}
        self.assertGreaterEqual(
            surfaces,
            {"ailuminate", "modelbench", "endpoints", "medperf", "croissant"},
        )
        self.assertIn("not production certification", profile["claim_boundary"].lower())

    def test_checked_in_profile_and_sample_results_are_valid(self):
        profile = mlcommons_aix.load_mlcommons_aix_profile(ROOT / "examples" / "mlcommons_aix_profile.json")
        validation = mlcommons_aix.validate_mlcommons_aix_profile(profile)
        results = json.loads((ROOT / "examples" / "mlcommons_ailuminate_results.json").read_text(encoding="utf-8"))
        normalized = mlcommons_aix.normalize_mlcommons_results(results, source_type="ailuminate", profile=profile)
        report = mlcommons_aix.build_mlcommons_aix_report(normalized, profile=profile)
        report_validation = mlcommons_aix.validate_mlcommons_aix_report(report)

        self.assertTrue(validation["valid"], validation)
        self.assertTrue(report_validation["valid"], report_validation)
        self.assertEqual(report["deployment_recommendation"], "pilot_ready")
        self.assertEqual(report["mlcommons_source"]["source_type"], "ailuminate")
        self.assertIn("P", report["component_scores"])
        self.assertIn("B", report["component_scores"])
        self.assertIn("C", report["component_scores"])
        self.assertIn("F", report["component_scores"])

    def test_hard_blockers_prevent_pilot_ready_recommendation(self):
        profile = mlcommons_aix.default_mlcommons_aix_profile()
        results = {
            "benchmark": "AILuminate blocker sample",
            "hazard_scores": [
                {"hazard_uid": "prv", "score": 0.98, "violation_rate": 0.04, "samples": 10},
                {"hazard_uid": "spc_med", "score": 0.97, "violation_rate": 0.03, "samples": 10},
            ],
        }
        normalized = mlcommons_aix.normalize_mlcommons_results(results, source_type="ailuminate", profile=profile)
        report = mlcommons_aix.build_mlcommons_aix_report(normalized, profile=profile)

        self.assertEqual(report["deployment_recommendation"], "not_pilot_ready")
        self.assertIn("privacy_violation", report["hard_blockers"])
        self.assertIn("unapproved_medical_advice", report["hard_blockers"])

    def test_modelbench_journal_import(self):
        results = json.loads((ROOT / "examples" / "mlcommons_modelbench_journal_sample.json").read_text(encoding="utf-8"))
        normalized = mlcommons_aix.normalize_mlcommons_results(results, source_type="modelbench")

        self.assertEqual(normalized["source_type"], "modelbench")
        self.assertEqual(len(normalized["hazard_rows"]), 2)
        self.assertEqual({row["hazard_uid"] for row in normalized["hazard_rows"]}, {"prv", "spc_fin"})
        self.assertEqual(normalized["hazard_rows"][0]["score"], 0.06)

    def test_actual_modelbench_jsonl_journal_shape_import(self):
        results = mlcommons_aix.load_mlcommons_results_artifact(
            ROOT / "examples" / "mlcommons_modelbench_journal_actual.jsonl",
            source_type="modelbench",
        )
        normalized = mlcommons_aix.normalize_mlcommons_results(results, source_type="modelbench")
        report = mlcommons_aix.build_mlcommons_aix_report(normalized)

        self.assertEqual(results["result_type"], "modelbench_journal")
        self.assertEqual(len(results["journal_events"]), 7)
        self.assertEqual(len(normalized["hazard_rows"]), 3)
        self.assertEqual(normalized["hazard_rows"][0]["score"], 0.994)
        self.assertEqual(normalized["hazard_rows"][0]["violation_rate"], 0.006)
        self.assertEqual(normalized["hazard_rows"][0]["hazard_key"], "safe_hazard-1_1-prv")
        self.assertEqual(report["deployment_recommendation"], "pilot_ready")

    def test_actual_modelbench_zstd_journal_shape_import(self):
        zstandard = __import__("zstandard")
        source = (ROOT / "examples" / "mlcommons_modelbench_journal_actual.jsonl").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "journal.jsonl.zst"
            path.write_bytes(zstandard.ZstdCompressor().compress(source))
            results = mlcommons_aix.load_mlcommons_results_artifact(path, source_type="modelbench")
            normalized = mlcommons_aix.normalize_mlcommons_results(results, source_type="modelbench")

        self.assertEqual(results["result_type"], "modelbench_journal")
        self.assertEqual(len(normalized["hazard_rows"]), 3)
        self.assertEqual(normalized["hazard_rows"][1]["hazard_uid"], "spc_hlt")

    def test_actual_ailuminate_prompt_csv_shape_import_is_coverage_not_score(self):
        results = mlcommons_aix.load_mlcommons_results_artifact(
            ROOT / "examples" / "mlcommons_ailuminate_prompt_set_sample.csv",
            source_type="ailuminate",
        )
        normalized = mlcommons_aix.normalize_mlcommons_results(results, source_type="ailuminate")
        report = mlcommons_aix.build_mlcommons_aix_report(normalized)

        self.assertEqual(results["result_type"], "mlcommons_ailuminate_prompt_set")
        self.assertEqual(results["prompt_set"]["prompt_count"], 3)
        self.assertEqual(results["prompt_set"]["hazard_counts"]["spc_hlt"], 1)
        self.assertFalse(results["prompt_set"]["raw_prompt_text_logged"])
        self.assertEqual(normalized["hazard_rows"], [])
        self.assertEqual(normalized["overall_aix"], 0.0)
        self.assertEqual(report["deployment_recommendation"], "insufficient_evidence")

    def test_run_mlcommons_aix_report_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            result = mlcommons_aix.run_mlcommons_aix_report(
                results_path=ROOT / "examples" / "mlcommons_ailuminate_results.json",
                profile_path=ROOT / "examples" / "mlcommons_aix_profile.json",
                output_dir=directory,
            )

            self.assertTrue(result["valid"], result)
            self.assertTrue(pathlib.Path(result["artifacts"]["normalized_results"]).exists())
            self.assertTrue(pathlib.Path(result["artifacts"]["report_json"]).exists())
            self.assertTrue(pathlib.Path(result["artifacts"]["report_markdown"]).exists())

    def test_cli_generates_mlcommons_aix_report(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/aana_cli.py",
                    "mlcommons-aix-report",
                    "--results",
                    "examples/mlcommons_modelbench_journal_actual.jsonl",
                    "--source-type",
                    "modelbench",
                    "--output-dir",
                    directory,
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["valid"], payload)
            self.assertEqual(payload["deployment_recommendation"], "pilot_ready")
            self.assertTrue(pathlib.Path(payload["artifacts"]["report_json"]).exists())

    def test_python_sdk_exports_mlcommons_helpers(self):
        self.assertTrue(callable(aana.run_mlcommons_aix_report))
        self.assertTrue(callable(aana.default_mlcommons_aix_profile))
        self.assertEqual(aana.MLCOMMONS_AIX_VERSION, mlcommons_aix.MLCOMMONS_AIX_VERSION)


if __name__ == "__main__":
    unittest.main()
