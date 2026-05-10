import copy
import json
import unittest
from pathlib import Path

from eval_pipeline.evidence_artifact_policy import load_manifest, validate_evidence_artifact_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "evidence" / "artifact_manifest.json"


class EvidenceArtifactPolicyTests(unittest.TestCase):
    def test_manifest_covers_tracked_evidence_artifacts(self):
        report = validate_evidence_artifact_manifest(load_manifest(MANIFEST_PATH), root=ROOT)

        self.assertTrue(report["valid"], report["issues"])
        self.assertGreater(report["covered_files"], 0)
        self.assertEqual(report["covered_files"], report["tracked_files"])

    def test_public_claims_require_eligible_label(self):
        manifest = copy.deepcopy(load_manifest(MANIFEST_PATH))
        manifest["artifacts"][0]["result_label"] = "diagnostic"
        manifest["artifacts"][0]["public_claim_allowed"] = True

        report = validate_evidence_artifact_manifest(
            manifest,
            root=ROOT,
            require_existing_artifacts=False,
        )

        self.assertFalse(report["valid"])
        messages = "\n".join(issue["message"] for issue in report["issues"])
        self.assertIn("heldout or external_reporting", messages)

    def test_public_claims_block_calibration_splits(self):
        manifest = copy.deepcopy(load_manifest(MANIFEST_PATH))
        manifest["artifacts"][0]["source_split"] = "calibration_split"
        manifest["artifacts"][0]["public_claim_allowed"] = True

        report = validate_evidence_artifact_manifest(
            manifest,
            root=ROOT,
            require_existing_artifacts=False,
        )

        self.assertFalse(report["valid"])
        self.assertTrue(any("calibration" in issue["message"] for issue in report["issues"]))

    def test_requires_reproduction_command(self):
        manifest = copy.deepcopy(load_manifest(MANIFEST_PATH))
        manifest["artifacts"][0]["reproduction_command"] = ""

        report = validate_evidence_artifact_manifest(
            manifest,
            root=ROOT,
            require_existing_artifacts=False,
        )

        self.assertFalse(report["valid"])
        self.assertTrue(any("reproduction_command" in issue["path"] for issue in report["issues"]))

    def test_manifest_is_json_serializable(self):
        payload = load_manifest(MANIFEST_PATH)

        self.assertIsInstance(json.dumps(payload), str)


if __name__ == "__main__":
    unittest.main()
