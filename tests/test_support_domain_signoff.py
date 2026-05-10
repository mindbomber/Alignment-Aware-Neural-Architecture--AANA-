import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SIGNOFF_PATH = ROOT / "examples" / "support_domain_owner_signoff_template.json"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


signoff = load_script("validate_support_domain_signoff", ROOT / "scripts" / "validation" / "validate_support_domain_signoff.py")


class SupportDomainSignoffTests(unittest.TestCase):
    def test_signoff_template_covers_required_support_approval_areas(self):
        report = signoff.validate_support_domain_signoff(SIGNOFF_PATH)

        self.assertTrue(report["valid"], report)
        self.assertEqual(set(report["required_areas"]), signoff.REQUIRED_AREAS)
        self.assertEqual(report["area_count"], len(signoff.REQUIRED_AREAS))
        self.assertEqual(report["overall_status"], "approved")

    def test_signoff_template_keeps_production_claim_conservative(self):
        payload = json.loads(SIGNOFF_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["production_claim"], "not production-approved by this repository artifact")
        self.assertTrue(payload["approval_rules"]["require_all_areas_approved_before_enforced_support"])
        self.assertTrue(payload["approval_rules"]["require_live_evidence_before_production"])
        self.assertTrue(payload["approval_rules"]["allow_pending_for_demo_or_shadow"])

    def test_require_approved_passes_for_completed_signoff(self):
        report = signoff.validate_support_domain_signoff(SIGNOFF_PATH, require_approved=True)

        self.assertTrue(report["valid"], report)

    def test_completed_signoff_has_named_approvers(self):
        payload = json.loads(SIGNOFF_PATH.read_text(encoding="utf-8"))

        for approver in payload["required_approvers"]:
            self.assertNotEqual(approver["name"], "TBD")
            self.assertEqual(approver["approval_status"], "approved")
            self.assertTrue(approver["approval_uri"])
            self.assertTrue(approver["approved_at"])
        for area in payload["required_signoff_areas"]:
            self.assertEqual(area["approval_status"], "approved")

    def test_validator_rejects_missing_required_approval_area(self):
        payload = json.loads(SIGNOFF_PATH.read_text(encoding="utf-8"))
        payload["required_signoff_areas"] = [
            area for area in payload["required_signoff_areas"] if area["id"] != "audit_retention"
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "bad-signoff.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            report = signoff.validate_support_domain_signoff(path)

        self.assertFalse(report["valid"])
        self.assertTrue(any("audit_retention" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
