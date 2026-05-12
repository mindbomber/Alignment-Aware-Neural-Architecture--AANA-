import copy
import pathlib
import tempfile
import unittest

import aana
from eval_pipeline import medperf_aix
from scripts import aana_cli


class MedPerfAixProfileTests(unittest.TestCase):
    def test_default_profile_validates_as_strict_healthcare_ready_not_go_live(self):
        profile = medperf_aix.default_medperf_aix_profile()
        report = medperf_aix.validate_medperf_aix_profile(profile)

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["healthcare_evaluation_ready"])
        self.assertFalse(report["go_live_ready"])
        self.assertEqual(report["risk_tier"], "strict")
        self.assertEqual(report["hard_blockers"], [])
        self.assertIn("not production certification", profile["claim_boundary"].lower())
        self.assertIn("clinical deployment", profile["claim_boundary"].lower())

    def test_missing_site_approval_is_hard_blocker(self):
        profile = copy.deepcopy(medperf_aix.default_medperf_aix_profile())
        profile["evaluation_context"]["site_approval"]["approval_status"] = "missing"

        report = medperf_aix.validate_medperf_aix_profile(profile)

        self.assertFalse(report["valid"])
        self.assertFalse(report["healthcare_evaluation_ready"])
        self.assertIn("missing_site_approval", report["hard_blockers"])

    def test_missing_privacy_boundary_is_hard_blocker(self):
        profile = copy.deepcopy(medperf_aix.default_medperf_aix_profile())
        profile["evaluation_context"]["privacy_controls"]["privacy_boundary"] = ""

        report = medperf_aix.validate_medperf_aix_profile(profile)

        self.assertFalse(report["valid"])
        self.assertIn("missing_privacy_boundary", report["hard_blockers"])

    def test_unsupported_medical_claim_is_hard_blocker(self):
        profile = copy.deepcopy(medperf_aix.default_medperf_aix_profile())
        profile["evaluation_context"]["clinical_task"]["unsupported_medical_claims_detected"] = True

        report = medperf_aix.validate_medperf_aix_profile(profile)

        self.assertFalse(report["valid"])
        self.assertIn("unsupported_medical_claim", report["hard_blockers"])

    def test_missing_clinical_owner_signoff_is_hard_blocker(self):
        profile = copy.deepcopy(medperf_aix.default_medperf_aix_profile())
        profile["evaluation_context"]["clinical_owner_signoff"]["status"] = "pending"

        report = medperf_aix.validate_medperf_aix_profile(profile)

        self.assertFalse(report["valid"])
        self.assertIn("missing_clinical_owner_signoff", report["hard_blockers"])

    def test_report_section_contains_healthcare_fields(self):
        profile = medperf_aix.default_medperf_aix_profile()
        validation = medperf_aix.validate_medperf_aix_profile(profile)

        section = medperf_aix.build_medperf_aix_report_section(profile, validation)

        self.assertEqual(section["section_type"], "aana_medperf_healthcare_aix_section")
        self.assertEqual(section["mlcommons_surface"], "medperf")
        self.assertEqual(section["risk_tier"], "strict")
        self.assertEqual(section["site"]["site_id"], "synthetic-hospital-site")
        self.assertEqual(section["dataset"]["dataset_id"], "synthetic-radiology-demo")
        self.assertFalse(section["privacy_controls"]["raw_records_in_audit_allowed"])
        self.assertEqual(section["clinical_owner_signoff"]["status"], "approved")

    def test_write_report_section_and_cli(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = pathlib.Path(temp_dir) / "medperf-profile.json"
            report_path = pathlib.Path(temp_dir) / "medperf-report-section.json"

            write = medperf_aix.write_medperf_aix_profile(profile_path)
            code = aana_cli.main(
                [
                    "medperf-aix-profile",
                    "--profile",
                    str(profile_path),
                    "--report",
                    str(report_path),
                ]
            )

            self.assertTrue(write["validation"]["valid"], write["validation"])
            self.assertEqual(code, 0)
            self.assertTrue(report_path.exists())

    def test_public_exports_include_medperf_helpers(self):
        profile = aana.default_medperf_aix_profile()

        self.assertEqual(aana.MEDPERF_AIX_PROFILE_VERSION, "0.1")
        self.assertEqual(aana.MEDPERF_AIX_PROFILE_TYPE, "aana_medperf_aix_profile")
        self.assertIn("site", aana.REQUIRED_HEALTHCARE_CONTEXT_FIELDS)
        self.assertTrue(aana.validate_medperf_aix_profile(profile)["valid"])


if __name__ == "__main__":
    unittest.main()
