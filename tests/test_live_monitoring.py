import copy
import json
import pathlib
import tempfile
import unittest

import aana
from eval_pipeline import agent_api, live_monitoring
from scripts import aana_cli


def healthy_record():
    event = agent_api.load_json_file("examples/agent_event_support_reply.json")
    result = agent_api.check_event(event)
    result["gate_decision"] = "pass"
    result["candidate_gate"] = "pass"
    result["recommended_action"] = "accept"
    result["violations"] = []
    result["aix"] = {
        "aix_version": "0.1",
        "score": 0.96,
        "components": {"P": 0.96, "B": 0.96, "C": 0.96, "F": 0.96},
        "decision": "accept",
        "hard_blockers": [],
    }
    result["audit_metadata"] = {"latency_ms": 42.0}
    return agent_api.audit_event_check(event, result, created_at="2026-05-05T00:00:00Z")


def critical_record():
    record = healthy_record()
    record["gate_decision"] = "fail"
    record["recommended_action"] = "defer"
    record["candidate_gate"] = "fail"
    record["aix"]["score"] = 0.4
    record["aix"]["decision"] = "defer"
    record["aix"]["hard_blockers"] = ["missing_policy_evidence"]
    record["hard_blockers"] = ["missing_policy_evidence"]
    record["human_review_queue"] = {
        "required": True,
        "queue": "support_human_review",
        "route": "human_review_queue",
        "priority": "critical",
        "triggers": ["aix_hard_blocker"],
        "reason": "aix_hard_blocker",
    }
    record["audit_safe_log_event"]["route"] = "defer"
    record["audit_safe_log_event"]["hard_blockers"] = ["missing_policy_evidence"]
    return record


class LiveMonitoringTests(unittest.TestCase):
    def test_config_validates_redacted_live_monitoring_defaults(self):
        config = live_monitoring.live_monitoring_config()
        report = live_monitoring.validate_live_monitoring_config(config)

        self.assertTrue(report["valid"], report)
        self.assertEqual(config["config_type"], "aana_live_monitoring_config")
        self.assertEqual(config["source_of_truth"], "redacted_aana_runtime_audit_jsonl")
        self.assertFalse(config["redaction"]["raw_prompt_logged"])

    def test_live_monitoring_report_marks_healthy_records_healthy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            output = pathlib.Path(temp_dir) / "live-monitoring.json"
            agent_api.append_audit_record(audit_log, healthy_record())

            report = live_monitoring.live_monitoring_report(audit_log, output_path=output)

            self.assertEqual(report["status"], "healthy", report["checks"])
            self.assertTrue(report["healthy"])
            self.assertTrue(output.exists())
            self.assertEqual(report["summary"]["aix_average"], 0.96)
            self.assertFalse(report["raw_payload_logged"])
            self.assertNotIn("Hi Maya", output.read_text(encoding="utf-8"))

    def test_live_monitoring_report_marks_hard_blocker_traffic_critical(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            agent_api.append_audit_record(audit_log, critical_record())

            report = live_monitoring.live_monitoring_report(audit_log)

            self.assertEqual(report["status"], "critical")
            self.assertFalse(report["healthy"])
            metrics = {check["metric"]: check for check in report["checks"]}
            self.assertEqual(metrics["aix_hard_blocker_rate"]["status"], "critical")
            self.assertEqual(metrics["aix_score_min"]["status"], "critical")

    def test_cli_live_monitoring_writes_config_and_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            output = pathlib.Path(temp_dir) / "live-monitoring.json"
            config_path = pathlib.Path(temp_dir) / "live-monitoring-config.json"
            agent_api.append_audit_record(audit_log, healthy_record())

            write_code = aana_cli.main(["live-monitoring", "--write-config", "--config", str(config_path)])
            report_code = aana_cli.main(
                [
                    "live-monitoring",
                    "--audit-log",
                    str(audit_log),
                    "--config",
                    str(config_path),
                    "--output",
                    str(output),
                ]
            )

            self.assertEqual(write_code, 0)
            self.assertEqual(report_code, 0)
            self.assertTrue(config_path.exists())
            self.assertTrue(output.exists())

    def test_live_monitoring_rejects_raw_audit_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            record = healthy_record()
            record["raw_prompt"] = "do not monitor"
            audit_log.write_text(json.dumps(record) + "\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                live_monitoring.live_monitoring_report(audit_log)

    def test_public_exports_include_live_monitoring_helpers(self):
        config = aana.live_monitoring_config()

        self.assertEqual(aana.LIVE_MONITORING_VERSION, "0.1")
        self.assertEqual(config["config_type"], "aana_live_monitoring_config")
        self.assertTrue(aana.validate_live_monitoring_config(config)["valid"])


if __name__ == "__main__":
    unittest.main()
