import json
import pathlib
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

    def test_bad_json_returns_400(self):
        status, payload = agent_server.route_request("POST", "/agent-check", b"{")

        self.assertEqual(status, 400)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
