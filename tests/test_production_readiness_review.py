import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
REVIEW_PATH = ROOT / "examples" / "production_readiness_review_internal_pilot.json"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


review = load_script("validate_production_readiness_review", ROOT / "scripts" / "validation" / "validate_production_readiness_review.py")


class ProductionReadinessReviewTests(unittest.TestCase):
    def test_internal_pilot_review_passes(self):
        report = review.validate_production_readiness_review(REVIEW_PATH)

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["environment_deployable"])
        self.assertFalse(report["production_ready"])
        self.assertEqual(report["reviewed_evidence_count"], len(review.REQUIRED_EVIDENCE))

    def test_review_covers_required_evidence(self):
        payload = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
        reviewed = {item["id"]: item for item in payload["reviewed_evidence"]}

        self.assertEqual(set(reviewed), review.REQUIRED_EVIDENCE)
        for evidence in reviewed.values():
            self.assertIn(evidence["status"], review.APPROVED_STATUSES)
            self.assertTrue((ROOT / evidence["artifact"]).exists(), evidence["artifact"])

    def test_review_requires_release_gate_and_require_reached_command(self):
        payload = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
        commands = {item["id"]: item for item in payload["required_commands"]}

        self.assertEqual(set(commands), review.REQUIRED_COMMANDS)
        self.assertIn("python scripts/dev.py release-gate", commands["local_release_gates"]["command"])
        self.assertIn("--require-reached", commands["environment_baseline_require_reached"]["command"])

    def test_review_rejects_external_production_ready_claim(self):
        payload = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
        payload["production_ready"] = True

        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "review.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            report = review.validate_production_readiness_review(path)

        self.assertFalse(report["valid"])
        self.assertTrue(any("production_ready must remain false" in error for error in report["errors"]))

    def test_review_rejects_missing_evidence(self):
        payload = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
        payload["reviewed_evidence"] = [
            item for item in payload["reviewed_evidence"] if item["id"] != "incident_response"
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "review.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            report = review.validate_production_readiness_review(path)

        self.assertFalse(report["valid"])
        self.assertTrue(any("incident_response" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
