import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import aana
from eval_pipeline import dataperf_dynabench_audit


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DataPerfDynabenchAuditTests(unittest.TestCase):
    def test_default_profile_validates(self):
        profile = dataperf_dynabench_audit.default_dataperf_dynabench_profile()
        report = dataperf_dynabench_audit.validate_dataperf_dynabench_profile(profile)

        self.assertTrue(report["valid"], report)
        self.assertEqual(profile["profile_type"], "aana_dataperf_dynabench_audit_profile")
        self.assertIn("dataperf", profile["surfaces"])
        self.assertIn("dynabench", profile["surfaces"])
        self.assertIn("not regulated deployment approval", profile["claim_boundary"].lower())

    def test_run_audit_produces_standard_recommendation_for_clean_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            report = dataperf_dynabench_audit.run_dataperf_dynabench_audit(
                metadata_path=ROOT / "examples" / "croissant_metadata_sample.json",
                benchmark_path=ROOT / "examples" / "dataperf_dynabench_benchmark_summary.json",
                profile_path=ROOT / "examples" / "dataperf_dynabench_audit_profile.json",
                report_path=pathlib.Path(directory) / "report.json",
            )

            self.assertTrue(report["valid"], report)
            self.assertEqual(report["risk_tier_recommendation"]["risk_tier"], "standard")
            self.assertGreaterEqual(report["dataset_quality"]["quality_score"], 0.75)
            self.assertGreaterEqual(report["benchmark_coverage"]["coverage_score"], 0.8)
            self.assertEqual(report["drift_risk"]["risk_level"], "standard")

    def test_missing_metadata_and_low_coverage_raise_high_or_elevated_risk(self):
        benchmark = json.loads((ROOT / "examples" / "dataperf_dynabench_benchmark_summary.json").read_text(encoding="utf-8"))
        benchmark["baselines"] = []
        benchmark["adversarial_coverage"] = 0.0
        benchmark["drift"]["distribution_shift"] = 0.35
        benchmark["regulated_domain"] = True

        with tempfile.TemporaryDirectory() as directory:
            benchmark_path = pathlib.Path(directory) / "benchmark.json"
            benchmark_path.write_text(json.dumps(benchmark), encoding="utf-8")
            report = dataperf_dynabench_audit.run_dataperf_dynabench_audit(
                metadata_path=ROOT / "examples" / "croissant_metadata_missing_governance.json",
                benchmark_path=benchmark_path,
                report_path=pathlib.Path(directory) / "report.json",
            )

            self.assertFalse(report["valid"])
            self.assertEqual(report["risk_tier_recommendation"]["risk_tier"], "high")
            codes = {gap["code"] for gap in report["evidence_gaps"]}
            self.assertIn("large_distribution_shift", codes)
            self.assertIn("missing_baseline", codes)

    def test_drift_risk_elevates_without_errors(self):
        benchmark = json.loads((ROOT / "examples" / "dataperf_dynabench_benchmark_summary.json").read_text(encoding="utf-8"))
        benchmark["drift"]["quality_regression"] = 0.08

        drift = dataperf_dynabench_audit.drift_risk_summary(benchmark)

        self.assertEqual(drift["risk_level"], "elevated")
        self.assertTrue(any(risk["code"] == "quality_regression" for risk in drift["drift_risks"]))

    def test_cli_runs_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = pathlib.Path(directory) / "dataperf-dynabench-report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/aana_cli.py",
                    "dataperf-dynabench-audit",
                    "--metadata",
                    "examples/croissant_metadata_sample.json",
                    "--benchmark",
                    "examples/dataperf_dynabench_benchmark_summary.json",
                    "--report",
                    str(report_path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["risk_tier_recommendation"]["risk_tier"], "standard")
            self.assertTrue(report_path.exists())

    def test_public_sdk_exports_dataperf_dynabench_helpers(self):
        profile = aana.default_dataperf_dynabench_profile()

        self.assertEqual(aana.DATAPERF_DYNABENCH_AUDIT_VERSION, dataperf_dynabench_audit.DATAPERF_DYNABENCH_AUDIT_VERSION)
        self.assertEqual(aana.DATAPERF_DYNABENCH_PROFILE_TYPE, "aana_dataperf_dynabench_audit_profile")
        self.assertTrue(aana.validate_dataperf_dynabench_profile(profile)["valid"])
        self.assertTrue(callable(aana.run_dataperf_dynabench_audit))


if __name__ == "__main__":
    unittest.main()
