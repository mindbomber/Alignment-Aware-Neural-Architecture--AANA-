import json
import pathlib
import tempfile
import unittest

from eval_pipeline import audit
from scripts import run_support_enforced_email_pilot


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SupportEnforcedEmailPilotTests(unittest.TestCase):
    def test_enforced_email_pilot_allows_only_email_guardrail_after_preflight(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            args = run_support_enforced_email_pilot.parse_args(
                [
                    "--audit-log",
                    str(temp_root / "audit" / "enforced-email.jsonl"),
                    "--metrics-output",
                    str(temp_root / "metrics.json"),
                    "--reviewer-report",
                    str(temp_root / "review.md"),
                    "--output",
                    str(temp_root / "results.json"),
                ]
            )

            result = run_support_enforced_email_pilot.run_enforced_email_pilot(args)

            self.assertEqual(result["measurement_status"], "accepted", result)
            self.assertEqual(result["execution_mode"], "enforce")
            self.assertEqual(result["enforcement"], "irreversible_email_send_blocking")
            self.assertEqual(result["enforced_adapters"], ["email_send_guardrail"])
            self.assertEqual(result["summary"]["covered_enforced_adapters"], ["email_send_guardrail"])
            self.assertEqual(result["metrics"]["preflight_failure_count"], 0)
            self.assertGreater(result["metrics"]["excluded_non_email_checks"], 0)
            self.assertGreater(result["metrics"]["enforced_email_checks"], 0)
            self.assertGreater(result["metrics"]["send_allowed_count"], 0)
            self.assertGreater(result["metrics"]["send_blocked_count"], 0)
            self.assertTrue(result["metrics"]["bridge_outage_blocks_sends"])
            self.assertTrue(result["bridge_outage_proof"]["proven"])
            self.assertEqual(result["bridge_outage_proof"]["recommended_action"], "refuse")
            self.assertEqual(result["bridge_outage_proof"]["production_effect"], "send_blocked")

            for observation in result["observations"]:
                self.assertTrue(observation["preflight"]["recipient_verification_present"])
                self.assertTrue(observation["preflight"]["attachment_metadata_dlp_present"])
                self.assertTrue(observation["preflight"]["irreversible_send_approval_path_present"])

            self.assertTrue((temp_root / "audit" / "enforced-email.jsonl").exists())
            self.assertTrue((temp_root / "metrics.json").exists())
            self.assertTrue((temp_root / "review.md").exists())
            self.assertTrue((temp_root / "results.json").exists())

            records = [
                json.loads(line)
                for line in (temp_root / "audit" / "enforced-email.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(records)
            self.assertEqual({record.get("adapter") or record.get("adapter_id") for record in records}, {"email_send_guardrail"})
            self.assertTrue(all(record["execution_mode"] == "enforce" for record in records))
            self.assertTrue(all(record["enforcement"]["mode"] == "irreversible_email_send_blocking" for record in records))
            self.assertTrue(all(record["enforcement"]["bridge_outage_proof"]["production_effect"] == "send_blocked" for record in records))
            self.assertFalse(audit.validate_audit_record(records[0])["errors"])

    def test_enforced_email_pilot_result_is_default_measured_artifact_shape(self):
        self.assertEqual(
            pathlib.Path(run_support_enforced_email_pilot.DEFAULT_OUTPUT),
            ROOT / "eval_outputs" / "pilots" / "support-enforced-email-internal-pilot-results.json",
        )
        self.assertEqual(
            pathlib.Path(run_support_enforced_email_pilot.DEFAULT_AUDIT_LOG),
            ROOT / "eval_outputs" / "audit" / "support-enforced-email-internal-pilot.jsonl",
        )


if __name__ == "__main__":
    unittest.main()
