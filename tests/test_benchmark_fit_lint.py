import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.benchmark_fit_lint import validate_benchmark_fit_manifest


ROOT = Path(__file__).resolve().parents[1]


def valid_manifest(tmp_file: str = "*.py"):
    return {
        "schema_version": "0.1",
        "policy": {
            "decision_rule": "reject_answer_known_benchmark_fits_from_general_path",
            "scan_include": [tmp_file],
            "allowed_literal_paths": ["allowed_probe.py"],
            "required_adapter_family_surfaces": [],
        },
        "forbidden_literal_groups": [
            {
                "id": "known_answers",
                "description": "Known answer literals.",
                "literals": ["EXACT_BENCHMARK_ANSWER"],
            }
        ],
    }


class BenchmarkFitLintTests(unittest.TestCase):
    def test_current_manifest_passes(self):
        manifest = json.loads((ROOT / "examples" / "benchmark_fit_lint_manifest.json").read_text(encoding="utf-8"))
        report = validate_benchmark_fit_manifest(manifest, root=ROOT)

        self.assertTrue(report["valid"], report["issues"])
        self.assertGreaterEqual(report["scanned_file_count"], 1)

    def test_blocks_known_answer_literal_in_general_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "general.py").write_text("value = 'EXACT_BENCHMARK_ANSWER'\n", encoding="utf-8")
            report = validate_benchmark_fit_manifest(valid_manifest("*.py"), root=root)

        self.assertFalse(report["valid"])
        self.assertEqual(report["finding_count"], 1)
        self.assertIn("general.py", report["issues"][0]["path"])

    def test_allows_known_answer_literal_in_probe_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "allowed_probe.py").write_text("value = 'EXACT_BENCHMARK_ANSWER'\n", encoding="utf-8")
            report = validate_benchmark_fit_manifest(valid_manifest("*.py"), root=root)

        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["finding_count"], 0)

    def test_cli_validates_current_manifest(self):
        completed = subprocess.run(
            [sys.executable, "scripts/validate_benchmark_fit_lint.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass --", completed.stdout)

    def test_current_manifest_scans_all_adapter_family_surfaces(self):
        manifest = json.loads((ROOT / "examples" / "benchmark_fit_lint_manifest.json").read_text(encoding="utf-8"))
        include = set(manifest["policy"]["scan_include"])

        self.assertIn("examples/*_adapter.json", include)
        self.assertIn("examples/starter_pilot_kits/*/adapter_config.json", include)
        self.assertIn("eval_pipeline/adapter_runner/**/*.py", include)
        self.assertIn("examples/tau2/*.py", include)


if __name__ == "__main__":
    unittest.main()
