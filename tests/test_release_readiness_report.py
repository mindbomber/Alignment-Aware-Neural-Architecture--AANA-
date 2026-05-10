import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_audit import append_mi_audit_jsonl, mi_audit_record
from eval_pipeline.mi_boundary_gate import mi_boundary_gate
from eval_pipeline.pilot_hardening import write_guarded_research_citation_pilot
from eval_pipeline.production_readiness import production_mi_readiness_gate
from eval_pipeline.release_readiness_report import (
    parse_release_checklist_markdown,
    release_readiness_report,
    write_release_readiness_report,
)
from tests.test_handoff_gate import clean_handoff
from tests.test_production_readiness import clean_batch


ROOT = Path(__file__).resolve().parents[1]


def _write_ready_artifacts(directory: Path, readiness: dict):
    audit_path = directory / "mi_audit.jsonl"
    pilot_path = directory / "pilot_result.json"
    dashboard_path = directory / "mi_dashboard.json"
    queue_path = directory / "mi_human_review_queue.jsonl"

    result = mi_boundary_gate(clean_handoff())
    append_mi_audit_jsonl(audit_path, [mi_audit_record(result)])
    pilot_path.write_text(json.dumps({"mi_batch": clean_batch()}), encoding="utf-8")
    dashboard_path.write_text(
        json.dumps(
            {
                "mi_observability_dashboard_version": "0.1",
                "source": "unit-test",
                "metrics": {},
                "panels": {},
                "workflow_rows": [],
            }
        ),
        encoding="utf-8",
    )
    return {
        "audit_jsonl": audit_path,
        "pilot_result": pilot_path,
        "dashboard": dashboard_path,
        "human_review_queue": queue_path,
        "readiness": readiness,
    }


class ReleaseReadinessReportTests(unittest.TestCase):
    def test_parse_release_checklist_markdown_extracts_machine_rows(self):
        parsed = parse_release_checklist_markdown()

        self.assertEqual(len(parsed["required_checks"]), 5)
        self.assertEqual(len(parsed["blocking_conditions"]), 5)
        self.assertEqual(len(parsed["release_signoff"]), 5)
        self.assertEqual(parsed["blocking_conditions"][0]["condition"], "MI checks missing")

    def test_ready_release_report_passes_when_gate_and_signoff_pass(self):
        readiness = production_mi_readiness_gate(clean_batch())
        with tempfile.TemporaryDirectory() as directory:
            artifacts = _write_ready_artifacts(Path(directory), readiness)
            report = release_readiness_report(readiness=readiness, artifact_paths=artifacts)

        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["can_execute_directly"])
        self.assertEqual(report["counts"]["unresolved_count"], 0)
        self.assertEqual(report["unresolved_items"], [])

    def test_blocked_pilot_report_lists_unresolved_gate_and_signoff_items(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = write_guarded_research_citation_pilot(directory, allow_direct_execution=True)
            readiness = payload["result"]["production_mi_readiness"]
            report = release_readiness_report(readiness=readiness, artifact_paths=payload["paths"])

        unresolved_ids = {item["id"] for item in report["unresolved_items"]}

        self.assertEqual(report["status"], "block")
        self.assertFalse(report["can_execute_directly"])
        self.assertIn("propagation-resolved", unresolved_ids)
        self.assertIn("dashboard-propagation-clear", unresolved_ids)
        self.assertGreaterEqual(report["counts"]["unresolved_count"], 2)

    def test_write_release_readiness_report_outputs_json(self):
        readiness = production_mi_readiness_gate(clean_batch())
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            artifacts = _write_ready_artifacts(directory_path, readiness)
            output_path = directory_path / "release_report.json"
            payload = write_release_readiness_report(output_path, readiness=readiness, artifact_paths=artifacts)
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertGreater(payload["bytes"], 0)
        self.assertEqual(written["release_readiness_report_version"], "0.1")
        self.assertEqual(written["status"], "pass")

    def test_cli_returns_block_for_unresolved_release_report(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = write_guarded_research_citation_pilot(directory, allow_direct_execution=True)
            readiness_path = Path(directory) / "readiness.json"
            readiness_path.write_text(json.dumps(payload["result"]["production_mi_readiness"]), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/publication/release_readiness_report.py",
                    "--readiness",
                    str(readiness_path),
                    "--output",
                    str(Path(directory) / "report.json"),
                    "--audit-jsonl",
                    payload["paths"]["mi_audit_jsonl"],
                    "--pilot-result",
                    payload["paths"]["pilot_result"],
                    "--dashboard",
                    payload["paths"]["mi_dashboard"],
                    "--human-review-queue",
                    payload["paths"]["human_review_queue"],
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("block --", completed.stdout)
        self.assertIn("propagation-resolved", completed.stdout)


if __name__ == "__main__":
    unittest.main()
