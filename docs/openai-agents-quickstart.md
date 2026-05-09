# OpenAI Agents Quickstart

Use AANA as a control layer around OpenAI-style agents:

```text
agent proposes -> AANA checks -> tool executes only if allowed
```

This quickstart does not require OpenAI credentials. The examples use the same
tool-call shapes an OpenAI Agents SDK app would register with `function_tool`.

## 1. Wrap A Tool

Run the wrapped-tools example:

```powershell
python examples/integrations/openai_agents/wrapped_tools.py
```

Expected output:

- `get_public_status`: route `accept`, executed.
- `get_customer_profile`: route `accept`, executed after authenticated evidence.
- `send_customer_email_without_confirmation`: route `ask`, not executed.
- `send_customer_email_confirmed`: route `accept`, executed.
- `blocked_write_executed`: `false`.

The OpenAI Agents SDK seam is:

```python
import aana

@aana.openai_agents_tool_middleware(
    tool_name="send_customer_email",
    metadata={
        "tool_category": "write",
        "authorization_state": "confirmed",
        "risk_domain": "customer_support",
        "evidence_refs": [
            aana.tool_evidence_ref(
                source_id="approval.user.confirmed_send",
                kind="approval",
                trust_tier="verified",
                redaction_status="redacted",
            )
        ],
    },
)
def send_customer_email(to: str, body: str):
    return {"sent": True, "to": to}
```

When `openai-agents` is installed, register the guarded callable:

```python
from agents import Agent, function_tool

agent = Agent(
    name="AANA guarded agent",
    instructions="Use tools normally; AANA enforces before tool execution.",
    tools=[function_tool(send_customer_email)],
)
```

## 2. Call AANA Over FastAPI

Start AANA as a local policy service:

`POST /pre-tool-check` accepts the frozen Agent Action Contract v1 request
fields: `tool_name`, `tool_category`, `authorization_state`, `evidence_refs`,
`risk_domain`, `proposed_arguments`, and `recommended_route`.

```powershell
$env:AANA_BRIDGE_TOKEN = "local-dev-secret"
python scripts/aana_fastapi.py --host 127.0.0.1 --port 8766 --audit-log eval_outputs/audit/aana-fastapi.jsonl
```

In another terminal, call `/pre-tool-check`:

```powershell
$body = Get-Content examples/api/pre_tool_check_write_ask.json -Raw

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8766/pre-tool-check `
  -Headers @{ Authorization = "Bearer $env:AANA_BRIDGE_TOKEN" } `
  -Body $body `
  -ContentType "application/json"
```

Expected output:

- `route`: `ask`
- `execution_policy.execution_allowed`: `false`
- audit record appended to `eval_outputs/audit/aana-fastapi.jsonl`

Confirmed write:

```powershell
$body = Get-Content examples/api/pre_tool_check_confirmed_write.json -Raw

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8766/pre-tool-check `
  -Headers @{ Authorization = "Bearer $env:AANA_BRIDGE_TOKEN" } `
  -Body $body `
  -ContentType "application/json"
```

Expected output:

- `route`: `accept`
- `execution_policy.execution_allowed`: `true`

For an HTTP-only OpenAI app wrapper:

```powershell
$env:AANA_API_URL = "http://127.0.0.1:8766"
python examples/integrations/openai_agents/api_guard.py
```

Expected output: a blocked envelope for the unconfirmed email write.

## 3. Optional OpenAI Semantic Verifier

Deterministic AANA remains the default. For subtle grounded-QA or ambiguous
tool-use cases, enable an optional OpenAI-backed semantic verifier that can
tighten the route but cannot bypass deterministic schema, authorization, or hard
blockers.

Grounded-QA held-out smoke:

```powershell
$env:OPENAI_API_KEY = "<your key>"
python scripts/run_grounded_qa_hf_experiment.py --max-rows-per-source 2 --semantic-verifier openai --output eval_outputs/grounded_qa_hf_experiment_results.semantic_openai_smoke.json
```

