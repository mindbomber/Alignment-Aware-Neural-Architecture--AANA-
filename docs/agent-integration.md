# AANA Agent Integration Kit

AANA can sit around an AI agent as a verification and correction layer. The agent still plans and acts; AANA checks whether the next answer or action should pass, be revised, ask for missing information, defer to a stronger workflow, or be blocked.

Use this when an agent is about to:

- send a message or email,
- touch user files,
- use private account data,
- make a booking, purchase, or support promise,
- publish or commit code,
- answer from uncertain evidence.

## Agent Event Contract

Agents can call AANA with one JSON object:

```json
{
  "event_version": "0.1",
  "event_id": "demo-support-refund-001",
  "agent": "openclaw",
  "adapter_id": "support_reply",
  "user_request": "Draft a customer-support reply...",
  "candidate_action": "Hi Maya, order #A1842 is eligible...",
  "available_evidence": ["Customer name: Maya Chen"],
  "allowed_actions": ["accept", "revise", "ask", "defer", "refuse"]
}
```

Run the check:

```powershell
python scripts/aana_cli.py validate-event --event examples/agent_event_support_reply.json
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json
```

If the repo is installed with `python -m pip install -e .`, the same flow is:

```powershell
aana validate-event --event examples/agent_event_support_reply.json
aana agent-check --event examples/agent_event_support_reply.json
```

The output includes:

- `gate_decision`
- `candidate_gate`
- `recommended_action`
- `violations`
- `safe_response`
- the full adapter result

Print the versioned schemas when you need to wire another agent framework:

```powershell
python scripts/aana_cli.py agent-schema
python scripts/aana_cli.py agent-schema agent_event
python scripts/aana_cli.py agent-schema agent_check_result
```

Run the executable agent-event pack:

```powershell
python scripts/aana_cli.py run-agent-examples
```

The pack lives in [`examples/agent_events/`](../examples/agent_events/) and currently covers support replies, travel booking/planning, and meal planning.

Scaffold a new event from a gallery adapter:

```powershell
python scripts/aana_cli.py scaffold-agent-event support_reply --output-dir examples/agent_events
```

Then edit the generated `candidate_action` and `available_evidence` fields to match the real action your agent is about to take.

## Python API

Agents that can call Python directly do not need to shell out to the CLI. Import the small API shim and pass the same event object:

```python
from eval_pipeline.agent_api import check_event

result = check_event(event)
if result["gate_decision"] == "pass":
    send(result["safe_response"])
else:
    follow(result["recommended_action"])
```

A runnable example is included at:

- [`examples/agent_api_usage.py`](../examples/agent_api_usage.py)

Run it with:

```powershell
python examples/agent_api_usage.py
```

## Policy Presets

Policy presets name common places where an agent should call AANA before acting. They are not a full permission system; they are a starter map for deciding which workflows need a gate.

```powershell
python scripts/aana_cli.py policy-presets
python scripts/aana_cli.py policy-presets --json
```

Included presets cover message sending, file writes, code commits, support replies, bookings or purchases, and private-data use.

## Local HTTP Bridge

Agents that work best with HTTP tools can run AANA as a local bridge:

```powershell
python scripts/aana_server.py --host 127.0.0.1 --port 8765
```

If the package is installed locally, the same bridge is available as:

```powershell
aana-server --host 127.0.0.1 --port 8765
```

Available routes:

- `GET /health`
- `GET /policy-presets`
- `GET /openapi.json`
- `GET /schemas`
- `GET /schemas/agent-event.schema.json`
- `GET /schemas/agent-check-result.schema.json`
- `POST /validate-event`
- `POST /agent-check`

PowerShell example:

```powershell
$event = Get-Content examples/agent_event_support_reply.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/validate-event -Body $event -ContentType 'application/json'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/agent-check -Body $event -ContentType 'application/json'
```

This is the easiest integration path for agent frameworks that expose local tools, webhooks, or HTTP request actions. Keep the bridge bound to `127.0.0.1` unless you have a real deployment boundary, authentication, logging, and network controls.

The OpenAPI route is useful for tools that can import an HTTP contract:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/openapi.json
```

The schema routes are useful for tools that want only the event or result shape:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/schemas/agent-event.schema.json
Invoke-RestMethod http://127.0.0.1:8765/schemas/agent-check-result.schema.json
```

## Integration Patterns

### Prompt-Level

Add an instruction to the agent:

```text
Before high-risk actions, create an AANA agent event and run:
python scripts/aana_cli.py agent-check --event <event.json>
Only proceed when gate_decision is pass. If recommended_action is revise, ask, defer, or refuse, follow that action instead of executing the original candidate.
```

### CLI-Level

Have the agent write an event file and call:

```powershell
python scripts/aana_cli.py validate-event --event .aana/agent_event.json
python scripts/aana_cli.py agent-check --event .aana/agent_event.json
```

### Tool-Level

Expose `aana_cli.py agent-check` as a local tool. The agent sends its planned action as `candidate_action` and receives a gate result before execution.

### HTTP-Level

Expose the local bridge as an agent tool:

```text
POST http://127.0.0.1:8765/validate-event
Content-Type: application/json
Body: the AANA agent event

POST http://127.0.0.1:8765/agent-check
Content-Type: application/json
Body: the AANA agent event
```

Use `/validate-event` to catch malformed events before execution. The `/agent-check` response shape matches the CLI and Python API: `gate_decision`, `recommended_action`, `violations`, `safe_response`, and the full adapter result.

For tools that ingest OpenAPI, point them at:

```text
http://127.0.0.1:8765/openapi.json
```

For tools that ingest JSON Schema directly, use:

```text
http://127.0.0.1:8765/schemas/agent-event.schema.json
http://127.0.0.1:8765/schemas/agent-check-result.schema.json
```

## OpenClaw-Style Setup

For OpenClaw-style agents, place an AANA guardrail skill in the agent workspace and tell the agent when to call AANA. A starter skill is included at:

- [`examples/openclaw/aana-guardrail-skill/SKILL.md`](../examples/openclaw/aana-guardrail-skill/SKILL.md)

The practical rule is:

> AANA is not a replacement for the agent. AANA is the verification and correction layer the agent calls before risky outputs or actions.

## Choosing An Adapter

Use the existing gallery adapters first:

```powershell
python scripts/aana_cli.py list
```

Current runnable adapters:

- `travel_planning`: budget, transport, lunch, ticket caps.
- `meal_planning`: grocery budget, dietary exclusions, day coverage.
- `support_reply`: verified account facts, private data minimization, secure routing.

For a new agent workflow:

```powershell
python scripts/aana_cli.py scaffold "your agent workflow"
python scripts/aana_cli.py validate-adapter examples/your_agent_workflow_adapter.json
python scripts/aana_cli.py scaffold-agent-event support_reply --output-dir examples/agent_events
```

Then add deterministic verifier logic and a gallery entry when the adapter has a real executable path.
