import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.validate_mi_contracts import ROOT, validate_mi_contracts


class ValidateMIContractsTests(unittest.TestCase):
    def test_default_mi_contract_artifacts_validate(self):
        report = validate_mi_contracts()

        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["issue_count"], 0)
        self.assertIn("pilot_handoffs", report["artifacts"])

    def test_cli_passes_for_default_artifacts(self):
        completed = subprocess.run(
            [sys.executable, "scripts/validate_mi_contracts.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("ok -- MI contract validation passed", completed.stdout)

    def test_cli_fails_on_pilot_handoff_contract_drift(self):
        source = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "pilot_handoffs.json"
        with tempfile.TemporaryDirectory() as directory:
            drifted = Path(directory) / "pilot_handoffs.json"
            payload = json.loads(source.read_text(encoding="utf-8"))
            del payload["handoffs"][0]["recommended_action"]
            drifted.write_text(json.dumps(payload), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/validate_mi_contracts.py",
                    "--pilot-handoffs",
                    str(drifted),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("recommended_action", completed.stderr)

    def test_json_output_reports_machine_readable_status(self):
        completed = subprocess.run(
            [sys.executable, "scripts/validate_mi_contracts.py", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["valid"])
        self.assertEqual(report["issue_count"], 0)

    def test_cli_fails_on_audit_manifest_tamper(self):
        audit_source = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_audit.jsonl"
        manifest_source = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_audit.jsonl.sha256.json"
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "mi_audit.jsonl"
            manifest_path = Path(directory) / "mi_audit.jsonl.sha256.json"
            audit_path.write_text(audit_source.read_text(encoding="utf-8"), encoding="utf-8")
            manifest_path.write_text(manifest_source.read_text(encoding="utf-8"), encoding="utf-8")
            lines = audit_path.read_text(encoding="utf-8").splitlines()
            first = json.loads(lines[0])
            first["gate_decision"] = "fail"
            lines[0] = json.dumps(first, sort_keys=True)
            audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/validate_mi_contracts.py",
                    "--audit-jsonl",
                    str(audit_path),
                    "--audit-manifest",
                    str(manifest_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("does not match", completed.stderr)

    def test_cli_fails_on_schema_artifact_version_drift(self):
        source = ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "pilot_handoffs.json"
        with tempfile.TemporaryDirectory() as directory:
            drifted = Path(directory) / "pilot_handoffs.json"
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["handoffs"][0]["contract_version"] = "9.9"
            drifted.write_text(json.dumps(payload), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/validate_mi_contracts.py",
                    "--pilot-handoffs",
                    str(drifted),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("not compatible", completed.stderr)


if __name__ == "__main__":
    unittest.main()
