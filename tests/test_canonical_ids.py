import unittest

from aana import canonical_ids
from aana.adapters import FAMILY_IDS
from aana.bundles import BUNDLE_ALIASES, BUNDLE_IDS, aliases_for_bundle, canonicalize_bundle_id
from eval_pipeline import agent_contract


class CanonicalIDTests(unittest.TestCase):
    def test_canonical_registry_validates_current_platform(self):
        report = canonical_ids.validate_canonical_ids()

        self.assertTrue(report["valid"], report)
        self.assertEqual(tuple(FAMILY_IDS), canonical_ids.ADAPTER_FAMILY_IDS)
        self.assertEqual(tuple(BUNDLE_IDS), canonical_ids.BUNDLE_IDS)
        self.assertEqual(tuple(agent_contract.ALLOWED_ACTIONS), canonical_ids.ACTION_ROUTES)

    def test_alias_maps_are_backward_compatibility_only(self):
        for canonical_id in canonical_ids.BUNDLE_IDS:
            self.assertNotIn(canonical_id, BUNDLE_ALIASES)
            self.assertEqual(canonicalize_bundle_id(canonical_id), canonical_id)

        self.assertEqual(canonicalize_bundle_id("civic_government"), "government_civic")
        self.assertEqual(aliases_for_bundle("government_civic"), ["civic_government"])

    def test_alias_drift_is_reported(self):
        issues = []
        canonical_ids._validate_surface(
            issues,
            surface="demo",
            canonical_ids=("canonical",),
            aliases={"canonical": "canonical", "legacy": "missing"},
        )
        codes = {issue["code"] for issue in issues}

        self.assertIn("identity_alias_not_allowed", codes)
        self.assertIn("alias_redefines_canonical_id", codes)
        self.assertIn("alias_targets_unknown_canonical_id", codes)

    def test_route_and_evidence_aliases_resolve_to_canonical_ids(self):
        self.assertEqual(canonical_ids.canonicalize_route("route_to_review"), "defer")
        self.assertEqual(canonical_ids.canonicalize_route("accept"), "accept")
        self.assertEqual(canonical_ids.canonicalize_tool_evidence_type("approval_state"), "approval")
        self.assertEqual(canonical_ids.canonicalize_runtime_mode("observe_only"), "shadow")


if __name__ == "__main__":
    unittest.main()
