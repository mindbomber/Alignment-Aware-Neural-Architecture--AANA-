import subprocess
import sys
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
while str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))
loaded_evals = sys.modules.get("evals")
if loaded_evals is not None and not str(getattr(loaded_evals, "__file__", "")).startswith(str(ROOT)):
    del sys.modules["evals"]

from evals.openai_agents_aana.run_local import run_eval
from examples.integrations.openai_agents.api_guard import AANAApiGuard
from examples.integrations.openai_agents.wrapped_tools import run_smoke as run_openai_wrapped_tools_smoke
import aana
from fastapi.testclient import TestClient
from eval_pipeline.fastapi_app import create_app


EXAMPLES = [
    "plain_python.py",
    "openai_agents_sdk.py",
    "langchain.py",
    "autogen.py",
    "crewai.py",
    "fastapi_api_guard.py",
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
                try:
                    payload = json.loads(completed.stdout)
                except json.JSONDecodeError:
                    self.assertIn("'aana_route': 'accept'", completed.stdout)
                    continue
                self.assertEqual(payload["accepted_route"], "accept")
                self.assertIn(payload["blocked_route"], {"ask", "defer", "refuse"})
                self.assertFalse(payload["blocked_tool_executed"])

    def test_public_docs_link_each_integration_example(self):
        readme = (ROOT / "examples" / "integrations" / "README.md").read_text(encoding="utf-8")
        docs = (ROOT / "docs" / "agent-framework-middleware.md").read_text(encoding="utf-8")

        for name in ["Plain Python", "OpenAI Agents SDK", "LangChain", "AutoGen", "CrewAI", "FastAPI", "MCP"]:
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

    def test_openai_agents_wrapped_tools_example_proves_blocked_tool_does_not_execute(self):
        result = run_openai_wrapped_tools_smoke()

        self.assertEqual(result["routes"]["get_public_status"], "accept")
        self.assertEqual(result["routes"]["get_customer_profile"], "accept")
        self.assertEqual(result["routes"]["send_customer_email_without_confirmation"], "ask")
        self.assertEqual(result["routes"]["send_customer_email_confirmed"], "accept")
        self.assertFalse(result["blocked_write_executed"])
        self.assertEqual(
            [item["tool_name"] for item in result["executed_tool_calls"]],
            ["get_public_status", "get_customer_profile", "send_customer_email_confirmed"],
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

    def test_openai_agents_local_eval_harness_passes_behavior_matrix(self):
        result = run_eval()

        self.assertEqual(result["metrics"]["total_cases"], 6)
        self.assertEqual(result["metrics"]["passed"], 6)
        self.assertEqual(result["metrics"]["aana_bad_tool_executions"], 0)
        self.assertGreater(result["metrics"]["permissive_bad_tool_executions"], 0)
        self.assertEqual(result["metrics"]["task_success_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
