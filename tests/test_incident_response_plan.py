import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "examples" / "incident_response_plan_internal_pilot.json"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


incident_plan = load_script("validate_incident_response_plan", ROOT / "scripts" / "validation" / "validate_incident_response_plan.py")


class IncidentResponsePlanTests(unittest.TestCase):
    def test_incident_response_plan_validates(self):
        report = incident_plan.validate_plan(PLAN_PATH)

        self.assertTrue(report["valid"], report)
        self.assertEqual(set(report["required_severities"]), {"sev0", "sev1", "sev2", "sev3"})
        self.assertEqual(report["severity_count"], 4)
        self.assertGreaterEqual(report["rollback_trigger_count"], 5)
        self.assertGreaterEqual(report["notification_path_count"], 4)

    def test_plan_defines_required_operational_paths(self):
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))

        sev0 = next(item for item in plan["severity_levels"] if item["id"] == "sev0")
        self.assertTrue(sev0["rollback_required"])
        self.assertTrue(sev0["customer_impact_review_required"])
        self.assertTrue(sev0["audit_review_required"])

        trigger_ids = {trigger["id"] for trigger in plan["rollback_triggers"]}
        self.assertIn("critical_false_accept", trigger_ids)
        self.assertIn("audit_leakage", trigger_ids)
        self.assertIn("bridge_unavailable_irreversible_actions", trigger_ids)

        audit = plan["audit_review_procedure"]
        self.assertIn("python scripts/aana_cli.py audit-validate", " ".join(audit["commands"]))
        self.assertIn("raw customer", audit["raw_data_policy"].lower())
        self.assertIn("tokens", audit["raw_data_policy"].lower())

        customer = plan["customer_impact_review"]
        self.assertGreaterEqual({"sev0", "sev1", "sev2"}, set(customer["required_for_severities"]))
        self.assertTrue(customer["review_questions"])
        self.assertTrue(customer["remediation_paths"])

    def test_plan_rejects_missing_rollback_trigger_and_notification_coverage(self):
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        plan["rollback_triggers"] = [trigger for trigger in plan["rollback_triggers"] if trigger["id"] != "audit_leakage"]
        for path in plan["notification_paths"]:
            path["severities"] = [severity for severity in path["severities"] if severity != "sev0"]

        temp = PLAN_PATH.parent / "_tmp_bad_incident_plan.json"
        try:
            temp.write_text(json.dumps(plan), encoding="utf-8")
            report = incident_plan.validate_plan(temp)
        finally:
            temp.unlink(missing_ok=True)

        self.assertFalse(report["valid"])
        joined = " ".join(report["errors"])
        self.assertIn("audit_leakage", joined)
        self.assertIn("sev0", joined)


if __name__ == "__main__":
    unittest.main()
