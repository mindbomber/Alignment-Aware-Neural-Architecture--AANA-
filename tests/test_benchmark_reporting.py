import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.benchmark_reporting import validate_benchmark_reporting_manifest


ROOT = Path(__file__).resolve().parents[1]


def valid_manifest():
    return {
        "schema_version": "0.1",
        "policy": {
            "never_merge_probe_results_into_public_claims": True,
            "require_scope_label": True,
        },
        "benchmark_reports": [
            {
                "report_id": "general-result",
                "benchmark": "example benchmark",
                "run_type": "general",
                "scope_label": "public_general_result",
                "summary": "Measured general run without probes.",
                "public_claim": True,
                "public_claim_eligible": True,
                "includes_probe_results": False,
                "uses_allow_benchmark_probes": False,
                "probe_results_policy": "excluded_from_public_claims",
                "limitations": ["Labels are maintainer-reviewed."],
                "artifacts": {"primary_results": ["docs/example.md"], "probe_results": []},
            }
        ],
    }


class BenchmarkReportingTests(unittest.TestCase):
    def test_current_manifest_is_valid(self):
        manifest = json.loads((ROOT / "examples" / "benchmark_reporting_manifest.json").read_text(encoding="utf-8"))
        report = validate_benchmark_reporting_manifest(manifest)

        self.assertTrue(report["valid"], report["issues"])
        self.assertGreaterEqual(report["report_count"], 1)

    def test_blocks_public_claim_with_probe_results(self):
        manifest = valid_manifest()
        row = manifest["benchmark_reports"][0]
        row["includes_probe_results"] = True
        row["artifacts"]["probe_results"] = ["examples/tau2/aana_tau2_probe_planners.py"]
        report = validate_benchmark_reporting_manifest(manifest)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"].endswith("includes_probe_results") for issue in report["issues"]))

    def test_blocks_public_claim_from_probe_run_type(self):
        manifest = valid_manifest()
        row = manifest["benchmark_reports"][0]
        row["run_type"] = "diagnostic_probe"
        row["uses_allow_benchmark_probes"] = True
        report = validate_benchmark_reporting_manifest(manifest)

        self.assertFalse(report["valid"])
        self.assertTrue(any("diagnostic_probe" in issue["message"] for issue in report["issues"]))

    def test_blocks_probe_report_marked_public_claim_eligible(self):
        manifest = valid_manifest()
        row = manifest["benchmark_reports"][0]
        row["public_claim"] = False
        row["public_claim_eligible"] = True
        row["includes_probe_results"] = True
        report = validate_benchmark_reporting_manifest(manifest)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"].endswith("public_claim_eligible") for issue in report["issues"]))

    def test_cli_validates_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "benchmark_reporting.json"
            manifest_path.write_text(json.dumps(valid_manifest()), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "scripts/validate_benchmark_reporting.py", "--manifest", str(manifest_path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass -- reports=1", completed.stdout)


if __name__ == "__main__":
    unittest.main()
