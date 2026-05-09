import unittest

from eval_pipeline.bundle_certification import certify_bundle_report, certification_target_choices, certification_targets
from scripts import aana_cli


class BundleCertificationTests(unittest.TestCase):
    def test_bundle_certification_targets_are_public_bundles(self):
        self.assertEqual(set(certification_targets()), {"enterprise", "personal_productivity", "government_civic"})
        self.assertIn("civic_government", certification_target_choices())

    def test_enterprise_bundle_certification_reports_required_manifest_fields(self):
        report = certify_bundle_report("enterprise")

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["bundle_id"], "enterprise")
        self.assertTrue(report["manifest"]["core_adapter_ids"])
        self.assertTrue(report["manifest"]["required_evidence_connectors"])
        self.assertTrue(report["manifest"]["human_review_required_for"])
        self.assertTrue(report["manifest"]["minimum_validation"])
        self.assertEqual(report["surfaces"][0]["surface_id"], "enterprise_manifest")

    def test_cli_certify_bundle_json_reports_bundle(self):
        code = aana_cli.main(["certify-bundle", "personal_productivity", "--json"])

        self.assertEqual(code, 0)

    def test_cli_certify_bundle_accepts_backward_compatible_alias(self):
        code = aana_cli.main(["certify-bundle", "civic_government", "--json"])

        self.assertEqual(code, 0)

    def test_cli_contract_lists_certify_bundle(self):
        commands = {item["command"] for item in aana_cli.cli_command_matrix()}

        self.assertIn("certify-bundle", commands)


if __name__ == "__main__":
    unittest.main()
