import subprocess
import sys
import unittest
import json
from pathlib import Path

import aana
from fastapi.testclient import TestClient
from eval_pipeline.fastapi_app import create_app
from examples.integrations.openai_agents.api_guard import AANAApiGuard


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = [
    "openai_agents_sdk.py",
    "langchain.py",
    "autogen.py",
    "crewai.py",
    "mcp.py",
]


class IntegrationExamplesTests(unittest.TestCase):
    def test_integration_examples_run_without_framework_dependencies(self):
        for filename in EXAMPLES:
            with self.subTest(filename=filename):
                completed = subprocess.run(
                    [sys.executable, str(ROOT / "examples" / "integrations" / filename)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                )

                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertIn("'aana_route': 'accept'", completed.stdout)

    def test_public_docs_link_each_integration_example(self):
        readme = (ROOT / "examples" / "integrations" / "README.md").read_text(encoding="utf-8")
        docs = (ROOT / "docs" / "agent-framework-middleware.md").read_text(encoding="utf-8")

        for name in ["OpenAI Agents SDK", "LangChain", "AutoGen", "CrewAI", "MCP"]:
            with self.subTest(name=name):
                self.assertIn(name, readme)
                self.assertIn(name, docs)

    def test_openai_agents_demo_proves_blocked_tool_does_not_execute(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "examples" / "integrations" / "openai_agents" / "demo.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["blocked_send_email_executed"])
        self.assertEqual([item["route"] for item in payload["decisions"]], ["accept", "ask", "accept"])
        self.assertEqual(
            [item["tool_name"] for item in payload["executed_tool_calls"]],
            ["get_public_status", "send_customer_email"],
        )

    def test_openai_agents_manual_middleware_quickstart_shape_blocks(self):
        calls = []

        def send_email(to, body):
            calls.append((to, body))
            return {"sent": True}

        decision = aana.check_tool_call(
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

        if decision["route"] != "accept":
            result = {"blocked": True, "aana": decision}
        else:
            result = send_email(to="customer@example.com", body="Needs confirmation")

        self.assertTrue(result["blocked"])
        self.assertEqual(result["aana"]["route"], "ask")
        self.assertEqual(calls, [])

    def test_openai_agents_api_guard_blocks_without_importing_aana_in_app_path(self):
        calls = []
        test_client = create_app(auth_token="secret-token", rate_limit_per_minute=0, max_request_bytes=0)

        def test_post(url, payload, *, token=None):
            path = "/" + url.rstrip("/").split("/")[-1]
            response = TestClient(test_client).post(path, json=payload, headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()

        def send_email(to, body):
            calls.append((to, body))
            return {"sent": True}

        guard = AANAApiGuard(base_url="http://aana.test", token="secret-token", post=test_post)
        guarded = guard.guard_tool(
            send_email,
            tool_name="send_email",
            tool_category="write",
            authorization_state="user_claimed",
            evidence_refs=["draft_id:123"],
            risk_domain="customer_support",
        )

        result = guarded(to="customer@example.com", body="Needs confirmation")

        self.assertTrue(result["blocked"])
        self.assertEqual(result["aana"]["route"], "ask")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
