import json
import pathlib
import tempfile
import unittest

import aana
from eval_pipeline import agent_api, runtime_human_review
from scripts import aana_cli


def review_required_record():
    event = agent_api.load_json_file("examples/agent_event_support_reply.json")
    result = agent_api.check_event(event)
    result["recommended_action"] = "defer"
    result["gate_decision"] = "fail"
    result["candidate_gate"] = "fail"
    result.setdefault("aix", {})["decision"] = "defer"
    result["aix"]["hard_blockers"] = ["missing_policy_evidence"]
    result.setdefault("violations", []).append({"code": "recommended_action_not_allowed", "severity": "high"})
    return agent_api.audit_event_check(event, result, created_at="2026-05-05T00:00:00Z")


class RuntimeHumanReviewExportTests(unittest.TestCase):
    def test_config_validates_redacted_review_export_defaults(self):
        config = runtime_human_review.human_review_export_config()
        report = runtime_human_review.validate_human_review_export_config(config)

        self.assertTrue(report["valid"], report)
        self.assertEqual(config["export_type"], "aana_runtime_human_review_export")
        self.assertFalse(config["redaction"]["raw_prompt_logged"])
        self.assertIn("not production certification", config["claim_boundary"].lower())

    def test_runtime_review_packet_contains_decisions_not_raw_content(self):
        record = review_required_record()
        packet = runtime_human_review.runtime_human_review_packet(record, created_at="2026-05-05T00:01:00Z")
        validation = runtime_human_review.validate_runtime_human_review_packet(packet)
        serialized = json.dumps(packet, sort_keys=True)

        self.assertTrue(validation["valid"], validation)
        self.assertEqual(packet["packet_type"], "aana_runtime_human_review_packet")
        self.assertEqual(packet["review_queue"]["queue"], "support_human_review")
        self.assertEqual(packet["status"], "open")
        self.assertEqual(packet["decision_context"]["recommended_action"], "defer")
        self.assertIn("missing_policy_evidence", packet["decision_context"]["aix"]["hard_blockers"])
        self.assertIn("source_record_sha256", packet["source"])
        self.assertNotIn("Hi Maya", serialized)
        self.assertNotIn("Refund eligibility", serialized)
        self.assertNotIn("candidate_action", serialized)

    def test_export_runtime_review_queue_writes_jsonl_and_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            queue = pathlib.Path(temp_dir) / "review-queue.jsonl"
            summary = pathlib.Path(temp_dir) / "review-summary.json"
            agent_api.append_audit_record(audit_log, review_required_record())

            result = runtime_human_review.export_runtime_human_review_queue(
                audit_log,
                queue_path=queue,
                summary_path=summary,
                created_at="2026-05-05T00:01:00Z",
            )

            packets = runtime_human_review.load_runtime_human_review_queue(queue)
            summary_payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertTrue(result["valid"], result)
            self.assertEqual(result["packet_count"], 1)
            self.assertEqual(len(packets), 1)
            self.assertEqual(summary_payload["packet_count"], 1)
            self.assertEqual(summary_payload["by_recommended_action"]["defer"], 1)
            self.assertFalse(summary_payload["raw_payload_logged"])
            self.assertNotIn("Hi Maya", queue.read_text(encoding="utf-8"))

    def test_export_rejects_raw_audit_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            record = review_required_record()
            record["raw_prompt"] = "do not export"
            audit_log.write_text(json.dumps(record) + "\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                runtime_human_review.export_runtime_human_review_queue(audit_log)

    def test_cli_exports_human_review_queue(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            queue = pathlib.Path(temp_dir) / "review-queue.jsonl"
            summary = pathlib.Path(temp_dir) / "review-summary.json"
            agent_api.append_audit_record(audit_log, review_required_record())

            code = aana_cli.main(
                [
                    "human-review-export",
                    "--audit-log",
                    str(audit_log),
                    "--queue-output",
                    str(queue),
                    "--summary-output",
                    str(summary),
                ]
            )

            self.assertEqual(code, 0)
            self.assertTrue(queue.exists())
            self.assertTrue(summary.exists())

    def test_public_exports_include_runtime_human_review_helpers(self):
        config = aana.human_review_export_config()

        self.assertEqual(aana.RUNTIME_HUMAN_REVIEW_VERSION, "0.1")
        self.assertEqual(config["export_type"], "aana_runtime_human_review_export")
        self.assertTrue(aana.validate_human_review_export_config(config)["valid"])


if __name__ == "__main__":
    unittest.main()