Calibrate before enabling. The calibration path uses claim-level entailment:
the semantic verifier must return per-claim labels and unsupported claim types,
and AANA only accepts the semantic judgment when the calibrated policy preserves
safe allow.

```powershell
python scripts/run_grounded_qa_semantic_calibration.py --calibration-rows-per-source 12 --heldout-rows-per-source 20
```

Expected output includes `deployment_recommendation.status`. Keep the semantic
policy disabled unless held-out safe allow meets the configured target and
unsupported-claim recall improves over deterministic AANA.

Pre-tool-call v2 with semantic verifier:

```powershell
python scripts/aana_cli.py pre-tool-check --event examples/api/pre_tool_check_write_ask.json --gate-version v2 --semantic-verifier openai
```

Expected behavior:

- OpenAI can identify semantic grounding or tool-use ambiguity.
- AANA records the semantic result as audit-safe metadata.
- Only AANA route `accept` can execute.
- Semantic verifier output can block, ask, defer, or revise, but it cannot turn a deterministic blocker into execution.

## 4. Use MCP / ChatGPT App Prototype

List the MCP-style AANA tool:

```powershell
python scripts/aana_mcp_server.py --list-tools
```

Expected output:

- tool name: `aana_pre_tool_check`
- annotations: `readOnlyHint: true`, `destructiveHint: false`
- input schema with Agent Action Contract v1 fields

Run the ChatGPT Apps-style prototype:

```powershell
python examples/chatgpt_app/aana_mcp_app.py
```

Expected local endpoints:

- `GET http://127.0.0.1:8770/health`
- `POST http://127.0.0.1:8770/mcp`
- `GET http://127.0.0.1:8770/aana-decision.html`

For ChatGPT Developer Mode testing, expose the local server through an HTTPS
tunnel and connect ChatGPT to:

```text
https://<your-tunnel>/mcp
```

This prototype is not submission-ready. It is a local integration scaffold for
the standard `aana_pre_tool_check` control point.

## 5. Run Eval Harnesses

OpenAI-style guarded-tool eval:

```powershell
python evals/openai_agents_aana/run_local.py
```

Expected output:

- `aana_bad_tool_executions`: `0`
- `permissive_bad_tool_executions`: greater than `0`
- `task_success_rate`: `1.0`

Multi-surface controlled-agent eval:

```powershell
python evals/aana_controlled_agents/run_local.py
```

Expected output:

- `all_controlled_passed`: `true`
- `controlled_unsafe_executions.sdk`: `0`
- `controlled_unsafe_executions.api`: `0`
- `controlled_unsafe_executions.mcp`: `0`
- `permissive_unsafe_executions`: greater than `0`

## 6. Validate The Whole Integration Stack

Run the single integration validator:

```powershell
python scripts/validate_agent_integrations.py
```

It checks:

- CLI decision-shape smoke;
- Python SDK smoke;
- TypeScript SDK smoke;
- OpenAI Agents SDK wrapped-tools smoke;
- LangChain middleware smoke;
- AutoGen middleware smoke;
- CrewAI middleware smoke;
- middleware decision-shape smoke;
- FastAPI policy-service smoke;
- MCP tool smoke;
- MCP decision-shape smoke;
- controlled-agent eval harness.

Expected output:

```text
pass -- passed=12/12
- pass: cli_decision_shape_smoke
- pass: python_sdk_smoke
- pass: typescript_sdk_smoke
- pass: openai_wrapped_tools_smoke
- pass: langchain_middleware_smoke
- pass: autogen_middleware_smoke
- pass: crewai_middleware_smoke
- pass: middleware_decision_shape_smoke
- pass: fastapi_policy_service_smoke
- pass: mcp_tool_smoke
- pass: mcp_decision_shape_smoke
- pass: controlled_agent_eval_harness
```

For machine-readable output:

```powershell
python scripts/validate_agent_integrations.py --json
```

## Rule To Preserve

AANA is not the agent. The agent proposes. AANA checks. The runtime executes
only when AANA returns a true `accept` decision with no hard blockers or schema
errors.
