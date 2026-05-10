import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.production_candidate_evidence_pack import (
    EXACT_NOT_PROVEN_ENGINE_CLAIM,
    EXACT_PRODUCTION_CANDIDATE_CLAIM,
    validate_production_candidate_evidence_pack,
)


ROOT = Path(__file__).resolve().parents[1]


def load_current():
    return json.loads((ROOT / "examples" / "production_candidate_evidence_pack.json").read_text(encoding="utf-8"))


class ProductionCandidateEvidencePackTests(unittest.TestCase):
    def test_current_manifest_and_report_are_valid(self):
        manifest = load_current()
        report = validate_production_candidate_evidence_pack(manifest, root=ROOT, require_existing_artifacts=True)

        self.assertTrue(report["valid"], report["issues"])
        self.assertGreaterEqual(report["required_artifact_count"], 3)

    def test_requires_exact_claim_boundary(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["claim_boundary"]["production_candidate_layer"] = EXACT_PRODUCTION_CANDIDATE_CLAIM.replace("production-candidate", "production-ready")

        report = validate_production_candidate_evidence_pack(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("exact approved language" in issue["message"] for issue in report["issues"]))

    def test_blocks_raw_agent_engine_claims(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["policy"]["allow_raw_agent_performance_claim"] = True
        broken["claim_boundary"]["not_proven_engine"] = EXACT_NOT_PROVEN_ENGINE_CLAIM

        report = validate_production_candidate_evidence_pack(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("Raw agent-performance claims" in issue["message"] for issue in report["issues"]))

    def test_blocks_raw_agent_superiority_claims(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["policy"]["allow_raw_agent_performance_superiority_claim"] = True

        report = validate_production_candidate_evidence_pack(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("superiority" in issue["message"] for issue in report["issues"]))

    def test_requires_public_result_label(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["result_label"] = "diagnostic"

        report = validate_production_candidate_evidence_pack(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "result_label" for issue in report["issues"]))

    def test_requires_limitations(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["limitations"]["latency"] = []

        report = validate_production_candidate_evidence_pack(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "limitations.latency" for issue in report["issues"]))

    def test_requires_report_sections(self):
        manifest = load_current()
        broken = copy.deepcopy(manifest)
        broken["required_report_sections"].append("## Missing Section")

        report = validate_production_candidate_evidence_pack(broken, root=ROOT)

        self.assertFalse(report["valid"])
        self.assertTrue(any("Missing Section" in issue["message"] for issue in report["issues"]))

    def test_cli_validates_manifest(self):
        manifest = load_current()
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "production-evidence.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/validation/validate_production_candidate_evidence_pack.py",
                    "--manifest",
                    str(manifest_path),
                    "--require-existing-artifacts",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass -- sections=", completed.stdout)


if __name__ == "__main__":
    unittest.main()
