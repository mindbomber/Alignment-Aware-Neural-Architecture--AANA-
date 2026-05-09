import json
import subprocess
import sys
import unittest
from pathlib import Path

from eval_pipeline import mcp_server
from examples.chatgpt_app.aana_mcp_app import create_app
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


class AANAMcpServerTests(unittest.TestCase):
    def test_tool_descriptor_exposes_standard_pre_tool_check(self):
        tools = mcp_server.list_tools()

        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertEqual(tool["name"], "aana_pre_tool_check")
        self.assertTrue(tool["annotations"]["readOnlyHint"])
        self.assertFalse(tool["annotations"]["destructiveHint"])
        self.assertIn("tool_name", tool["inputSchema"]["required"])
        self.assertIn("authorization_state", tool["inputSchema"]["properties"])

    def test_pre_tool_check_tool_blocks_unconfirmed_write(self):
        response = mcp_server.handle_aana_pre_tool_check(
            {
                "tool_name": "send_email",
                "tool_category": "write",
                "authorization_state": "user_claimed",
                "evidence_refs": ["draft_id:123"],
                "risk_domain": "customer_support",
                "proposed_arguments": {"to": "customer@example.com"},
                "recommended_route": "accept",
            }
        )

        self.assertEqual(response["structuredContent"]["route"], "ask")
        self.assertFalse(response["structuredContent"]["execution_allowed"])
        self.assertEqual(response["content"][0]["type"], "text")
        self.assertIn("aana_decision", response["_meta"])

    def test_pre_tool_check_tool_accepts_confirmed_write(self):
        response = mcp_server.handle_aana_pre_tool_check(
            {
                "tool_name": "send_email",
                "tool_category": "write",
                "authorization_state": "confirmed",
                "evidence_refs": [
                    {
                        "source_id": "approval.user.confirmed_send",
                        "kind": "approval",
                        "trust_tier": "verified",
                        "redaction_status": "redacted",
                        "summary": "The user explicitly confirmed this redacted email draft should be sent.",
                    }
                ],
                "risk_domain": "customer_support",
                "proposed_arguments": {"to": "customer@example.com"},
                "recommended_route": "accept",
            }
        )

        self.assertEqual(response["structuredContent"]["route"], "accept")
        self.assertTrue(response["structuredContent"]["execution_allowed"])

    def test_jsonrpc_tools_list_and_call(self):
        listed = mcp_server.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        called = mcp_server.handle_jsonrpc(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "aana_pre_tool_check",
                    "arguments": {
                        "tool_name": "get_public_status",
                        "tool_category": "public_read",
                        "authorization_state": "none",
                        "evidence_refs": ["policy:public-status-read"],
                        "risk_domain": "public_information",
                        "proposed_arguments": {"service": "docs"},
                        "recommended_route": "accept",
                    },
                },
            }
        )

        self.assertEqual(listed["result"]["tools"][0]["name"], "aana_pre_tool_check")
        self.assertEqual(called["result"]["structuredContent"]["route"], "accept")

    def test_jsonrpc_resources_list_and_read_decision_viewer(self):
        listed = mcp_server.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "resources/list"})
        read = mcp_server.handle_jsonrpc(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {"uri": "ui://aana/decision.html"},
            }
        )

        self.assertEqual(listed["result"]["resources"][0]["uri"], "ui://aana/decision.html")
        content = read["result"]["contents"][0]
        self.assertEqual(content["mimeType"], "text/html;profile=mcp-app")
        self.assertIn("AANA Pre-Tool Decision", content["text"])

    def test_script_lists_tools(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "aana_mcp_server.py"), "--list-tools"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["tools"][0]["name"], "aana_pre_tool_check")

    def test_chatgpt_app_prototype_exposes_mcp_http_endpoint(self):
        client = TestClient(create_app())

        health = client.get("/health")
        listed = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        called = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "aana_pre_tool_check",
                    "arguments": {
                        "tool_name": "send_email",
                        "tool_category": "write",
                        "authorization_state": "user_claimed",
                        "evidence_refs": ["draft_id:123"],
                        "risk_domain": "customer_support",
                        "proposed_arguments": {"to": "customer@example.com"},
                        "recommended_route": "accept",
                    },
                },
            },
        )
        widget = client.get("/aana-decision.html")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["mcp_endpoint"], "/mcp")
        self.assertEqual(listed.json()["result"]["tools"][0]["name"], "aana_pre_tool_check")
        self.assertEqual(called.json()["result"]["structuredContent"]["route"], "ask")
        self.assertEqual(widget.status_code, 200)
        self.assertIn("AANA Pre-Tool Decision", widget.text)


if __name__ == "__main__":
    unittest.main()
