import json
import pathlib
import tempfile
import unittest

from eval_pipeline import audit
from scripts import run_support_enforced_draft_pilot


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SupportEnforcedDraftPilotTests(unittest.TestCase):
    def test_enforced_draft_pilot_blocks_only_allowlisted_support_drafts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = pathlib.Path(temp_dir)
            args = run_support_enforced_draft_pilot.parse_args(
                [
                    "--audit-log",
                    str(temp_root / "audit" / "enforced.jsonl"),
                    "--metrics-output",
                    str(temp_root / "metrics.json"),
                    "--reviewer-report",
                    str(temp_root / "review.md"),
                    "--output",
                    str(temp_root / "results.json"),
                ]
            )

            result = run_support_enforced_draft_pilot.run_enforced_draft_pilot(args)

            self.assertEqual(result["measurement_status"], "accepted", result)
            self.assertEqual(result["execution_mode"], "enforce")
            self.assertEqual(result["enforcement"], "narrow_support_draft_blocking")
            self.assertEqual(
                set(result["enforced_adapters"]),
                {"support_reply", "crm_support_reply", "ticket_update_checker"},
            )
            self.assertEqual(result["excluded_from_enforcement"], ["email_send_guardrail"])
            self.assertEqual(result["metrics"]["prohibited_email_enforcement_count"], 0)
            self.assertGreater(result["metrics"]["excluded_email_send_checks"], 0)
            self.assertGreater(result["metrics"]["original_candidate_blocked_count"], 0)
            self.assertGreater(result["metrics"]["candidate_allowed_count"], 0)
            self.assertEqual(
                set(result["summary"]["covered_enforced_adapters"]),
                {"support_reply", "crm_support_reply", "ticket_update_checker"},
            )
            self.assertTrue((temp_root / "audit" / "enforced.jsonl").exists())
            self.assertTrue((temp_root / "metrics.json").exists())
            self.assertTrue((temp_root / "review.md").exists())
            self.assertTrue((temp_root / "results.json").exists())

            records = [
                json.loads(line)
                for line in (temp_root / "audit" / "enforced.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(records)
            self.assertNotIn("email_send_guardrail", {record.get("adapter") or record.get("adapter_id") for record in records})
            self.assertTrue(all(record["execution_mode"] == "enforce" for record in records))
            self.assertTrue(all(record["enforcement"]["mode"] == "narrow_support_draft_blocking" for record in records))
            self.assertFalse(audit.validate_audit_record(records[0])["errors"])

    def test_enforced_draft_pilot_result_is_default_measured_artifact_shape(self):
        self.assertEqual(
            pathlib.Path(run_support_enforced_draft_pilot.DEFAULT_OUTPUT),
            ROOT / "eval_outputs" / "pilots" / "support-enforced-draft-internal-pilot-results.json",
        )
        self.assertEqual(
            pathlib.Path(run_support_enforced_draft_pilot.DEFAULT_AUDIT_LOG),
            ROOT / "eval_outputs" / "audit" / "support-enforced-draft-internal-pilot.jsonl",
        )


if __name__ == "__main__":
    unittest.main()
