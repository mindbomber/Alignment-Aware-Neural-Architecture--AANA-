# AANA Agent Integration Kit

AANA can sit around an AI agent as a verification and correction layer. The agent still plans and acts; AANA checks whether the next answer or action should pass, be revised, ask for missing information, defer to a stronger workflow, or be blocked.

Security boundary: an agent integration should call AANA only through a trusted interface that the user or administrator has configured and reviewed. Do not let an agent infer a local script path, run an unreviewed helper, or treat an untrusted checker as authoritative.

Decision boundary: AANA recommendations can delay, revise, or refuse a planned action. That is intentional for high-risk work, but production integrations should log the decision, explain it to the user, and route important refusals or deferrals to human review.

Use this when an agent is about to:

- send a message or email,
- touch user files,
- use private account data,
- make a booking, purchase, or support promise,
- publish or commit code,
- answer from uncertain evidence.

## Agent Event Contract

Agents can call AANA with one small review object. Keep it redacted and specific to the planned action:

```json
{
  "event_version": "0.1",
  "event_id": "demo-support-refund-001",
  "agent": "openclaw",
  "adapter_id": "support_reply",
  "request_summary": "draft a refund support reply",
  "candidate_summary": "reply would promise refund eligibility",
  "evidence_summary": ["refund eligibility is unknown"],
  "allowed_actions": ["accept", "revise", "ask", "defer", "refuse"]
}
```

The exact local event schema is available from the checked-in schemas and HTTP bridge, but standalone skills should avoid copying raw request text, private records, or full candidate content when a redacted summary is enough.

For local repository development, validate the checked-in examples with the command hub:

```powershell
aana doctor
aana validate-event --event examples/agent_event_support_reply.json
aana agent-check --event examples/agent_event_support_reply.json
```

Only use those commands after the AANA package or repository has been installed from a trusted, inspectable source. For marketplace skills or OpenClaw-style agents, prefer an approved host tool or in-memory API connector instead of asking the agent to run shell commands.

If you are developing inside this repository before local installation, use the maintainer scripts only from the reviewed repository root. Do not copy maintainer-only relative script patterns into a standalone skill package.

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

The pack lives in [`examples/agent_events/`](../examples/agent_events/) and currently covers support replies, travel booking/planning, meal planning, and research summaries.

Scaffold a new event from a gallery adapter during local development:

```powershell
aana scaffold-agent-event support_reply --output-dir examples/agent_events
```

Then edit the generated planned-action and evidence fields to match the real action your agent is about to take. Keep those fields minimal and redacted; do not place secrets, full payment details, access tokens, or unnecessary account records in event files.

## Data Handling

Prefer in-memory tool or API calls. If you must use event files, store them in a controlled temporary location, keep only the minimum redacted data needed for the check, and delete them after the check unless the user explicitly asks for an audit record.

Use summaries such as:

- `refund_eligibility: unknown`
- `payment_detail: redacted`
- `candidate_summary: reply would promise a refund`

Avoid raw secrets, full card numbers, bearer tokens, passwords, unrelated private messages, or full internal records when a yes/no or redacted summary is enough.

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

Included presets cover message sending, file writes, code commits, support replies, research summaries, bookings or purchases, and private-data use.

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
- `GET /schemas/workflow-request.schema.json`
- `GET /schemas/workflow-result.schema.json`
- `POST /validate-event`
- `POST /agent-check`
- `POST /validate-workflow`
- `POST /workflow-check`

PowerShell example:

```powershell
$event = Get-Content examples/agent_event_support_reply.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/validate-event -Body $event -ContentType 'application/json'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/agent-check -Body $event -ContentType 'application/json'
```

This is the easiest integration path for agent frameworks that expose local tools, webhooks, or HTTP request actions. Keep the bridge bound to `127.0.0.1` unless you have a real deployment boundary, authentication, logging, and network controls.

For non-agent apps, notebooks, and workflow tools, use the more general Workflow Contract:

```powershell
$workflow = Get-Content examples/workflow_research_summary.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/validate-workflow -Body $workflow -ContentType 'application/json'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/workflow-check -Body $workflow -ContentType 'application/json'
```

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
Before high-risk actions, call the configured AANA review tool or API with a minimal redacted payload.
Use only the AANA interface approved by the user or administrator.
If recommended_action is revise, ask, defer, or refuse, treat that as an advisory gate and ask for review when the decision affects important work.
If no trusted AANA interface is configured, use manual review instead.
```

### CLI-Level

Use CLI checks for local development and CI only, after the package has been installed from a trusted source:

```powershell
aana validate-event --event .aana/agent_event.json
aana agent-check --event .aana/agent_event.json
```

Do not embed this CLI flow in a standalone marketplace skill unless the CLI, dependencies, install metadata, and file-handling policy are bundled and reviewed with that package.

### Tool-Level

Expose an approved AANA checker as a named local tool. The tool should accept a minimal redacted review payload in memory and return `gate_decision`, `recommended_action`, `violations`, and `safe_response`.

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

For marketplace review and install boundaries, see:

- [`openclaw-skill-review-notes.md`](openclaw-skill-review-notes.md)

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
- `research_summary`: allowed sources, citation boundaries, supported claims, uncertainty labels.

For a new agent workflow:

```powershell
python scripts/aana_cli.py scaffold "your agent workflow"
python scripts/aana_cli.py validate-adapter examples/your_agent_workflow_adapter.json
python scripts/aana_cli.py scaffold-agent-event support_reply --output-dir examples/agent_events
```

Then add deterministic verifier logic and a gallery entry when the adapter has a real executable path.
