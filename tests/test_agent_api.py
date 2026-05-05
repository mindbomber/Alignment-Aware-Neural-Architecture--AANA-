import pathlib
import tempfile
import unittest

from eval_pipeline import agent_api


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AgentApiTests(unittest.TestCase):
    def test_check_event_returns_agent_guardrail_result(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")

        result = agent_api.check_event(event)

        self.assertEqual(result["agent"], "openclaw")
        self.assertEqual(result["adapter_id"], "support_reply")
        self.assertEqual(result["candidate_gate"], "block")
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "revise")
        self.assertTrue(result["violations"])
        self.assertIn("safe_response", result)
        self.assertIn("aix", result)
        self.assertIn("candidate_aix", result)
        self.assertEqual(result["aix"]["decision"], "accept")

    def test_policy_presets_include_agent_workflows(self):
        presets = agent_api.list_policy_presets()

        self.assertIn("message_send", presets)
        self.assertIn("file_write", presets)
        self.assertIn("code_commit", presets)
        self.assertIn("support_reply", presets)
        self.assertIn("research_summary", presets)
        self.assertIn("private_data_use", presets)

    def test_validate_event_reports_missing_adapter(self):
        report = agent_api.validate_event({"user_request": "Draft a reply."})

        self.assertFalse(report["valid"])
        self.assertEqual(report["errors"], 1)
        self.assertIn("adapter_id", report["issues"][0]["path"])

    def test_run_agent_event_examples(self):
        report = agent_api.run_agent_event_examples()

        self.assertTrue(report["valid"])
        self.assertGreaterEqual(report["count"], 3)
        event_ids = {item["event_id"] for item in report["checked_examples"]}
        self.assertIn("demo-support-refund-001", event_ids)
        self.assertIn("demo-travel-booking-001", event_ids)
        self.assertIn("demo-meal-planning-001", event_ids)
        self.assertIn("demo-research-summary-001", event_ids)

    def test_check_research_event_returns_grounded_revision(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_events" / "research_summary.json")

        result = agent_api.check_event(event)

        self.assertEqual(result["adapter_id"], "research_summary")
        self.assertEqual(result["candidate_gate"], "block")
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "revise")
        self.assertTrue(result["violations"])
        self.assertIn("Grounded research summary", result["safe_response"])

    def test_scaffold_agent_event_from_gallery(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = agent_api.scaffold_agent_event("support_reply", output_dir=tmp)

            path = pathlib.Path(created["event"])
            self.assertTrue(path.exists())
            event = agent_api.load_json_file(path)
            self.assertEqual(event["adapter_id"], "support_reply")
            self.assertEqual(event["metadata"]["expected_gate_decision"], "pass")
            self.assertTrue(agent_api.validate_event(event)["valid"])

    def test_audit_event_check_excludes_raw_sensitive_text(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        event["candidate_action"] = "Customer card ending 4242 should receive a refund."
        result = agent_api.check_event(event)

        record = agent_api.audit_event_check(event, result, created_at="2026-05-05T00:00:00+00:00")
        serialized = str(record)

        self.assertEqual(record["record_type"], "agent_check")
        self.assertEqual(record["event_id"], event["event_id"])
        self.assertEqual(record["adapter_id"], "support_reply")
        self.assertEqual(record["gate_decision"], "pass")
        self.assertEqual(record["recommended_action"], "revise")
        self.assertEqual(record["aix"]["decision"], "accept")
        self.assertGreater(record["violation_count"], 0)
        self.assertIn("private_account_detail", record["violation_codes"])
        self.assertIn("sha256", record["input_fingerprints"]["candidate"])
        self.assertNotIn("4242", serialized)
        self.assertNotIn("Customer card", serialized)

    def test_audit_jsonl_roundtrip_and_summary(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        result = agent_api.check_event(event)
        record = agent_api.audit_event_check(event, result, created_at="2026-05-05T00:00:00+00:00")

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "audit.jsonl"
            agent_api.append_audit_record(path, record)
            records = agent_api.load_audit_records(path)
            summary = agent_api.summarize_audit_records(records)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["record_type"], "agent_check")
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["gate_decisions"]["pass"], 1)
        self.assertEqual(summary["recommended_actions"]["revise"], 1)
        self.assertIn("invented_order_id", summary["violation_codes"])
        self.assertEqual(summary["aix"]["decisions"]["accept"], 1)
        self.assertEqual(summary["aix"]["hard_blockers"], {})

    def test_export_audit_metrics_flattens_summary_for_dashboards(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        result = agent_api.check_event(event)
        record = agent_api.audit_event_check(event, result, created_at="2026-05-05T00:00:00+00:00")

        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "audit.jsonl"
            metrics_path = pathlib.Path(tmp) / "metrics" / "aana-metrics.json"
            agent_api.append_audit_record(audit_log, record)
            payload = agent_api.export_audit_metrics_file(
                audit_log,
                output_path=metrics_path,
                created_at="2026-05-05T00:01:00+00:00",
            )

            metrics = payload["metrics"]
            self.assertTrue(metrics_path.exists())
            self.assertEqual(payload["audit_metrics_export_version"], "0.1")
            self.assertEqual(payload["record_count"], 1)
            self.assertEqual(metrics["audit_records_total"], 1)
            self.assertEqual(metrics["audit_record_type_count.agent_check"], 1)
            self.assertEqual(metrics["gate_decision_count"], 1)
            self.assertEqual(metrics["gate_decision_count.pass"], 1)
            self.assertEqual(metrics["recommended_action_count"], 1)
            self.assertEqual(metrics["recommended_action_count.revise"], 1)
            self.assertGreater(metrics["violation_code_count"], 0)
            self.assertEqual(metrics["violation_code_count.invented_order_id"], 1)
            self.assertEqual(metrics["adapter_check_count.support_reply"], 1)
            self.assertEqual(metrics["aix_score_average"], 1.0)
            self.assertEqual(metrics["aix_decision_count"], 1)
            self.assertEqual(metrics["aix_decision_count.accept"], 1)
            self.assertEqual(metrics["aix_hard_blocker_count"], 0)
            self.assertIn("latency", payload["unavailable_metrics"])


if __name__ == "__main__":
    unittest.main()
