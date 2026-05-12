import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import aana
from eval_pipeline import agent_api, croissant_evidence


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CroissantEvidenceTests(unittest.TestCase):
    def test_imports_croissant_metadata_to_aana_evidence_registry(self):
        metadata = json.loads((ROOT / "examples" / "croissant_metadata_sample.json").read_text(encoding="utf-8"))
        summary = croissant_evidence.croissant_metadata_summary(metadata)
        registry = croissant_evidence.croissant_to_evidence_registry(metadata)
        registry_validation = agent_api.validate_evidence_registry(registry)

        self.assertEqual(summary["source_id"], "croissant-synthetic-support-cases-2026-05")
        self.assertTrue(summary["gap_report"]["valid"], summary["gap_report"])
        self.assertEqual(summary["licenses"], ["https://spdx.org/licenses/CC-BY-4.0.html"])
        self.assertIn("customer_email", summary["sensitive_fields"])
        self.assertEqual(len(registry["sources"]), 1)
        source = registry["sources"][0]
        self.assertTrue(source["enabled"])
        self.assertEqual(source["metadata"]["source_type"], "croissant_dataset")
        self.assertFalse("Prompt_text" in json.dumps(source))
        self.assertTrue(registry_validation["valid"], registry_validation)

    def test_missing_governance_metadata_flags_gaps_and_disables_source(self):
        metadata = json.loads((ROOT / "examples" / "croissant_metadata_missing_governance.json").read_text(encoding="utf-8"))
        summary = croissant_evidence.croissant_metadata_summary(metadata)
        source = croissant_evidence.croissant_to_evidence_source(metadata)

        self.assertFalse(summary["gap_report"]["valid"])
        self.assertGreaterEqual(summary["gap_report"]["errors"], 3)
        self.assertFalse(source["enabled"])
        self.assertIn("patient_name", summary["sensitive_fields"])
        fields = {gap["field"] for gap in summary["gap_report"]["gaps"]}
        self.assertGreaterEqual(fields, {"creator", "license", "distribution"})

    def test_import_command_writes_registry_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output_registry = pathlib.Path(directory) / "evidence-registry.json"
            report_path = pathlib.Path(directory) / "croissant-report.json"
            report = croissant_evidence.import_croissant_evidence(
                metadata_path=ROOT / "examples" / "croissant_metadata_sample.json",
                output_registry=output_registry,
                report_path=report_path,
            )

            self.assertTrue(report["valid"], report)
            self.assertTrue(output_registry.exists())
            self.assertTrue(report_path.exists())
            registry = json.loads(output_registry.read_text(encoding="utf-8"))
            self.assertEqual(registry["sources"][0]["source_id"], "croissant-synthetic-support-cases-2026-05")

    def test_cli_croissant_evidence_import(self):
        with tempfile.TemporaryDirectory() as directory:
            output_registry = pathlib.Path(directory) / "evidence-registry.json"
            report_path = pathlib.Path(directory) / "croissant-report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/aana_cli.py",
                    "croissant-evidence-import",
                    "--metadata",
                    "examples/croissant_metadata_sample.json",
                    "--output-registry",
                    str(output_registry),
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
            self.assertTrue(payload["valid"], payload)
            self.assertTrue(output_registry.exists())
            self.assertTrue(report_path.exists())

    def test_python_sdk_exports_croissant_helpers(self):
        self.assertTrue(callable(aana.import_croissant_evidence))
        self.assertTrue(callable(aana.croissant_to_evidence_registry))
        self.assertEqual(aana.CROISSANT_EVIDENCE_IMPORT_VERSION, croissant_evidence.CROISSANT_EVIDENCE_IMPORT_VERSION)


if __name__ == "__main__":
    unittest.main()
