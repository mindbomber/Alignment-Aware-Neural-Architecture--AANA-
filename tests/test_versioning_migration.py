import importlib.util
import json
import pathlib
import tempfile
import unittest

from eval_pipeline import agent_contract, aix, audit, evidence_integrations, runtime, workflow_contract
from eval_pipeline.adapter_runner import verifier_modules


ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "examples" / "version_migration_policy.json"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


versioning = load_script("validate_versioning_migration", ROOT / "scripts" / "validation" / "validate_versioning_migration.py")


class VersioningMigrationTests(unittest.TestCase):
    def test_version_policy_matches_code_constants(self):
        report = versioning.validate_versioning_migration(POLICY_PATH)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["surface_count"], len(versioning.REQUIRED_SURFACES))

        payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        surfaces = payload["versioned_surfaces"]
        self.assertEqual(surfaces["workflow_contract_version"]["current"], workflow_contract.WORKFLOW_CONTRACT_VERSION)
        self.assertEqual(surfaces["agent_event_contract_version"]["current"], agent_contract.AGENT_EVENT_VERSION)
        self.assertEqual(surfaces["verifier_module_version"]["current"], verifier_modules.VERIFIER_MODULE_VERSION)
        self.assertEqual(surfaces["route_map_version"]["current"], verifier_modules.ROUTE_MAP_VERSION)
        self.assertEqual(surfaces["aix_tuning_version"]["current"], aix.AIX_VERSION)
        self.assertEqual(surfaces["evidence_connector_manifest_version"]["current"], evidence_integrations.CONNECTOR_CONTRACT_VERSION)
        self.assertEqual(surfaces["audit_schema_version"]["current"], audit.AUDIT_RECORD_VERSION)
        self.assertEqual(surfaces["runtime_version"]["current"], runtime.RUNTIME_API_VERSION)

    def test_all_adapter_files_have_versions(self):
        for path in sorted((ROOT / "examples").glob("*_adapter.json")):
            with self.subTest(path=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertRegex(payload.get("version", ""), versioning.SEMVERISH)

    def test_breaking_change_requires_migration_note_and_compatibility_test(self):
        payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        payload["migration_notes"].append(
            {
                "version": "0.2",
                "date": "2026-05-05",
                "breaking": True,
                "summary": "Break the runtime shape without a migration plan.",
                "compatibility_tests": [],
                "migration": ""
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "version-policy.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            report = versioning.validate_versioning_migration(path)

        self.assertFalse(report["valid"])
        self.assertTrue(any("breaking changes require migration text" in error for error in report["errors"]))
        self.assertTrue(any("breaking changes require compatibility_tests" in error for error in report["errors"]))

    def test_docs_name_every_versioned_surface(self):
        doc = (ROOT / "docs" / "versioning-migration.md").read_text(encoding="utf-8")

        for phrase in (
            "adapter version",
            "Workflow Contract version",
            "Agent Event Contract version",
            "verifier module version",
            "route map version",
            "AIx tuning version",
            "evidence connector manifest version",
            "audit schema version",
            "runtime version",
        ):
            self.assertIn(phrase, doc)


if __name__ == "__main__":
    unittest.main()
