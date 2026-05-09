import json
import pathlib
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

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

    def test_playground_static_assets(self):
        status, content_type, body = agent_server.playground_static_response("/playground")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"AANA Adapter Playground", body)

    def test_playground_supports_adapter_deep_links(self):
        status, content_type, body = agent_server.playground_static_response("/playground?adapter=email_send_guardrail")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"AANA Adapter Playground", body)
        app = (ROOT / "web" / "playground" / "app.js").read_text(encoding="utf-8")
        self.assertIn("new URLSearchParams(window.location.search)", app)
        self.assertIn('params.get("adapter")', app)
        self.assertIn("selectAdapter(selected.id)", app)

    def test_local_demos_static_assets(self):
        status, content_type, body = agent_server.playground_static_response("/demos")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"AANA Local Action Demos", body)

    def test_dashboard_static_assets(self):
        status, content_type, body = agent_server.playground_static_response("/dashboard")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"AANA Metrics Dashboard", body)

    def test_adapter_gallery_no_slash_uses_absolute_asset_paths(self):
        status, content_type, body = agent_server.playground_static_response("/adapter-gallery")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b'AANA Adapter Gallery', body)
        self.assertIn(b'href="/adapter-gallery/app.css"', body)
        self.assertIn(b'src="/adapter-gallery/app.js"', body)

    def test_playground_gallery_route(self):
        status, payload = agent_server.route_request("GET", "/playground/gallery")

        self.assertEqual(status, 200)
        self.assertGreater(payload["adapter_count"], 0)
        self.assertTrue(any(entry["id"] == "support_reply" for entry in payload["adapters"]))

    def test_local_demos_scenarios_route(self):
        status, payload = agent_server.route_request("GET", "/demos/scenarios")

        self.assertEqual(status, 200)
        self.assertEqual(payload["local_action_demos_version"], "0.1")
        self.assertEqual(len(payload["demos"]), 7)
        self.assertEqual(
            {demo["id"] for demo in payload["demos"]},
            {
                "email_send",
                "file_operation",
                "calendar_scheduling",
                "booking_purchase",
                "research_grounding",
                "publication_check",
                "meeting_summary",
            },
        )

    def test_dashboard_metrics_route_without_audit_log(self):
        status, payload = agent_server.route_request("GET", "/dashboard/metrics")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "missing_audit_log")
        self.assertEqual(payload["record_count"], 0)
        self.assertEqual(payload["cards"]["shadow_would_block_rate"], 0.0)

    def test_dashboard_metrics_route_reads_redacted_audit_log(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"
            agent_server.route_request(
                "POST",
                "/agent-check",
                json.dumps(event).encode("utf-8"),
                audit_log_path=audit_log,
            )

            status, payload = agent_server.route_request("GET", "/dashboard/metrics", audit_log_path=audit_log)

            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["record_count"], 1)
            self.assertEqual(payload["cards"]["total_records"], 1)
            self.assertTrue(payload["adapter_breakdown"])

    def test_mi_dashboard_metrics_route_reads_mi_observability_payload(self):
        status, payload = agent_server.route_request("GET", "/dashboard/mi-metrics")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mi_observability_dashboard_version"], "0.1")
        self.assertIn("handoff_pass_rate", payload["metrics"])
        self.assertIn("propagated_error_rate", payload["metrics"])
        self.assertIn("correction_success_rate", payload["metrics"])
        self.assertIn("false_accept_rate", payload["metrics"])
        self.assertIn("false_refusal_rate", payload["metrics"])
        self.assertIn("global_aix_drift_max_drop", payload["metrics"])

    def test_dashboard_static_assets_bind_mi_observability_ui(self):
        html = (ROOT / "web" / "dashboard" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "dashboard" / "app.js").read_text(encoding="utf-8")

        self.assertIn("mi-pass-fail", html)
        self.assertIn("mi-propagated-error", html)
        self.assertIn("mi-correction-success", html)
        self.assertIn("mi-false-routes", html)
        self.assertIn("mi-aix-drift", html)
        self.assertIn("/dashboard/mi-metrics", script)
        self.assertIn("renderMiDashboard", script)

    def test_openapi_route_documents_agent_check(self):
        status, payload = agent_server.route_request("GET", "/openapi.json")

        self.assertEqual(status, 200)
        self.assertEqual(payload["openapi"], "3.1.0")
        self.assertIn("/agent-check", payload["paths"])
        self.assertIn("/ready", payload["paths"])
        self.assertIn("/config", payload["paths"])
        self.assertIn("/validate-event", payload["paths"])
        self.assertIn("/workflow-check", payload["paths"])
        self.assertIn("/workflow-batch", payload["paths"])
        self.assertIn("/tool-precheck", payload["paths"])
        self.assertIn("/validate-tool-precheck", payload["paths"])
        self.assertIn("/playground/gallery", payload["paths"])
        self.assertIn("/playground/check", payload["paths"])
        self.assertIn("/demos/scenarios", payload["paths"])
        self.assertIn("/dashboard/metrics", payload["paths"])
        self.assertIn("/dashboard/mi-metrics", payload["paths"])
        self.assertIn("/validate-workflow", payload["paths"])
        self.assertIn("/validate-workflow-batch", payload["paths"])
        self.assertIn("AgentEvent", payload["components"]["schemas"])
        self.assertIn("WorkflowRequest", payload["components"]["schemas"])
        self.assertIn("WorkflowBatchRequest", payload["components"]["schemas"])
        self.assertIn("AgentToolPrecheck", payload["components"]["schemas"])
        self.assertIn("BridgeConfig", payload["components"]["schemas"])
        self.assertIn("error_code", payload["components"]["schemas"]["Error"]["properties"])

    def test_config_route_returns_redacted_deployment_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status, payload = agent_server.route_request(
                "GET",
                "/config",
                auth_token="secret-token",
                audit_log_path=pathlib.Path(temp_dir) / "audit.jsonl",
                max_body_bytes=2048,
                rate_limit_per_minute=12,
                read_timeout_seconds=3.5,
            )

            self.assertEqual(status, 200)
            self.assertTrue(payload["auth_required"])
            self.assertEqual(payload["auth_token_source"], "value")
            self.assertEqual(payload["audit_logging"], "enabled")
            self.assertEqual(payload["max_body_bytes"], 2048)
            self.assertEqual(payload["rate_limit_per_minute"], 12)
            self.assertEqual(payload["read_timeout_seconds"], 3.5)
            self.assertEqual(payload["runtime_routes"], ["/agent-check", "/workflow-check", "/workflow-batch", "/tool-precheck"])
            self.assertEqual(payload["raw_debug_leakage"], "disabled")
            self.assertTrue(payload["redacted_logs"])
            self.assertNotIn("secret-token", json.dumps(payload))

    def test_readiness_route_reports_ready_dependencies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status, payload = agent_server.route_request(
                "GET",
                "/ready",
                audit_log_path=pathlib.Path(temp_dir) / "audit.jsonl",
                auth_token="secret-token",
            )

            self.assertEqual(status, 200)
            self.assertTrue(payload["ready"])
            self.assertEqual(payload["summary"]["failures"], 0)

    def test_readiness_route_reports_missing_gallery(self):
        status, payload = agent_server.route_request(
            "GET",
            "/ready",
            gallery_path=ROOT / "examples" / "missing-gallery.json",
            auth_token="secret-token",
        )

        self.assertEqual(status, 503)
        self.assertFalse(payload["ready"])
        self.assertTrue(any(item["name"] == "adapter_gallery" for item in payload["checks"]))

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

    def test_tool_precheck_routes(self):
        event = {
            "schema_version": "aana.agent_tool_precheck.v1",
            "tool_name": "get_game_score",
            "tool_category": "public_read",
            "authorization_state": "none",
            "evidence_refs": [
                {
                    "source_id": "policy.public_scores",
                    "kind": "policy",
                    "trust_tier": "verified",
                    "redaction_status": "public",
                }
            ],
            "risk_domain": "public_information",
            "proposed_arguments": {"game_id": "GAME-123"},
            "recommended_route": "accept",
        }

        status, validation = agent_server.route_request("POST", "/validate-tool-precheck", json.dumps(event).encode("utf-8"))
        status_check, result = agent_server.route_request("POST", "/tool-precheck", json.dumps(event).encode("utf-8"))
        schema_status, schema = agent_server.route_request("GET", "/schemas/agent-tool-precheck.schema.json")

        self.assertEqual(status, 200)
        self.assertTrue(validation["valid"])
        self.assertEqual(status_check, 200)
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "accept")
        self.assertEqual(schema_status, 200)
        self.assertEqual(schema["title"], "AANA Agent Action Contract v1")

    def test_playground_check_returns_result_and_audit_preview(self):
        workflow_request = {
            "contract_version": "0.1",
            "workflow_id": "playground-test-support-reply",
            "adapter": "support_reply",
            "request": "Draft a support reply. Customer name is Maya Chen. Order ID and refund eligibility are unavailable. Do not include private account details.",
            "candidate": "Hi Maya, order #A1842 is eligible for a full refund and your card ending 4242 will be credited in 3 days.",
            "allowed_actions": ["accept", "revise", "retrieve", "ask", "defer", "refuse"],
            "metadata": {"surface": "test_playground"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "playground.jsonl"

            status, payload = agent_server.route_request(
                "POST",
                "/playground/check",
                json.dumps(workflow_request).encode("utf-8"),
                audit_log_path=audit_log,
            )

            self.assertEqual(status, 200)
            self.assertEqual(payload["result"]["adapter"], "support_reply")
            self.assertEqual(payload["result"]["gate_decision"], "pass")
            self.assertEqual(payload["audit_record"]["record_type"], "workflow_check")
            self.assertTrue(payload["audit_appended"])
            records = agent_api.load_audit_records(audit_log)
            self.assertEqual(len(records), 1)

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
            self.assertIsInstance(records[0]["latency_ms"], (int, float))
            self.assertGreaterEqual(records[0]["latency_ms"], 0)
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

    def test_shadow_mode_workflow_check_observes_without_blocking(self):
        workflow_request = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "shadow.jsonl"

            status, payload = agent_server.route_request(
                "POST",
                "/workflow-check?shadow_mode=true",
                json.dumps(workflow_request).encode("utf-8"),
                audit_log_path=audit_log,
            )

            self.assertEqual(status, 200)
            self.assertEqual(payload["execution_mode"], "shadow")
            self.assertEqual(payload["shadow_observation"]["enforcement"], "observe_only")
            self.assertEqual(payload["production_decision"]["production_effect"], "not_blocked")
            records = agent_api.load_audit_records(audit_log)
            self.assertEqual(records[0]["execution_mode"], "shadow")
            self.assertEqual(records[0]["shadow_observation"]["would_route"], "revise")

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
        self.assertEqual(payload["error_code"], "bad_request")
        self.assertEqual(payload["status"], 400)
        self.assertEqual(payload["error"], "Request could not be processed.")
        self.assertEqual(payload["details"]["exception_type"], "JSONDecodeError")

    def test_bad_request_error_does_not_leak_raw_payload_text(self):
        workflow_request = {
            "contract_version": "0.1",
            "workflow_id": "private-error-test",
            "request": "Customer says the card ending 4242 was charged twice.",
            "candidate": "Expose token sk_live_private and CRM fraud note.",
        }

        status, payload = agent_server.route_request(
            "POST",
            "/workflow-check",
            json.dumps(workflow_request).encode("utf-8"),
        )
        serialized = json.dumps(payload, sort_keys=True)

        self.assertEqual(status, 400)
        self.assertEqual(payload["error_code"], "bad_request")
        self.assertEqual(payload["error"], "Request could not be processed.")
        self.assertIn("exception_type", payload["details"])
        self.assertNotIn("4242", serialized)
        self.assertNotIn("sk_live_private", serialized)
        self.assertNotIn("fraud note", serialized)

    def test_post_body_limit_returns_413(self):
        status, payload = agent_server.route_request(
            "POST",
            "/validate-event",
            b'{"user_request":"x"}',
            max_body_bytes=4,
        )

        self.assertEqual(status, 413)
        self.assertEqual(payload["error"], "Request body too large.")
        self.assertEqual(payload["error_code"], "request_body_too_large")
        self.assertEqual(payload["max_body_bytes"], 4)

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

    def test_bridge_log_redacts_tokens_and_control_characters(self):
        text = agent_server._redact_log_text(
            "POST /workflow-check?token=secret-token&x=1\r\nAuthorization: Bearer abc123 X-AANA-Token: xyz"
        )

        self.assertNotIn("secret-token", text)
        self.assertNotIn("abc123", text)
        self.assertNotIn("xyz", text)
        self.assertIn("token=[redacted]", text)
        self.assertIn("\\r\\n", text)

    def test_auth_token_file_supports_rotation(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            token_file = pathlib.Path(temp_dir) / "aana-token.txt"
            token_file.write_text("first-token\n", encoding="utf-8")

            status, payload = agent_server.route_request(
                "POST",
                "/validate-event",
                json.dumps(event).encode("utf-8"),
                headers={"Authorization": "Bearer first-token"},
                auth_token_file=token_file,
            )
            self.assertEqual(status, 200)
            self.assertTrue(payload["valid"])

            token_file.write_text("second-token\n", encoding="utf-8")
            old_status, old_payload = agent_server.route_request(
                "POST",
                "/validate-event",
                json.dumps(event).encode("utf-8"),
                headers={"Authorization": "Bearer first-token"},
                auth_token_file=token_file,
            )
            new_status, new_payload = agent_server.route_request(
                "POST",
                "/validate-event",
                json.dumps(event).encode("utf-8"),
                headers={"Authorization": "Bearer second-token"},
                auth_token_file=token_file,
            )

            self.assertEqual(old_status, 401)
            self.assertEqual(old_payload["error_code"], "unauthorized")
            self.assertEqual(new_status, 200)
            self.assertTrue(new_payload["valid"])

    def test_missing_auth_token_file_rejects_post(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")

        status, payload = agent_server.route_request(
            "POST",
            "/validate-event",
            json.dumps(event).encode("utf-8"),
            auth_token_file=ROOT / "examples" / "missing-token.txt",
        )

        self.assertEqual(status, 503)
        self.assertEqual(payload["error_code"], "auth_token_unavailable")

    def test_post_rate_limit_returns_429(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        state = {}

        first_status, _ = agent_server.route_request(
            "POST",
            "/validate-event",
            json.dumps(event).encode("utf-8"),
            rate_limit_per_minute=1,
            rate_limit_state=state,
            client_id="client-a",
        )
        second_status, second_payload = agent_server.route_request(
            "POST",
            "/validate-event",
            json.dumps(event).encode("utf-8"),
            rate_limit_per_minute=1,
            rate_limit_state=state,
            client_id="client-a",
        )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 429)
        self.assertEqual(second_payload["error_code"], "rate_limited")

    def test_concurrent_agent_checks_append_distinct_audit_records(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log = pathlib.Path(temp_dir) / "audit.jsonl"

            def call_bridge(_):
                status, payload = agent_server.route_request(
                    "POST",
                    "/agent-check",
                    json.dumps(event).encode("utf-8"),
                    audit_log_path=audit_log,
                )
                return status, payload

            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(call_bridge, range(8)))

            self.assertTrue(all(status == 200 for status, _ in results), results)
            records = agent_api.load_audit_records(audit_log)
            self.assertEqual(len(records), 8)
            self.assertTrue(all(record["record_type"] == "agent_check" for record in records))


if __name__ == "__main__":
    unittest.main()
