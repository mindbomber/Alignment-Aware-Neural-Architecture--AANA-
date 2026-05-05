import json
import pathlib
import tempfile
import unittest

from eval_pipeline import agent_api, agent_server


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AgentServerTests(unittest.TestCase):
    def test_health_route(self):
        status, payload = agent_server.route_request("GET", "/health")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "aana-agent-bridge")

    def test_policy_presets_route(self):
        status, payload = agent_server.route_request("GET", "/policy-presets")

        self.assertEqual(status, 200)
        self.assertIn("message_send", payload["policy_presets"])

    def test_openapi_route_documents_agent_check(self):
        status, payload = agent_server.route_request("GET", "/openapi.json")

        self.assertEqual(status, 200)
        self.assertEqual(payload["openapi"], "3.1.0")
        self.assertIn("/agent-check", payload["paths"])
        self.assertIn("/validate-event", payload["paths"])
        self.assertIn("/workflow-check", payload["paths"])
        self.assertIn("/workflow-batch", payload["paths"])
        self.assertIn("/validate-workflow", payload["paths"])
        self.assertIn("/validate-workflow-batch", payload["paths"])
        self.assertIn("AgentEvent", payload["components"]["schemas"])
        self.assertIn("WorkflowRequest", payload["components"]["schemas"])
        self.assertIn("WorkflowBatchRequest", payload["components"]["schemas"])

    def test_agent_event_schema_route(self):
        status, payload = agent_server.route_request("GET", "/schemas/agent-event.schema.json")

        self.assertEqual(status, 200)
        self.assertEqual(payload["title"], "AANA Agent Event")
        self.assertIn("adapter_id", payload["properties"])

    def test_agent_check_route(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")

        status, payload = agent_server.route_request("POST", "/agent-check", json.dumps(event).encode("utf-8"))

        self.assertEqual(status, 200)
        self.assertEqual(payload["agent"], "openclaw")
        self.assertEqual(payload["gate_decision"], "pass")
        self.assertEqual(payload["recommended_action"], "revise")

    def test_agent_check_route_appends_redacted_audit_record(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"

            status, payload = agent_server.route_request(
                "POST",
                "/agent-check",
                json.dumps(event).encode("utf-8"),
                headers={"Authorization": "Bearer secret-token"},
                auth_token="secret-token",
                audit_log_path=audit_log,
            )

            self.assertEqual(status, 200)
            self.assertEqual(payload["gate_decision"], "pass")
            records = agent_api.load_audit_records(audit_log)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["record_type"], "agent_check")
            self.assertEqual(records[0]["adapter_id"], "support_reply")
            self.assertNotIn("Hi Maya", audit_log.read_text(encoding="utf-8"))

    def test_unauthorized_agent_check_does_not_append_audit_record(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"

            status, payload = agent_server.route_request(
                "POST",
                "/agent-check",
                json.dumps(event).encode("utf-8"),
                auth_token="secret-token",
                audit_log_path=audit_log,
            )

            self.assertEqual(status, 401)
            self.assertEqual(payload["error"], "Unauthorized.")
            self.assertFalse(audit_log.exists())

    def test_agent_check_audit_append_failure_returns_500(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            status, payload = agent_server.route_request(
                "POST",
                "/agent-check",
                json.dumps(event).encode("utf-8"),
                audit_log_path=pathlib.Path(temp_dir),
            )

            self.assertEqual(status, 500)
            self.assertIn("Audit append failed", payload["error"])

    def test_validate_event_route(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")

        status, payload = agent_server.route_request("POST", "/validate-event", json.dumps(event).encode("utf-8"))

        self.assertEqual(status, 200)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["errors"], 0)

    def test_validate_event_route_reports_invalid_event(self):
        status, payload = agent_server.route_request("POST", "/validate-event", b"{}")

        self.assertEqual(status, 200)
        self.assertFalse(payload["valid"])
        self.assertGreater(payload["errors"], 0)

    def test_validate_workflow_batch_route(self):
        batch_request = agent_api.load_json_file(ROOT / "examples" / "workflow_batch_productive_work.json")

        status, payload = agent_server.route_request("POST", "/validate-workflow-batch", json.dumps(batch_request).encode("utf-8"))

        self.assertEqual(status, 200)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["errors"], 0)

    def test_workflow_check_route_appends_redacted_audit_record(self):
        workflow_request = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"

            status, payload = agent_server.route_request(
                "POST",
                "/workflow-check",
                json.dumps(workflow_request).encode("utf-8"),
                audit_log_path=audit_log,
            )

            self.assertEqual(status, 200)
            records = agent_api.load_audit_records(audit_log)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["record_type"], "workflow_check")
            self.assertEqual(records[0]["adapter"], payload["adapter"])

    def test_workflow_batch_route_appends_per_item_audit_records(self):
        batch_request = agent_api.load_json_file(ROOT / "examples" / "workflow_batch_productive_work.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"

            status, payload = agent_server.route_request(
                "POST",
                "/workflow-batch",
                json.dumps(batch_request).encode("utf-8"),
                audit_log_path=audit_log,
            )

            self.assertEqual(status, 200)
            records = agent_api.load_audit_records(audit_log)
            self.assertEqual(len(records), len(payload["results"]))
            self.assertTrue(all(record["record_type"] == "workflow_check" for record in records))

    def test_bad_json_returns_400(self):
        status, payload = agent_server.route_request("POST", "/agent-check", b"{")

        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_post_body_limit_returns_413(self):
        status, payload = agent_server.route_request(
            "POST",
            "/validate-event",
            b'{"user_request":"x"}',
            max_body_bytes=4,
        )

        self.assertEqual(status, 413)
        self.assertEqual(payload["error"], "Request body too large.")

    def test_post_auth_token_rejects_missing_credentials(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")

        status, payload = agent_server.route_request(
            "POST",
            "/validate-event",
            json.dumps(event).encode("utf-8"),
            auth_token="secret-token",
        )

        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "Unauthorized.")

    def test_post_auth_token_accepts_bearer_credentials(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")

        status, payload = agent_server.route_request(
            "POST",
            "/validate-event",
            json.dumps(event).encode("utf-8"),
            headers={"Authorization": "Bearer secret-token"},
            auth_token="secret-token",
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["valid"])

    def test_post_auth_token_accepts_x_aana_token_header(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")

        status, payload = agent_server.route_request(
            "POST",
            "/validate-event",
            json.dumps(event).encode("utf-8"),
            headers={"X-AANA-Token": "secret-token"},
            auth_token="secret-token",
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["valid"])


if __name__ == "__main__":
    unittest.main()
