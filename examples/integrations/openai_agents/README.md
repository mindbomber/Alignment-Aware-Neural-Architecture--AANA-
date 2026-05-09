# OpenAI Agents SDK + AANA

This demo shows the product pattern:

```text
agent proposes -> AANA checks -> tool executes only if allowed
```

For the shortest command-first guide, see
`docs/openai-agents-quickstart.md`.

It is intentionally runnable without OpenAI credentials. The scripted path in
`demo.py` simulates the tool proposals an OpenAI agent would emit, converts each
proposal into the Agent Action Contract v1 shape, and uses AANA to decide
whether the underlying tool body can run.

## Run

```powershell
python examples/integrations/openai_agents/demo.py
python examples/integrations/openai_agents/wrapped_tools.py
```

The output includes:

- one public read that executes;
- one write that AANA blocks because it lacks explicit confirmation;
- one confirmed write that executes;
- an `executed_tool_calls` ledger proving the blocked write did not run.

`wrapped_tools.py` shows the OpenAI Agents SDK registration seam more directly:

- define ordinary Python tool functions;
- wrap each one with `@aana.openai_agents_tool_middleware(...)`;
- optionally register the guarded functions with `agents.function_tool(...)`;
- build an `Agent` with the guarded tool list when `openai-agents` is installed.

## Optional OpenAI Agents SDK Registration

When `openai-agents` is installed, `build_agent()` returns an illustrative
OpenAI Agents SDK `Agent` whose tools are already wrapped by AANA:

```python
from examples.integrations.openai_agents.demo import build_agent

agent = build_agent()
```

For the multi-tool wrapped example:

```python
from examples.integrations.openai_agents.wrapped_tools import build_agent

agent = build_agent()
```

The enforcement boundary stays inside the tool wrapper. That is the important
part: an agent may propose a side-effecting tool call, but the original tool
body is invoked only when AANA returns `accept`.

## AANA FastAPI Guard

Use `api_guard.py` when an OpenAI-powered app should call AANA over HTTP instead
of importing the Python package:

```powershell
$env:AANA_BRIDGE_TOKEN = "local-dev-secret"
python scripts/aana_fastapi.py --host 127.0.0.1 --port 8766

$env:AANA_API_URL = "http://127.0.0.1:8766"
python examples/integrations/openai_agents/api_guard.py
```

The API guard calls:

- `POST /pre-tool-check` for proposed tool calls;
- `POST /agent-check` for full agent answer/action events.

It fails closed. The wrapped tool body runs only when AANA returns `accept`,
the gate passes, there are no hard blockers or validation errors, and the
execution policy allows enforcement execution.

## Local Agent Evals

Run the local OpenAI-style agent eval harness:

```powershell
python evals/openai_agents_aana/run_local.py
```

The eval compares a permissive agent path against AANA-guarded execution for:

- unsafe tool blocking;
- private-read authorization;
- write confirmation;
- missing-evidence `ask` / `defer` / `refuse`;
- preserving safe tool execution.

Results are written to `evals/openai_agents_aana/results/latest.json`.

## Minimal Middleware Shape

Use this shape when you want to gate an OpenAI tool function by hand:

```python
import aana

def send_email(to: str, body: str):
    return {"sent": True}

def guarded_send_email(to: str, body: str):
    decision = aana.check_tool_call({
        "tool_name": "send_email",
        "tool_category": "write",
        "authorization_state": "user_claimed",
        "evidence_refs": ["draft_id:123"],
        "risk_domain": "customer_support",
        "proposed_arguments": {"to": to},
        "recommended_route": "accept",
    })

    if decision["route"] != "accept":
        return {"blocked": True, "aana": decision}

    return send_email(to=to, body=body)
```

For production wrappers, prefer `aana.openai_agents_tool_middleware(...)` or
`aana.execute_tool_if_allowed(...)` because they also apply the full execution
policy: route, gate result, hard blockers, schema validation, and audit-safe
logging.
