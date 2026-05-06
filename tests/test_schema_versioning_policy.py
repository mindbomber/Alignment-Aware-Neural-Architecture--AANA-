import json
import unittest

from eval_pipeline.schema_versioning_policy import (
    ACTIVE_INTEROPERABILITY_SCHEMA_VERSION,
    BREAKING_CHANGE_RULES,
    COMPATIBILITY_MATRIX,
    MIGRATION_NOTES,
    SCHEMA_VERSIONING_POLICY_VERSION,
    check_schema_artifact_compatibility,
    schema_versioning_policy,
    schema_versioning_policy_markdown,
)
from scripts.validate_mi_contracts import ROOT


class SchemaVersioningPolicyTests(unittest.TestCase):
    def test_policy_declares_active_schema_and_migration_notes(self):
        policy = schema_versioning_policy()

        self.assertEqual(policy["schema_versioning_policy_version"], SCHEMA_VERSIONING_POLICY_VERSION)
        self.assertEqual(policy["active_interoperability_schema_version"], ACTIVE_INTEROPERABILITY_SCHEMA_VERSION)
        self.assertIn("0.1", policy["compatibility_matrix"])
        self.assertTrue(BREAKING_CHANGE_RULES)
        self.assertTrue(MIGRATION_NOTES["0.1"])

    def test_policy_markdown_documents_breaking_changes_and_compatibility(self):
        markdown = schema_versioning_policy_markdown()

        self.assertIn("Breaking Changes", markdown)
        self.assertIn("Compatibility Matrix", markdown)
        self.assertIn("Migration Notes", markdown)
        self.assertIn("scripts/validate_mi_contracts.py", markdown)

    def test_default_artifacts_are_policy_compatible(self):
        schema = json.loads((ROOT / "schemas" / "interoperability_contract.schema.json").read_text(encoding="utf-8"))
        pilot_handoffs = json.loads(
            (ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "pilot_handoffs.json").read_text(encoding="utf-8")
        )
        dashboard = json.loads(
            (ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_dashboard.json").read_text(encoding="utf-8")
        )
        readiness = json.loads(
            (ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "production_mi_readiness.json").read_text(
                encoding="utf-8"
            )
        )
        audit_records = [
            json.loads(line)
            for line in (ROOT / "eval_outputs" / "mi_pilot" / "research_citation" / "mi_audit.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]

        report = check_schema_artifact_compatibility(
            schema=schema,
            pilot_handoffs=pilot_handoffs,
            audit_records=audit_records,
            dashboard=dashboard,
            production_readiness=readiness,
        )

        self.assertTrue(report["compatible"], report["issues"])
        self.assertEqual(report["observed_versions"]["schema"], COMPATIBILITY_MATRIX["0.1"]["schema"]["contract_version"])

    def test_detects_pilot_version_drift(self):
        schema = {"properties": {"contract_version": {"const": "0.1"}}}
        pilot_handoffs = {"handoffs": [{"contract_version": "9.9"}]}

        report = check_schema_artifact_compatibility(schema=schema, pilot_handoffs=pilot_handoffs)

        self.assertFalse(report["compatible"])
        self.assertEqual(report["issues"][0]["artifact"], "pilot_handoffs")
        self.assertIn("not compatible", report["issues"][0]["message"])


if __name__ == "__main__":
    unittest.main()
