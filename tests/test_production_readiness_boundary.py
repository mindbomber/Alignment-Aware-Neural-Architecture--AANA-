import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BOUNDARY_PATH = ROOT / "examples" / "production_readiness_boundary.json"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


boundary = load_script("validate_production_readiness_boundary", ROOT / "scripts" / "validation" / "validate_production_readiness_boundary.py")


class ProductionReadinessBoundaryTests(unittest.TestCase):
    def test_boundary_manifest_declares_allowed_statuses_and_external_gates(self):
        report = boundary.validate_boundary(BOUNDARY_PATH)

        self.assertTrue(report["valid"], report)
        self.assertEqual(set(report["allowed_repo_statuses"]), boundary.REQUIRED_REPO_STATUSES)
        self.assertEqual(set(report["required_gates"]), boundary.REQUIRED_GATES)
        self.assertEqual(report["gate_count"], len(boundary.REQUIRED_GATES))

    def test_boundary_validator_rejects_missing_gate_and_local_certification_drift(self):
        payload = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
        payload["repo_local_positioning"] = "Local tests prove production safety."
        payload["production_readiness_requires"] = [
            gate for gate in payload["production_readiness_requires"] if gate["id"] != "measured_pilot_results"
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "boundary.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            report = boundary.validate_boundary(path)

        self.assertFalse(report["valid"])
        self.assertTrue(any("repo_local_positioning" in error for error in report["errors"]))
        self.assertTrue(any("measured_pilot_results" in error for error in report["errors"]))

    def test_boundary_doc_matches_manifest_positioning(self):
        doc = (ROOT / "docs" / "production-readiness-boundary.md").read_text(encoding="utf-8")

        self.assertIn("demo-ready, pilot-ready, or production-candidate", doc)
        self.assertIn("not production-certified by local tests alone", doc)
        for gate in (
            "live evidence connectors",
            "domain owner signoff",
            "audit retention",
            "observability",
            "human review path",
            "security review",
            "deployment manifest",
            "incident response plan",
            "measured pilot results",
        ):
            self.assertIn(gate, doc)


if __name__ == "__main__":
    unittest.main()
