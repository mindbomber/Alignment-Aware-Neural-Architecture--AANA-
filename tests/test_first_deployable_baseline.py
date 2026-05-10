import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "examples" / "first_deployable_support_baseline.json"
INTERNAL_PILOT_BASELINE_PATH = ROOT / "examples" / "first_deployable_support_baseline.internal_pilot.json"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


baseline = load_script("validate_first_deployable_baseline", ROOT / "scripts" / "validation" / "validate_first_deployable_baseline.py")


class FirstDeployableBaselineTests(unittest.TestCase):
    def test_baseline_manifest_covers_required_criteria(self):
        report = baseline.validate_first_deployable_baseline(BASELINE_PATH)

        self.assertTrue(report["valid"], report)
        self.assertEqual(set(report["required_criteria"]), baseline.REQUIRED_CRITERIA)
        self.assertEqual(report["criteria_count"], len(baseline.REQUIRED_CRITERIA))
        self.assertEqual(report["current_status"], "not_reached_external_evidence_required")
        self.assertFalse(report["baseline_reached"])

    def test_baseline_requires_external_signoff_and_measured_pilot_results(self):
        payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        criteria = {item["id"]: item for item in payload["required_criteria"]}

        self.assertEqual(criteria["support_domain_owner_signoff"]["status"], "pending_external_approval")
        self.assertEqual(criteria["internal_pilot_metrics"]["status"], "pending_measured_pilot_results")
        self.assertIn("approved support domain owner signoff artifact", payload["baseline_reached_policy"]["external_evidence_required"])
        self.assertIn(
            "measured internal pilot metrics report with over-acceptance, over-refusal, latency, and correction metrics",
            payload["baseline_reached_policy"]["external_evidence_required"],
        )

    def test_require_reached_fails_for_repo_local_baseline(self):
        report = baseline.validate_first_deployable_baseline(BASELINE_PATH, require_reached=True)

        self.assertFalse(report["valid"])
        self.assertTrue(any("external signoff and measured pilot results" in error for error in report["errors"]))

    def test_internal_pilot_baseline_passes_require_reached(self):
        report = baseline.validate_first_deployable_baseline(
            INTERNAL_PILOT_BASELINE_PATH,
            require_reached=True,
        )

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["baseline_reached"], report)
        self.assertEqual(report["current_status"], "reached")

    def test_internal_pilot_baseline_attaches_required_artifacts(self):
        payload = json.loads(INTERNAL_PILOT_BASELINE_PATH.read_text(encoding="utf-8"))
        attachments = payload["attached_artifacts"]

        self.assertEqual(set(attachments), baseline.REQUIRED_ATTACHMENTS)
        for reference in attachments.values():
            self.assertTrue((ROOT / reference).exists(), reference)

    def test_reached_baseline_rejects_pending_connector_manifest(self):
        payload = json.loads(INTERNAL_PILOT_BASELINE_PATH.read_text(encoding="utf-8"))
        connectors = json.loads((ROOT / payload["attached_artifacts"]["connector_manifests"]).read_text(encoding="utf-8"))
        connectors["connector_manifests"][0]["approval_status"] = "pending"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            connector_path = temp_path / "connectors.json"
            baseline_path = temp_path / "baseline.json"
            connector_path.write_text(json.dumps(connectors), encoding="utf-8")
            payload["attached_artifacts"]["connector_manifests"] = str(connector_path)
            baseline_path.write_text(json.dumps(payload), encoding="utf-8")
            report = baseline.validate_first_deployable_baseline(baseline_path, require_reached=True)

        self.assertFalse(report["valid"])
        self.assertTrue(any("approval_status must be live_approved" in error for error in report["errors"]))

    def test_validator_rejects_reached_without_all_criteria_reached(self):
        payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        payload["current_status"] = "reached"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "baseline.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            report = baseline.validate_first_deployable_baseline(path)

        self.assertFalse(report["valid"])
        self.assertTrue(any("current_status cannot be reached" in error for error in report["errors"]))

    def test_docs_state_reached_criteria(self):
        doc = (ROOT / "docs" / "first-deployable-support-baseline.md").read_text(encoding="utf-8")

        for phrase in (
            "support adapters run through Workflow Contract and Agent Event Contract paths",
            "runtime routing is registry-driven",
            "live or approved support evidence connectors exist",
            "audit-safe records are emitted",
            "human review paths are wired",
            "golden outputs pass",
            "gallery validation passes",
            "release gate passes",
            "security/privacy review is complete",
            "support domain owner signs off",
            "internal pilot shows acceptable over-acceptance, over-refusal, latency, and correction metrics",
        ):
            self.assertIn(phrase, doc)


if __name__ == "__main__":
    unittest.main()
