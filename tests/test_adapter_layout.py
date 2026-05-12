import unittest

from aana.adapter_layout import validate_adapter_layout
from aana.adapters import FAMILY_IDS, load_adapter_families
from aana.bundles import BUNDLE_IDS, aliases_for_bundle, canonicalize_bundle_id, load_bundle, load_bundles


class AdapterLayoutTests(unittest.TestCase):
    def test_adapter_families_match_public_layout(self):
        families = load_adapter_families()
        self.assertEqual(set(families), set(FAMILY_IDS))
        self.assertEqual(
            set(FAMILY_IDS),
            {
                "privacy_pii",
                "grounded_qa",
                "agent_tool_use",
                "governance_compliance",
                "security_devops",
                "domain_risk",
            },
        )
        for family in families.values():
            self.assertEqual(family["family_type"], "technical_adapter")
            self.assertTrue(family["primary_metrics"])
            self.assertIn("claim_boundary", family)

    def test_product_bundles_reference_existing_adapter_families(self):
        families = load_adapter_families()
        bundles = load_bundles()
        self.assertEqual(set(bundles), set(BUNDLE_IDS))
        self.assertEqual(set(BUNDLE_IDS), {"enterprise", "enterprise_ops_pilot", "personal_productivity", "government_civic"})
        for bundle in bundles.values():
            self.assertEqual(bundle["bundle_type"], "product_bundle")
            self.assertEqual(bundle["bundle_id"], bundle["canonical_id"])
            self.assertTrue(set(bundle["adapter_families"]).issubset(families))
            self.assertIn("Never tune and claim on the same", bundle["required_split_rule"])
            self.assertTrue(bundle["core_adapter_ids"])
            self.assertTrue(bundle["required_evidence_connectors"])
            self.assertTrue(bundle["human_review_required_for"])
            self.assertEqual(
                set(bundle["minimum_validation"]["required_adapter_families"]),
                set(bundle["adapter_families"]),
            )
            covered = {
                item["adapter_family"]
                for item in bundle["minimum_validation"]["heldout_validation_coverage"]
            }
            self.assertEqual(covered, set(bundle["adapter_families"]))

    def test_civic_government_alias_resolves_to_government_civic(self):
        self.assertEqual(canonicalize_bundle_id("civic_government"), "government_civic")
        self.assertEqual(canonicalize_bundle_id("government_civic"), "government_civic")
        self.assertEqual(load_bundle("civic_government"), load_bundle("government_civic"))
        self.assertEqual(aliases_for_bundle("government_civic"), ["civic_government"])

    def test_split_isolation_is_enforced(self):
        report = validate_adapter_layout()
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["bundle_aliases"]["civic_government"], "government_civic")
        issue_codes = {issue["code"] for issue in report["issues"]}
        self.assertNotIn("same_split_for_tuning_and_public_claims", issue_codes)
        self.assertNotIn("same_split_for_tuning_and_heldout_validation", issue_codes)
        self.assertNotIn("bundle_missing_required_field", issue_codes)
        self.assertNotIn("bundle_missing_family_heldout_coverage", issue_codes)


if __name__ == "__main__":
    unittest.main()
