import json
import pathlib
import tempfile
import unittest

from fastapi.testclient import TestClient

from eval_pipeline import agent_api
from eval_pipeline.fastapi_app import create_app


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FastApiAppTests(unittest.TestCase):
    def test_health_and_openapi_docs_are_available(self):
        client = TestClient(create_app(auth_token="secret-token"))

        health = client.get("/health")
        openapi = client.get("/openapi.json")
        docs = client.get("/docs")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["service"], "aana-fastapi")
        self.assertEqual(health.json()["contract"], "aana.agent_action_contract.v1")
        self.assertTrue(health.json()["auth_required"])
        self.assertEqual(
            health.json()["auth_scopes"],
            [
                "agent_check",
                "aix_audit",
                "enterprise_connectors",
                "enterprise_demo",
                "pre_tool_check",
                "validation",
                "workflow_batch",
                "workflow_check",
            ],
        )
        self.assertTrue(health.json()["rate_limit"]["enabled"])
        self.assertTrue(health.json()["request_size_limit"]["enabled"])
        self.assertEqual(openapi.status_code, 200)
        openapi_payload = openapi.json()
        self.assertIn("/pre-tool-check", openapi_payload["paths"])
        self.assertIn("/agent-check", openapi_payload["paths"])
        self.assertIn("/workflow-check", openapi_payload["paths"])
        self.assertIn("/workflow-batch", openapi_payload["paths"])
        self.assertIn("/aix-audit", openapi_payload["paths"])
        self.assertIn("/enterprise-connectors", openapi_payload["paths"])
        self.assertIn("/enterprise-support-demo", openapi_payload["paths"])
        self.assertIn("HTTPBearer", openapi_payload["components"]["securitySchemes"])
        self.assertIn("APIKeyHeader", openapi_payload["components"]["securitySchemes"])
        pre_tool_body = openapi_payload["paths"]["/pre-tool-check"]["post"]["requestBody"]["content"]["application/json"]
        self.assertIn("writeNeedsConfirmation", pre_tool_body["examples"])
        agent_body = openapi_payload["paths"]["/agent-check"]["post"]["requestBody"]["content"]["application/json"]
        self.assertIn("supportReplyNeedsRevision", agent_body["examples"])
        self.assertIn("413", openapi_payload["paths"]["/pre-tool-check"]["post"]["responses"])
        self.assertIn("429", openapi_payload["paths"]["/agent-check"]["post"]["responses"])
        self.assertEqual(docs.status_code, 200)

    def test_post_routes_require_token_when_configured(self):
        client = TestClient(create_app(auth_token="secret-token"))

        response = client.post("/pre-tool-check", json={"tool_name": "send_email"})
        wrong = client.post("/pre-tool-check", json={"tool_name": "send_email"}, headers={"Authorization": "Bearer wrong-token"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(wrong.status_code, 401)

    def test_post_routes_require_configured_scope(self):
        client = TestClient(create_app(auth_token="secret-token", auth_scopes={"pre_tool_check"}))
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")

        response = client.post("/agent-check", json=event, headers={"Authorization": "Bearer secret-token"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "insufficient_scope")
        self.assertEqual(response.json()["detail"]["required_scope"], "agent_check")

    def test_request_size_limit_rejects_large_post_before_check(self):
        client = TestClient(create_app(auth_token="secret-token", max_request_bytes=16, rate_limit_per_minute=0))

        response = client.post(
            "/pre-tool-check",
            json={"tool_name": "send_email", "proposed_arguments": {"body": "x" * 200}},
            headers={"Authorization": "Bearer secret-token"},
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"], "request_too_large")

    def test_rate_limit_rejects_repeated_requests(self):
        client = TestClient(create_app(auth_token=None, rate_limit_per_minute=1, max_request_bytes=0))

        first = client.get("/health")
        second = client.get("/health")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["error"], "rate_limited")
        self.assertIn("Retry-After", second.headers)

    def test_pre_tool_check_accepts_quickstart_shape_and_appends_redacted_audit(self):
        payload = {
            "tool_name": "send_email",
            "tool_category": "write",
            "authorization_state": "user_claimed",
            "evidence_refs": ["draft_id:123"],
            "risk_domain": "customer_support",
            "proposed_arguments": {"to": "customer@example.com"},
            "recommended_route": "accept",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            client = TestClient(create_app(auth_token="secret-token", audit_log_path=audit_log))
            response = client.post("/pre-tool-check", json=payload, headers={"Authorization": "Bearer secret-token"})

            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertEqual(result["recommended_action"], "ask")
            self.assertEqual(result["architecture_decision"]["route"], "ask")
            self.assertTrue(audit_log.exists())
            records = [json.loads(line) for line in audit_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["record_type"], "tool_precheck")
            self.assertEqual(records[0]["audit_record_version"], "0.1")
            self.assertEqual(records[0]["proposed_argument_keys"], ["to"])
            self.assertEqual(records[0]["audit_safe_log_event"]["route"], "ask")
            self.assertEqual(records[0]["audit_safe_log_event"]["authorization_state"], "user_claimed")
            self.assertIn("latency_ms", records[0]["audit_safe_log_event"])
            self.assertNotIn("customer@example.com", audit_log.read_text(encoding="utf-8"))
            self.assertTrue(agent_api.validate_audit_records(records)["valid"])

    def test_checked_in_fastapi_examples_are_runnable(self):
        client = TestClient(create_app(auth_token="secret-token"))
        pre_tool = json.loads((ROOT / "examples" / "api" / "pre_tool_check_write_ask.json").read_text(encoding="utf-8"))
        confirmed = json.loads((ROOT / "examples" / "api" / "pre_tool_check_confirmed_write.json").read_text(encoding="utf-8"))
        agent_event = json.loads((ROOT / "examples" / "api" / "agent_check_support_reply.json").read_text(encoding="utf-8"))

        ask = client.post("/pre-tool-check", json=pre_tool, headers={"Authorization": "Bearer secret-token"})
        accept = client.post("/pre-tool-check", json=confirmed, headers={"Authorization": "Bearer secret-token"})
        revise = client.post("/agent-check", json=agent_event, headers={"Authorization": "Bearer secret-token"})

        self.assertEqual(ask.status_code, 200)
        self.assertEqual(ask.json()["recommended_action"], "ask")
        self.assertEqual(accept.status_code, 200)
        self.assertEqual(accept.json()["recommended_action"], "accept")
        self.assertEqual(revise.status_code, 200)
        self.assertEqual(revise.json()["recommended_action"], "revise")

    def test_agent_check_uses_existing_contract_and_appends_audit(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            client = TestClient(create_app(auth_token="secret-token", audit_log_path=audit_log))
            response = client.post("/agent-check", json=event, headers={"X-AANA-Token": "secret-token"})

            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertEqual(result["gate_decision"], "pass")
            self.assertEqual(result["recommended_action"], "revise")
            self.assertTrue(audit_log.exists())
            records = [json.loads(line) for line in audit_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["record_type"], "agent_check")

    def test_workflow_routes_validate_check_and_append_redacted_audit(self):
        workflow = {
            "contract_version": "0.1",
            "workflow_id": "test-workflow",
            "adapter": "support_reply",
            "request": "Draft a support reply using only verified facts.",
            "candidate": "Your refund is approved and arrives tomorrow.",
            "evidence": ["Refund eligibility: unavailable."],
            "allowed_actions": ["accept", "revise", "ask", "defer", "refuse"],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            client = TestClient(create_app(auth_token="secret-token", audit_log_path=audit_log))
            validation = client.post("/validate-workflow", json=workflow, headers={"Authorization": "Bearer secret-token"})
            single = client.post("/workflow-check", json=workflow, headers={"Authorization": "Bearer secret-token"})
            batch = client.post(
                "/workflow-batch",
                json={"contract_version": "0.1", "batch_id": "test-batch", "requests": [workflow]},
                headers={"Authorization": "Bearer secret-token"},
            )

            self.assertEqual(validation.status_code, 200)
            self.assertTrue(validation.json()["valid"])
            self.assertEqual(single.status_code, 200)
            self.assertIn(single.json()["recommended_action"], {"revise", "ask", "defer", "refuse"})
            self.assertEqual(batch.status_code, 200)
            self.assertEqual(batch.json()["summary"]["total"], 1)
            records = [json.loads(line) for line in audit_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["record_type"] for record in records], ["workflow_check", "workflow_check"])
            self.assertNotIn("Your refund is approved", audit_log.read_text(encoding="utf-8"))

    def test_fastapi_aix_audit_matches_enterprise_product_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app(auth_token="secret-token", rate_limit_per_minute=0, max_request_bytes=0))
            response = client.post(
                "/aix-audit",
                json={"output_dir": temp_dir, "shadow_mode": True},
                headers={"Authorization": "Bearer secret-token"},
            )

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            summary = payload["summary"]
            self.assertTrue(payload["valid"], payload["aix_report_validation"])
            self.assertEqual(payload["product"], "AANA AIx Audit")
            self.assertEqual(payload["product_bundle"], "enterprise_ops_pilot")
            self.assertEqual(payload["deployment_recommendation"], "pilot_ready_with_controls")
            self.assertEqual(summary["workflow_count"], 8)
            self.assertEqual(summary["audit_records"], 8)
            for key in (
                "audit_log",
                "metrics",
                "drift_report",
                "integrity_manifest",
                "enterprise_dashboard",
                "enterprise_connector_readiness",
                "aix_report_json",
                "aix_report_md",
            ):
                self.assertTrue(pathlib.Path(summary[key]).exists(), key)

            dashboard = json.loads(pathlib.Path(summary["enterprise_dashboard"]).read_text(encoding="utf-8"))
            connectors = json.loads(pathlib.Path(summary["enterprise_connector_readiness"]).read_text(encoding="utf-8"))
            audit_text = pathlib.Path(summary["audit_log"]).read_text(encoding="utf-8")
            self.assertEqual(dashboard["source_of_truth"], "redacted_audit_metrics")
            self.assertEqual(dashboard["cards"]["shadow_would_intervene"], 8)
            self.assertEqual(connectors["summary"]["connector_count"], 7)
            self.assertEqual(connectors["summary"]["live_execution_enabled_count"], 0)
            self.assertNotIn("sk-live-secret-123", audit_text)
            self.assertNotIn("payroll.xlsx", audit_text)
            self.assertIn("not production certification", " ".join(payload["aix_report"]["limitations"]).lower())

    def test_fastapi_enterprise_connectors_matches_readiness_contract(self):
        client = TestClient(create_app(auth_token="secret-token", rate_limit_per_minute=0, max_request_bytes=0))

        response = client.get("/enterprise-connectors", headers={"Authorization": "Bearer secret-token"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["validation"]["valid"], payload["validation"])
        plan = payload["plan"]
        self.assertEqual(plan["summary"]["connector_count"], 7)
        self.assertEqual(plan["summary"]["live_execution_enabled_count"], 0)
        self.assertEqual(
            set(plan["summary"]["required_connector_ids"]),
            {"crm_support", "ticketing", "email_send", "iam", "ci", "deployment", "data_export"},
        )
        for connector in plan["connectors"]:
            self.assertFalse(connector["live_execution_enabled"])
            self.assertEqual(connector["default_runtime_route_before_approval"], "defer")
            self.assertFalse(connector["auth_requirements"]["tokens_in_audit_logs"])
            self.assertFalse(connector["redaction_requirements"]["raw_private_content_allowed_in_audit"])
            self.assertTrue(connector["shadow_mode_requirements"]["write_operations_disabled"])

    def test_fastapi_enterprise_support_demo_matches_shadow_demo_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app(auth_token="secret-token", rate_limit_per_minute=0, max_request_bytes=0))
            response = client.post(
                "/enterprise-support-demo",
                json={"output_dir": temp_dir, "shadow_mode": True},
                headers={"Authorization": "Bearer secret-token"},
            )

            self.assertEqual(response.status_code, 200, response.text)
            flow = response.json()
            self.assertTrue(flow["valid"], flow)
            self.assertEqual(flow["wedge"], "customer support + email send + ticket update")
            self.assertEqual(len(flow["steps"]), 3)
            self.assertEqual(flow["aix_report_summary"]["deployment_recommendation"], "not_pilot_ready")
            self.assertEqual(flow["dashboard_cards"]["shadow_would_intervene"], 3)
            self.assertEqual(flow["dashboard_cards"]["shadow_would_block"], 1)
            self.assertEqual(flow["dashboard_cards"]["hard_blockers"], 1)

            routes = {step["stage"]: step["aana_check"]["recommended_action"] for step in flow["steps"]}
            self.assertEqual(routes["support_reply"], "revise")
            self.assertEqual(routes["email_send"], "defer")
            self.assertEqual(routes["ticket_update"], "revise")
            email_step = next(step for step in flow["steps"] if step["stage"] == "email_send")
            self.assertIn("recommended_action_not_allowed", email_step["aix"]["hard_blockers"])

            for key in ("audit_log", "metrics", "dashboard", "aix_report_json", "aix_report_md", "demo_flow"):
                self.assertTrue(pathlib.Path(flow["artifacts"][key]).exists(), key)
            audit_text = pathlib.Path(flow["artifacts"]["audit_log"]).read_text(encoding="utf-8")
            self.assertNotIn("sk-live-secret-123", audit_text)
            self.assertNotIn("payroll.xlsx", audit_text)


if __name__ == "__main__":
    unittest.main()
