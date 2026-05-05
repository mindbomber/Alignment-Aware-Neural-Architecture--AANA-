import unittest
from contextlib import redirect_stdout
from io import StringIO

from eval_pipeline import enterprise_family
from scripts import aana_cli, run_starter_pilot_kit


class EnterpriseFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with redirect_stdout(StringIO()):
            code = run_starter_pilot_kit.main(["--kit", "enterprise"])
        if code != 0:
            raise AssertionError("enterprise starter pilot kit failed")

    def test_enterprise_certification_report_passes_phase_two_surfaces(self):
        report = enterprise_family.enterprise_certification_report()

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["summary"]["readiness_level"], "enterprise_phase2_ready")
        self.assertEqual(report["summary"]["score_percent"], 100.0)
        self.assertEqual(set(report["core_adapters"]), set(enterprise_family.ENTERPRISE_CORE_ADAPTERS))
        surface_ids = {surface["surface_id"] for surface in report["surfaces"]}
        self.assertEqual(
            surface_ids,
            {
                "enterprise_core_pack",
                "enterprise_evidence_connectors",
                "enterprise_agent_skills",
                "enterprise_pilot_surface",
                "enterprise_certification",
            },
        )

    def test_enterprise_connectors_include_ticketing_and_data_export(self):
        report = enterprise_family.enterprise_connector_report()

        self.assertTrue(report["ready"], report)
        connector_gate = next(check for check in report["checks"] if check["id"] == "connector_contracts")
        required = connector_gate["details"]["required"]
        self.assertEqual(required["ticketing"], "ticketing")
        self.assertEqual(required["data_warehouse_export"], "data_export")

    def test_enterprise_skills_cover_required_skill_family(self):
        report = enterprise_family.enterprise_agent_skills_report()

        self.assertTrue(report["ready"], report)
        self.assertIn("access_change_approval", enterprise_family.ENTERPRISE_AGENT_SKILLS)
        self.assertIn("incident_communications", enterprise_family.ENTERPRISE_AGENT_SKILLS)

    def test_cli_enterprise_certify_json_reports_score(self):
        with redirect_stdout(StringIO()):
            code = aana_cli.main(["enterprise-certify", "--json"])

        self.assertEqual(code, 0)

    def test_cli_contract_lists_enterprise_certify(self):
        commands = {item["command"] for item in aana_cli.cli_command_matrix()}

        self.assertIn("enterprise-certify", commands)


if __name__ == "__main__":
    unittest.main()
