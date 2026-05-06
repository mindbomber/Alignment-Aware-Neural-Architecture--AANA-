import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_release_candidate import run_mi_release_candidate


ROOT = Path(__file__).resolve().parents[1]


class MIReleaseCandidateTests(unittest.TestCase):
    def test_release_candidate_runs_all_required_checks_and_writes_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "rc.json"
            benchmark_dir = Path(directory) / "benchmark"
            payload = run_mi_release_candidate(report_path=output_path, benchmark_dir=benchmark_dir)
            report = payload["report"]
            written = json.loads(output_path.read_text(encoding="utf-8"))

        check_names = {check["name"] for check in report["checks"]}

        self.assertEqual(written, report)
        self.assertEqual(report["mi_release_candidate_version"], "0.1")
        self.assertIn("schema", check_names)
        self.assertIn("pilot_handoff_contracts", check_names)
        self.assertIn("benchmark", check_names)
        self.assertIn("pilot", check_names)
        self.assertIn("audit", check_names)
        self.assertIn("audit_integrity", check_names)
        self.assertIn("readiness", check_names)
        self.assertIn("dashboard", check_names)
        self.assertIn("release_readiness", check_names)
        self.assertIn("contract_validation", check_names)

    def test_release_candidate_passes_after_release_blocker_remediation(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = run_mi_release_candidate(
                report_path=Path(directory) / "rc.json",
                benchmark_dir=Path(directory) / "benchmark",
            )
            report = payload["report"]

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["unresolved_items"], [])
        self.assertEqual(report["blocking_check_count"], 0)

    def test_release_candidate_cli_outputs_single_passing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "rc.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/mi_release_candidate.py",
                    "--output",
                    str(output_path),
                    "--benchmark-dir",
                    str(Path(directory) / "benchmark"),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0)
        self.assertIn("pass --", completed.stdout)
        self.assertEqual(report["status"], "pass")

    def test_release_candidate_cli_accepts_no_fail_on_block_option_for_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/mi_release_candidate.py",
                    "--output",
                    str(Path(directory) / "rc.json"),
                    "--benchmark-dir",
                    str(Path(directory) / "benchmark"),
                    "--no-fail-on-block",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("blocking=", completed.stdout)


if __name__ == "__main__":
    unittest.main()
