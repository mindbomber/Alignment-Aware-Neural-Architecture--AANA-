import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_release import run_mi_release


ROOT = Path(__file__).resolve().parents[1]


class MIReleaseCommandTests(unittest.TestCase):
    def test_run_mi_release_executes_candidate_bundle_and_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = run_mi_release(
                output_path=root / "release" / "aana_mi_release_report.json",
                rc_report_path=root / "rc" / "aana_mi_release_candidate_report.json",
                benchmark_dir=root / "benchmark",
                bundle_dir=root / "bundle",
            )
            report = payload["report"]
            written = json.loads(Path(payload["path"]).read_text(encoding="utf-8"))

        self.assertEqual(written, report)
        self.assertEqual(report["mi_release_command_version"], "0.1")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["stage_count"], 3)
        self.assertEqual(report["blocking_stage_count"], 0)
        self.assertEqual(report["skipped_stage_count"], 0)
        self.assertEqual([stage["name"] for stage in report["stages"]], [
            "release_candidate",
            "release_bundle",
            "release_bundle_verification",
        ])

    def test_run_mi_release_report_references_bundle_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = run_mi_release(
                output_path=root / "release.json",
                rc_report_path=root / "rc.json",
                benchmark_dir=root / "benchmark",
                bundle_dir=root / "bundle",
            )
            verification_path = Path(
                payload["report"]["stages"][2]["artifacts"]["release_bundle_verification"]
            )
            verification = json.loads(verification_path.read_text(encoding="utf-8"))

        self.assertTrue(verification["valid"])
        self.assertEqual(verification["status"], "pass")
        self.assertEqual(verification["artifact_count"], 9)

    def test_mi_release_cli_is_ci_safe_and_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_path = root / "release.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/publication/mi_release.py",
                    "--output",
                    str(output_path),
                    "--rc-report",
                    str(root / "rc.json"),
                    "--benchmark-dir",
                    str(root / "benchmark"),
                    "--bundle-dir",
                    str(root / "bundle"),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("pass -- stages=3 blocking=0 skipped=0", completed.stdout)
        self.assertEqual(report["status"], "pass")


if __name__ == "__main__":
    unittest.main()
