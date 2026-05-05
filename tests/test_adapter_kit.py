import importlib.util
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


new_adapter = load_script("new_adapter", ROOT / "scripts" / "new_adapter.py")
validate_adapter = load_script("validate_adapter", ROOT / "scripts" / "validate_adapter.py")


class AdapterKitTests(unittest.TestCase):
    def test_scaffold_creates_valid_adapter_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = new_adapter.scaffold("Meal Planning", tmp)
            adapter_path = pathlib.Path(created["adapter"])

            self.assertTrue(adapter_path.exists())
            self.assertTrue(pathlib.Path(created["prompt"]).exists())
            self.assertTrue(pathlib.Path(created["bad_candidate"]).exists())
            self.assertTrue(pathlib.Path(created["readme"]).exists())

            adapter = validate_adapter.load_adapter(adapter_path)
            report = validate_adapter.validate_adapter(adapter)

            self.assertTrue(report["valid"], report)
            self.assertGreaterEqual(report["warnings"], 1)
            self.assertEqual(adapter["adapter_name"], "meal_planning_aana_adapter")
            self.assertEqual(adapter["domain"]["name"], "meal_planning")

    def test_travel_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "travel_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_meal_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "meal_planning_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_support_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "support_reply_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_crm_support_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "crm_support_reply_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_email_send_guardrail_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "email_send_guardrail_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_file_operation_guardrail_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "file_operation_guardrail_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_code_change_review_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "code_change_review_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_incident_response_update_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "incident_response_update_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_security_vulnerability_disclosure_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "security_vulnerability_disclosure_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_access_permission_change_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "access_permission_change_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_database_migration_guardrail_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "database_migration_guardrail_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_experiment_ab_test_launch_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "experiment_ab_test_launch_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_product_requirements_checker_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "product_requirements_checker_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_procurement_vendor_risk_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "procurement_vendor_risk_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_hiring_candidate_feedback_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "hiring_candidate_feedback_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_performance_review_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "performance_review_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_learning_tutor_answer_checker_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "learning_tutor_answer_checker_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_api_contract_change_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "api_contract_change_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_infrastructure_change_guardrail_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "infrastructure_change_guardrail_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_data_pipeline_change_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "data_pipeline_change_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_model_evaluation_release_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "model_evaluation_release_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_feature_flag_rollout_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "feature_flag_rollout_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_sales_proposal_checker_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "sales_proposal_checker_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_customer_success_renewal_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "customer_success_renewal_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_invoice_billing_reply_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "invoice_billing_reply_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_insurance_claim_triage_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "insurance_claim_triage_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_grant_application_review_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "grant_application_review_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_deployment_readiness_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "deployment_readiness_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_legal_safety_router_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "legal_safety_router_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_medical_safety_router_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "medical_safety_router_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_financial_advice_router_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "financial_advice_router_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_booking_purchase_guardrail_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "booking_purchase_guardrail_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_calendar_scheduling_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "calendar_scheduling_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_data_export_guardrail_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "data_export_guardrail_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_publication_check_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "publication_check_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_meeting_summary_checker_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "meeting_summary_checker_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_ticket_update_checker_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "ticket_update_checker_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_research_answer_grounding_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "research_answer_grounding_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_research_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "research_summary_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_template_reports_placeholders(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "domain_adapter_template.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertFalse(report["valid"])
        self.assertGreater(report["errors"], 0)
        self.assertTrue(any(issue["level"] == "warning" for issue in report["issues"]))

    def test_duplicate_constraint_ids_fail_validation(self):
        adapter = new_adapter.build_adapter("support triage")
        adapter["constraints"][1]["id"] = adapter["constraints"][0]["id"]

        report = validate_adapter.validate_adapter(adapter)

        self.assertFalse(report["valid"])
        self.assertTrue(
            any("Duplicate constraint id" in issue["message"] for issue in report["issues"])
        )

    def test_missing_production_readiness_reports_warning(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "travel_adapter.json")
        adapter.pop("production_readiness", None)

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertTrue(any(issue["path"] == "production_readiness" for issue in report["issues"]))

    def test_malformed_production_readiness_fails_validation(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "travel_adapter.json")
        adapter["production_readiness"] = "production"

        report = validate_adapter.validate_adapter(adapter)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "production_readiness" for issue in report["issues"]))

    def test_incomplete_production_readiness_reports_missing_fixture_coverage(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "travel_adapter.json")
        adapter["production_readiness"].pop("fixture_coverage")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertTrue(any(issue["path"] == "production_readiness.fixture_coverage" for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
