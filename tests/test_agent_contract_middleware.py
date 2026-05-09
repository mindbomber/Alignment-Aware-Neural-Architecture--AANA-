import asyncio
import pathlib
import shutil
import subprocess
import unittest

import aana


class AgentContractMiddlewareTests(unittest.TestCase):
    def assert_blocked_gate(self, gate):
        self.assertFalse(gate["allowed"])
        self.assertFalse(gate["execution_allowed"])
        self.assertIn("error", gate)
        self.assertEqual(gate["error"]["error_type"], "aana_tool_execution_blocked")
        self.assertIn(gate["error"]["route"], {"ask", "defer", "refuse"})
        self.assertTrue(gate["error"]["recovery_suggestion"])
        self.assertEqual(gate["error"]["execution_policy"], gate["execution_policy"])

    def test_gate_tool_call_blocks_unauthenticated_private_read(self):
        with self.assertRaises(aana.AANAToolExecutionBlocked) as ctx:
            aana.gate_tool_call(
                tool_name="get_recent_transactions",
                arguments={"account_id": "acct_redacted"},
            )

        self.assertEqual(ctx.exception.result["recommended_action"], "refuse")
        self.assertFalse(aana.should_execute_tool(ctx.exception.result))
        self.assertEqual(ctx.exception.error["error_type"], "aana_tool_execution_blocked")
        self.assertIn("recovery_suggestion", ctx.exception.error)

    def test_openai_agents_decorator_allows_authenticated_private_read(self):
        calls = []
        decisions = []

        @aana.openai_agents_tool_middleware(
            metadata={
                "authorization_state": "authenticated",
                "evidence_refs": [
                    aana.tool_evidence_ref(
                        source_id="auth.lookup",
                        kind="auth_event",
                        trust_tier="verified",
                        redaction_status="redacted",
                    )
                ],
            },
            on_decision=decisions.append,
        )
        def get_recent_transactions(account_id):
            calls.append(account_id)
            return {"ok": True}

        result = get_recent_transactions(account_id="acct_redacted")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls, ["acct_redacted"])
        self.assertTrue(decisions[0]["allowed"])
        self.assertEqual(get_recent_transactions.aana_last_gate["result"]["architecture_decision"]["route"], "accept")

    def test_wrap_agent_tool_returns_gate_when_non_raising(self):
        calls = []

        def send_customer_email(to, body):
            calls.append((to, body))
            return {"sent": True}

        guarded = aana.wrap_agent_tool(
            send_customer_email,
            metadata={"tool_category": "write", "authorization_state": "validated", "risk_domain": "customer_support"},
            raise_on_block=False,
        )

        result = guarded(to="customer@example.com", body="Needs confirmation")

        self.assert_blocked_gate(result)
        self.assertEqual(result["result"]["architecture_decision"]["route"], "ask")
        self.assertEqual(calls, [])

    def test_wrap_agent_tool_one_line_allows_inferred_public_read(self):
        def get_public_status(service):
            return {"service": service, "status": "ok"}

        guarded = aana.wrap_agent_tool(get_public_status)

        result = guarded(service="docs")

        self.assertEqual(result, {"service": "docs", "status": "ok"})
        self.assertEqual(guarded.aana_last_gate["event"]["tool_category"], "public_read")
        self.assertEqual(guarded.aana_last_gate["result"]["architecture_decision"]["route"], "accept")

    def test_wrap_agent_tool_one_line_blocks_inferred_write(self):
        calls = []

        def send_email(to, body):
            calls.append((to, body))
            return {"sent": True}

        guarded = aana.wrap_agent_tool(send_email)

        with self.assertRaises(aana.AANAToolExecutionBlocked) as ctx:
            guarded(to="customer@example.com", body="Needs confirmation")

        self.assertEqual(calls, [])
        self.assertEqual(ctx.exception.event["tool_category"], "write")
        self.assertEqual(ctx.exception.result["architecture_decision"]["route"], "refuse")
        self.assertFalse(aana.should_execute_tool(ctx.exception.result))

    def test_execute_tool_if_allowed_returns_tool_and_aana_result(self):
        output = aana.execute_tool_if_allowed(
            lambda service: {"service": service, "status": "ok"},
            tool_name="get_public_status",
            arguments={"service": "docs"},
            metadata={"tool_category": "public_read", "authorization_state": "none", "risk_domain": "public_information"},
        )

        self.assertEqual(output["tool_result"], {"service": "docs", "status": "ok"})
        self.assertEqual(output["aana"]["route"], "accept")

    def test_execute_tool_if_allowed_blocks_without_execution_when_non_raising(self):
        calls = []

        def send_email(to):
            calls.append(to)
            return {"sent": True}

        output = aana.execute_tool_if_allowed(
            send_email,
            tool_name="send_email",
            arguments={"to": "customer@example.com"},
            metadata={"tool_category": "write", "authorization_state": "user_claimed", "risk_domain": "customer_support"},
            raise_on_block=False,
        )

        self.assertEqual(calls, [])
        self.assertIsNone(output["tool_result"])
        self.assert_blocked_gate(output["gate"])
        self.assertEqual(output["error"], output["gate"]["error"])

    def test_langchain_tool_proxy_gates_invoke(self):
        class FakeTool:
            name = "get_public_score"
            description = "Read a public score."

            def invoke(self, payload):
                return {"score": payload["game_id"]}

        guarded = aana.langchain_tool_middleware(FakeTool())

        self.assertEqual(guarded.invoke({"game_id": "GAME-123"}), {"score": "GAME-123"})
        self.assertEqual(guarded.name, "get_public_score")
        self.assertEqual(guarded.aana_last_gate["result"]["architecture_decision"]["route"], "accept")

    def test_langchain_tool_proxy_blocks_invoke_without_execution(self):
        calls = []

        class FakeTool:
            name = "send_customer_email"

            def invoke(self, payload):
                calls.append(payload)
                return {"sent": True}

        guarded = aana.langchain_tool_middleware(
            FakeTool(),
            metadata={"tool_category": "write", "authorization_state": "user_claimed", "risk_domain": "customer_support"},
            raise_on_block=False,
        )

        result = guarded.invoke({"to": "customer@example.com"})

        self.assertEqual(calls, [])
        self.assert_blocked_gate(result)

    def test_crewai_tool_proxy_blocks_write_without_confirmation(self):
        class FakeCrewTool:
            name = "send_customer_email"

            def _run(self, **kwargs):
                return kwargs

        guarded = aana.crewai_tool_middleware(FakeCrewTool())

        with self.assertRaises(aana.AANAToolExecutionBlocked):
            guarded._run(to="customer@example.com", body="Private details")

    def test_crewai_tool_proxy_blocks_without_execution_when_non_raising(self):
        calls = []

        class FakeCrewTool:
            name = "send_customer_email"

            def _run(self, **kwargs):
                calls.append(kwargs)
                return {"sent": True}

        guarded = aana.crewai_tool_middleware(
            FakeCrewTool(),
            metadata={"tool_category": "write", "authorization_state": "user_claimed", "risk_domain": "customer_support"},
            raise_on_block=False,
        )

        result = guarded._run(to="customer@example.com")

        self.assertEqual(calls, [])
        self.assert_blocked_gate(result)

    def test_mcp_tool_wrapper_allows_public_read(self):
        def get_public_status(arguments):
            return {"status": arguments["service"]}

        wrapped = aana.mcp_tool_middleware(get_public_status, tool_name="get_public_status")

        self.assertEqual(wrapped({"service": "docs"}), {"status": "docs"})

    def test_mcp_tool_wrapper_blocks_without_execution_when_non_raising(self):
        calls = []

        def send_email(arguments):
            calls.append(arguments)
            return {"sent": True}

        wrapped = aana.mcp_tool_middleware(
            send_email,
            tool_name="send_email",
            metadata={"tool_category": "write", "authorization_state": "user_claimed", "risk_domain": "customer_support"},
            raise_on_block=False,
        )

        result = wrapped({"to": "customer@example.com"})

        self.assertEqual(calls, [])
        self.assert_blocked_gate(result)

    def test_autogen_async_tool_wrapper(self):
        async def get_public_status(service):
            return {"status": service}

        wrapped = aana.autogen_tool_middleware(get_public_status, tool_name="get_public_status")

        self.assertEqual(asyncio.run(wrapped(service="docs")), {"status": "docs"})

    def test_autogen_async_tool_wrapper_blocks_without_execution(self):
        calls = []

        async def send_email(to):
            calls.append(to)
            return {"sent": True}

        wrapped = aana.autogen_tool_middleware(
            send_email,
            tool_name="send_email",
            metadata={"tool_category": "write", "authorization_state": "user_claimed", "risk_domain": "customer_support"},
            raise_on_block=False,
        )

        result = asyncio.run(wrapped(to="customer@example.com"))

        self.assertEqual(calls, [])
        self.assert_blocked_gate(result)

    def test_openai_agents_decorator_blocks_without_execution(self):
        calls = []

        @aana.openai_agents_tool_middleware(
            metadata={"tool_category": "write", "authorization_state": "user_claimed", "risk_domain": "customer_support"},
            raise_on_block=False,
        )
        def send_email(to):
            calls.append(to)
            return {"sent": True}

        result = send_email(to="customer@example.com")

        self.assertEqual(calls, [])
        self.assert_blocked_gate(result)

    def test_typescript_guard_blocks_without_execution_when_available(self):
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        node = shutil.which("node.exe") or shutil.which("node")
        if npm is None or node is None:
            self.skipTest("npm/node is not available")
        root = pathlib.Path(__file__).resolve().parents[1]
        subprocess.run([npm, "run", "build"], cwd=root / "sdk" / "typescript", check=True, capture_output=True, text=True)
        script = """
            import { guardToolFunction } from './dist/index.js';
            const calls = [];
            const guarded = guardToolFunction(
              'send_email',
              (payload) => { calls.push(payload); return { sent: true }; },
              { tool_category: 'write', authorization_state: 'user_claimed', risk_domain: 'customer_support' },
              { raiseOnBlock: false }
            );
            const result = guarded({ to: 'customer@example.com' });
            if (calls.length !== 0) throw new Error('wrapped TypeScript tool executed after AANA block');
            if (!result.error || result.error.error_type !== 'aana_tool_execution_blocked') throw new Error('missing standardized middleware error');
            if (result.execution_allowed !== false) throw new Error('blocked gate should not allow execution');
        """
        subprocess.run([node, "--input-type=module", "-e", script], cwd=root / "sdk" / "typescript", check=True, capture_output=True, text=True)

    def test_typescript_sdk_exports_named_middleware(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "sdk" / "typescript" / "src" / "index.ts").read_text(
            encoding="utf-8"
        )

        self.assertIn("export const langChainToolMiddleware", source)
        self.assertIn("export const openAIAgentsToolMiddleware", source)
        self.assertIn("export const autoGenToolMiddleware", source)
        self.assertIn("export const crewAIToolMiddleware", source)
        self.assertIn("export const mcpToolMiddleware", source)
        self.assertIn("export const wrapAgentTool", source)
        self.assertIn("architectureDecision", source)
        self.assertIn("middlewareError", source)


if __name__ == "__main__":
    unittest.main()
