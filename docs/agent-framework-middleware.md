# Agent Framework Middleware

AANA middleware wraps a framework tool call before execution. Each wrapper
normalizes the proposed tool call into `aana.agent_tool_precheck.v1`, runs the
AANA gate, and executes only when `should_execute_tool(result)` is true.

The product pattern is:

```text
agent proposes -> AANA checks -> agent executes only if allowed
```

The middleware is dependency-light: importing AANA does not require LangChain,
OpenAI Agents SDK, AutoGen, CrewAI, or an MCP SDK.

Runnable examples for every integration surface are in
`examples/integrations/`:

- `openai_agents_sdk.py`
- `openai_agents/demo.py`
- `langchain.py`
- `autogen.py`
- `crewai.py`
- `mcp.py`

For the OpenAI-specific path, use the [OpenAI Agents Quickstart](openai-agents-quickstart.md).

## Shared Rule

In enforcement mode, execute the original tool call only when:

- `gate_decision == "pass"`
- `recommended_action == "accept"`
- `architecture_decision.route == "accept"`
- no `hard_blockers`
- no `aix.hard_blockers`
- no schema or contract validation errors

This is the uniform AANA route rule across CLI, SDK, API, and middleware:
only `accept` can execute. `revise`, `retrieve`, `ask`, `defer`, and `refuse`
must not call the wrapped tool body.

Schema errors, missing authorization, unknown tools, malformed evidence, and
non-`accept` routes fail closed. If the gate fails, the Python wrappers raise
`AANAToolExecutionBlocked`.
Set `raise_on_block=False` when the agent runtime should receive the blocked
gate result instead of an exception. Each wrapper stores the latest decision in
`aana_last_gate`, and every gate result includes `architecture_decision` with
the parity shape used by CLI, Python SDK, TypeScript SDK, FastAPI, MCP, and
middleware: `route`, `aix_score`, `hard_blockers`, `missing_evidence`,
`authorization_state`, `recovery_suggestion`, and `audit_event`.

Blocked wrapper results are standardized across plain Python, OpenAI Agents SDK,
LangChain, AutoGen, CrewAI, MCP, and TypeScript wrappers:

```json
{
  "error_type": "aana_tool_execution_blocked",
  "code": "hard_blockers_present",
  "route": "ask",
  "hard_blockers": ["write_missing_explicit_confirmation"],
  "recovery_suggestion": "Ask the user or runtime for the missing authorization, confirmation, or evidence before execution.",
  "execution_policy": {"mode": "enforce", "execution_allowed": false}
}
```

When `raise_on_block=True`, the same object is available as
`AANAToolExecutionBlocked.error`. When `raise_on_block=False`, it is returned as
`gate["error"]`, and the wrapped tool body is not called.

Shadow mode is explicit observe-only mode. It records the AANA would-route and
lets the host application continue, but `allowed` remains false when AANA would
block. Use `execution_allowed` and `execution_policy` to distinguish enforcement
permission from shadow-mode production continuation.

## Plain Python SDK

```python
import aana

def get_public_status(service: str):
    return {"service": service, "status": "ok"}

guarded = aana.wrap_agent_tool(get_public_status)

result = guarded(service="docs")
decision = guarded.aana_last_gate["result"]["architecture_decision"]
```

The one-line wrapper infers common public reads, private reads, and writes from
the tool name and arguments. For example, `get_public_status` is allowed as a
public read, while `send_email` is treated as a write and blocked until the
runtime provides stronger authorization/confirmation evidence.

For consequential tools, pass metadata when registering the wrapper:

```python
guarded_send = aana.wrap_agent_tool(
    send_email,
    metadata={
        "tool_category": "write",
        "authorization_state": "confirmed",
        "risk_domain": "customer_support",
        "evidence_refs": [
            aana.tool_evidence_ref(source_id="approval.user", kind="approval", trust_tier="verified")
        ],
    },
)
```

For one-off calls that should return both the tool output and AANA decision:

```python
payload = aana.execute_tool_if_allowed(
    get_public_status,
    tool_name="get_public_status",
    arguments={"service": "docs"},
    metadata={"tool_category": "public_read", "authorization_state": "none"},
)
```

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
For a manual OpenAI tool wrapper, the quickstart shape is:

```python
decision = aana.check_tool_call({
    "tool_name": "send_email",
    "tool_category": "write",
    "authorization_state": "user_claimed",
    "evidence_refs": ["draft_id:123"],
    "risk_domain": "customer_support",
    "proposed_arguments": {"to": "customer@example.com"},
    "recommended_route": "accept",
})

if not aana.should_execute_tool(decision):
    return {"blocked": True, "aana": decision}
```

The production wrappers use the same `execution_policy`, so they also block
schema errors, hard blockers, and malformed evidence even if a route alias is
present.
For a repo-owned enforcement proof, run:

```powershell
python examples/integrations/openai_agents/demo.py
python examples/integrations/openai_agents/wrapped_tools.py
```

That demo simulates OpenAI-style tool proposals, gates each proposal through
AANA, and prints a side-effect ledger showing that the blocked write proposal
never reached the original `send_customer_email` body.
The wrapped-tools example shows the direct SDK seam: guarded Python callables are
registered with `agents.function_tool(...)` only after AANA middleware is
attached.

For OpenAI-powered apps that should call AANA as a service instead of importing
the Python package, use the HTTP guard:

```powershell
python examples/integrations/openai_agents/api_guard.py
```

It calls `POST /pre-tool-check` and executes the wrapped tool only when the API
route and execution policy allow enforcement execution.

To evaluate the OpenAI-style guarded-tool path:

```powershell
python evals/openai_agents_aana/run_local.py
```

The eval checks unsafe-action blocking, private-read authorization, write
confirmation, missing-evidence routing, and safe task success against a
permissive baseline.

To evaluate AANA-controlled agents across SDK, FastAPI, and MCP surfaces:

```powershell
python evals/aana_controlled_agents/run_local.py
```

That harness uses the same proposed tool calls across all surfaces and reports
unsafe executions, route accuracy, execution accuracy, and safe preservation.

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

AANA also exposes a standard MCP-style tool named `aana_pre_tool_check` for
agents that should ask AANA before executing consequential actions:

```powershell
python scripts/aana_mcp_server.py --list-tools
```

See [AANA MCP / ChatGPT App Direction](aana-mcp-chatgpt-app.md).

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
`checkToolPrecheck` and expose `architecture_decision` on the result. See
`examples/sdk/agent_wrapping_examples.ts` and
`examples/sdk/agent_wrapping_examples.py` for complete framework-neutral
wrapping examples.
