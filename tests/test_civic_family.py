import unittest
from contextlib import redirect_stdout
from io import StringIO

from eval_pipeline import civic_family
from scripts import aana_cli, run_starter_pilot_kit


class CivicFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with redirect_stdout(StringIO()):
            code = run_starter_pilot_kit.main(["--kit", "civic_government"])
        if code != 0:
            raise AssertionError("government/civic starter pilot kit failed")

    def test_civic_certification_report_passes_phase_four_surfaces(self):
        report = civic_family.civic_certification_report()

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["summary"]["readiness_level"], "civic_phase4_ready")
        self.assertEqual(report["summary"]["score_percent"], 100.0)
        self.assertEqual(set(report["core_adapters"]), set(civic_family.CIVIC_CORE_ADAPTERS))
        surface_ids = {surface["surface_id"] for surface in report["surfaces"]}
        self.assertEqual(
            surface_ids,
            {
                "civic_core_pack",
                "civic_evidence_connectors",
                "civic_agent_skills",
                "civic_pilot_surface",
                "civic_certification",
            },
        )

    def test_civic_connectors_include_source_law_redaction_and_case_history(self):
        report = civic_family.civic_connector_report()

        self.assertTrue(report["ready"], report)
        connector_gate = next(check for check in report["checks"] if check["id"] == "connector_contracts")
        required = connector_gate["details"]["required"]
        self.assertEqual(required["public_law_policy_sources"], "public_law_policy_sources")
        self.assertEqual(required["redaction_classification_registry"], "redaction_classification_registry")
        self.assertEqual(required["case_ticket_history"], "civic_case_history")

    def test_civic_skills_cover_required_skill_family(self):
        report = civic_family.civic_agent_skills_report()

        self.assertTrue(report["ready"], report)
        self.assertIn("benefits_eligibility_boundary", civic_family.CIVIC_AGENT_SKILLS)
        self.assertIn("public_records_privacy", civic_family.CIVIC_AGENT_SKILLS)
        self.assertIn("public_statement_risk", civic_family.CIVIC_AGENT_SKILLS)

    def test_cli_civic_certify_json_reports_score(self):
        with redirect_stdout(StringIO()):
            code = aana_cli.main(["civic-certify", "--json"])

        self.assertEqual(code, 0)

    def test_cli_contract_lists_civic_certify(self):
        commands = {item["command"] for item in aana_cli.cli_command_matrix()}

        self.assertIn("civic-certify", commands)


if __name__ == "__main__":
    unittest.main()
