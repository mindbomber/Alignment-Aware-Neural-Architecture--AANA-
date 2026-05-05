import unittest
from contextlib import redirect_stdout
from io import StringIO

from eval_pipeline import personal_family
from scripts import aana_cli, run_starter_pilot_kit


class PersonalFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with redirect_stdout(StringIO()):
            code = run_starter_pilot_kit.main(["--kit", "personal_productivity"])
        if code != 0:
            raise AssertionError("personal productivity starter pilot kit failed")

    def test_personal_certification_report_passes_phase_three_surfaces(self):
        report = personal_family.personal_certification_report()

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["summary"]["readiness_level"], "personal_phase3_ready")
        self.assertEqual(report["summary"]["score_percent"], 100.0)
        self.assertEqual(set(report["core_adapters"]), set(personal_family.PERSONAL_CORE_ADAPTERS))
        surface_ids = {surface["surface_id"] for surface in report["surfaces"]}
        self.assertEqual(
            surface_ids,
            {
                "personal_core_pack",
                "personal_evidence_connectors",
                "personal_agent_skills",
                "personal_demo_app",
                "personal_certification",
            },
        )

    def test_personal_connectors_include_browser_registry_and_approval(self):
        report = personal_family.personal_connector_report()

        self.assertTrue(report["ready"], report)
        connector_gate = next(check for check in report["checks"] if check["id"] == "connector_contracts")
        required = connector_gate["details"]["required"]
        self.assertEqual(required["browser_cart_quote"], "browser_cart_quote")
        self.assertEqual(required["citation_source_registry"], "citation_source_registry")
        self.assertEqual(required["local_approval_state"], "local_approval")

    def test_personal_demo_surface_covers_all_core_adapters(self):
        report = personal_family.personal_demo_surface_report()

        self.assertTrue(report["ready"], report)
        demo_gate = next(check for check in report["checks"] if check["id"] == "core_demo_scenarios")
        self.assertEqual(demo_gate["details"]["demo_count"], len(personal_family.PERSONAL_CORE_ADAPTERS))

    def test_cli_personal_certify_json_reports_score(self):
        with redirect_stdout(StringIO()):
            code = aana_cli.main(["personal-certify", "--json"])

        self.assertEqual(code, 0)

    def test_cli_contract_lists_personal_certify(self):
        commands = {item["command"] for item in aana_cli.cli_command_matrix()}

        self.assertIn("personal-certify", commands)


if __name__ == "__main__":
    unittest.main()
