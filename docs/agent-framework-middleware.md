# Agent Framework Middleware

AANA middleware wraps a framework tool call before execution. Each wrapper
normalizes the proposed tool call into `aana.agent_tool_precheck.v1`, runs the
AANA gate, and executes only when `should_execute_tool(result)` is true.

The middleware is dependency-light: importing AANA does not require LangChain,
OpenAI Agents SDK, AutoGen, CrewAI, or an MCP SDK.

## Shared Rule

Execute the original tool call only when:

- `gate_decision == "pass"`
- `recommended_action == "accept"`
- no `hard_blockers`
- no `aix.hard_blockers`

If the gate fails, the Python wrappers raise `AANAToolExecutionBlocked`.

## LangChain

```python
import aana

guarded_tool = aana.langchain_tool_middleware(
    langchain_tool,
    metadata={
        "authorization_state": "authenticated",
        "risk_domain": "finance",
        "evidence_refs": [
            aana.tool_evidence_ref(source_id="auth.lookup", kind="auth_event", trust_tier="verified")
        ],
    },
)

result = guarded_tool.invoke({"account_id": "acct_redacted"})
```

The proxy supports common `invoke`, `ainvoke`, `run`, and `arun` tool surfaces.

## OpenAI Agents SDK

```python
import aana

@aana.openai_agents_tool_middleware(
    metadata={
        "authorization_state": "confirmed",
        "risk_domain": "customer_support",
        "evidence_refs": [
            aana.tool_evidence_ref(source_id="approval.user", kind="approval", trust_tier="verified")
        ],
    }
)
def send_customer_email(to: str, body: str):
    return {"sent": True}
```

Use the decorator around tool functions registered with the agent runtime.

## AutoGen

```python
@aana.autogen_tool_middleware(metadata={"authorization_state": "authenticated"})
def get_account_profile(account_id: str):
    return {"account_id": account_id}
```

The AutoGen wrapper is intentionally the same shape as the OpenAI tool wrapper:
decorate the callable before registration.

## CrewAI

```python
guarded = aana.crewai_tool_middleware(
    crewai_tool,
    metadata={"authorization_state": "confirmed", "risk_domain": "devops"},
)

result = guarded._run(service="api")
```

For CrewAI-style tool objects, the proxy wraps `_run` and `_arun`.

## MCP Tool Calls

```python
async def handler(arguments: dict):
    return {"ok": True}

guarded_handler = aana.mcp_tool_middleware(
    handler,
    tool_name="deploy_service",
    metadata={
        "authorization_state": "confirmed",
        "risk_domain": "devops",
        "evidence_refs": [
            aana.tool_evidence_ref(source_id="change.approval", kind="approval", trust_tier="verified")
        ],
    },
)
```

The MCP wrapper accepts either a single `arguments` dictionary or keyword
arguments, then delegates to the original handler.

## TypeScript

The TypeScript SDK exports matching dependency-light helpers:

```ts
import {
  langChainToolMiddleware,
  openAIAgentsToolMiddleware,
  autoGenToolMiddleware,
  crewAIToolMiddleware,
  mcpToolMiddleware
} from "@aana/integration-sdk";

const guarded = mcpToolMiddleware("get_public_status", (args) => ({ ok: true }));
```

The TypeScript wrappers use the same local deterministic pre-tool-call gate as
`checkToolPrecheck`.
