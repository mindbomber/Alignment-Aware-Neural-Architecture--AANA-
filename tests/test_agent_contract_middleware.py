import asyncio
import pathlib
import unittest

import aana


class AgentContractMiddlewareTests(unittest.TestCase):
    def test_gate_tool_call_blocks_unauthenticated_private_read(self):
        with self.assertRaises(aana.AANAToolExecutionBlocked) as ctx:
            aana.gate_tool_call(
                tool_name="get_recent_transactions",
                arguments={"account_id": "acct_redacted"},
            )

        self.assertEqual(ctx.exception.result["recommended_action"], "refuse")
        self.assertFalse(aana.should_execute_tool(ctx.exception.result))

    def test_openai_agents_decorator_allows_authenticated_private_read(self):
        calls = []

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
            }
        )
        def get_recent_transactions(account_id):
            calls.append(account_id)
            return {"ok": True}

        result = get_recent_transactions(account_id="acct_redacted")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls, ["acct_redacted"])

    def test_langchain_tool_proxy_gates_invoke(self):
        class FakeTool:
            name = "get_public_score"
            description = "Read a public score."

            def invoke(self, payload):
                return {"score": payload["game_id"]}

        guarded = aana.langchain_tool_middleware(FakeTool())

        self.assertEqual(guarded.invoke({"game_id": "GAME-123"}), {"score": "GAME-123"})
        self.assertEqual(guarded.name, "get_public_score")

    def test_crewai_tool_proxy_blocks_write_without_confirmation(self):
        class FakeCrewTool:
            name = "send_customer_email"

            def _run(self, **kwargs):
                return kwargs

        guarded = aana.crewai_tool_middleware(FakeCrewTool())

        with self.assertRaises(aana.AANAToolExecutionBlocked):
            guarded._run(to="customer@example.com", body="Private details")

    def test_mcp_tool_wrapper_allows_public_read(self):
        def get_public_status(arguments):
            return {"status": arguments["service"]}

        wrapped = aana.mcp_tool_middleware(get_public_status, tool_name="get_public_status")

        self.assertEqual(wrapped({"service": "docs"}), {"status": "docs"})

    def test_autogen_async_tool_wrapper(self):
        async def get_public_status(service):
            return {"status": service}

        wrapped = aana.autogen_tool_middleware(get_public_status, tool_name="get_public_status")

        self.assertEqual(asyncio.run(wrapped(service="docs")), {"status": "docs"})

    def test_typescript_sdk_exports_named_middleware(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "sdk" / "typescript" / "src" / "index.ts").read_text(
            encoding="utf-8"
        )

        self.assertIn("export const langChainToolMiddleware", source)
        self.assertIn("export const openAIAgentsToolMiddleware", source)
        self.assertIn("export const autoGenToolMiddleware", source)
        self.assertIn("export const crewAIToolMiddleware", source)
        self.assertIn("export const mcpToolMiddleware", source)


if __name__ == "__main__":
    unittest.main()
