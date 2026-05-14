# AANA Agent Integration Kit

Canonical entry point: [Integrate Runtime](integrate-runtime/index.md). Treat the Agent Event Contract as the stable integration boundary for agent checks.

AANA can sit around an AI agent as a verification and correction layer. The agent still plans and acts; AANA checks whether the next answer or action should pass, be revised, ask for missing information, defer to a stronger workflow, or be blocked.

Fastest path: [Agent Action Contract Quickstart](agent-action-contract-quickstart.md).

The Agent Event Contract is one of AANA's two primary public APIs, alongside the Workflow Contract. Agent integrations should build and validate Agent Event payloads, then call the Python API, CLI, or HTTP bridge that accepts that payload. They should not depend on adapter runner internals, verifier helper names, or repair-policy implementation details.

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
  "user_request": "Draft a refund support reply using verified account facts only.",
  "candidate_action": "Promise a full refund even though eligibility is unknown.",
  "available_evidence": [
    {
      "source_id": "crm-record",
      "retrieved_at": "2026-05-05T00:00:00Z",
      "trust_tier": "verified",
      "redaction_status": "redacted",
      "text": "Refund eligibility is unknown."
    }
  ],
  "allowed_actions": ["accept", "revise", "ask", "defer", "refuse"]
}
```

The exact local event schema is available from the checked-in schemas and HTTP bridge, but standalone skills should avoid copying private records, secrets, or full candidate content when a redacted summary is enough.

Stable field reference:

- `agent_event` version: `event_version: "0.1"`.
- Required event fields: `user_request` plus either `adapter_id` or `workflow`.
- Optional event fields: `event_version`, `event_id`, `agent`, `candidate_action`, `candidate_answer`, `draft_response`, `available_evidence`, `allowed_actions`, and `metadata`.
- `agent_check_result` version: `agent_check_version: "0.1"`.
- Required result fields: `agent_check_version`, `adapter_id`, `gate_decision`, `recommended_action`, `safe_response`, and `audit_summary`.
- Public result shape: `gate_decision`, `recommended_action`, `violations`, `aix`, `candidate_aix`, `audit_summary`, and safe output in `safe_response`.
- Adapter IDs are the catalog IDs exposed by the adapter gallery, such as `support_reply`, `crm_support_reply`, `email_send_guardrail`, `ticket_update_checker`, and `research_summary`.
- Evidence may be a string or a structured object. Structured evidence requires `text`; `source_id`, `retrieved_at`, `trust_tier`, and `redaction_status` are optional but recommended for pilot and production-like integrations.
- `runtime.py`, `legacy_runner.py`, verifier modules, adapter JSON internals, repair policies, and runner helper functions are implementation details. Agent integrations should call the Agent Event or Workflow Contract surfaces instead.

The hardened Agent Event Contract validates:

- `candidate_action`, `candidate_answer`, and `draft_response` shape and ambiguity.
- `available_evidence` strings or structured evidence objects.
- `allowed_actions` values, non-empty lists, and duplicate actions.
- route mismatch when both `adapter_id` and `workflow` are present.
- `metadata.policy_preset` compatibility with known policy presets.
- structured evidence `source_id`, `trust_tier`, `redaction_status`, and `retrieved_at` freshness when an evidence registry is supplied.

For local repository development, validate the checked-in examples with the command hub:

```powershell
aana doctor
aana validate-event --event examples/agent_event_support_reply.json
aana validate-event --event examples/agent_events/research_summary.json --evidence-registry examples/evidence_registry.json
aana agent-check --event examples/agent_event_support_reply.json
```

Only use those commands after the AANA package or repository has been installed from a trusted, inspectable source. For marketplace skills or OpenClaw-style agents, prefer an approved host tool or in-memory API connector instead of asking the agent to run shell commands.

If you are developing inside this repository before local installation, use the maintainer scripts only from the reviewed repository root. Do not copy maintainer-only relative script patterns into a standalone skill package.

The output includes:

- `gate_decision`
- `candidate_gate`
- `recommended_action`
- `aix`
- `candidate_aix`
- `violations`
- `safe_response`
- `audit_summary`
- the full adapter result

`aix` is the score-derived Alignment Index for the final gated output. `candidate_aix` is the same score block for the proposed candidate when a candidate was supplied. Treat `aix.decision=accept` as actionable only when `gate_decision` is `pass`, `recommended_action` permits proceeding, and `aix.hard_blockers` is empty.

Agent, Workflow, SDK, CLI, HTTP bridge, and playground surfaces all route through the same contract runtime. Agent surfaces return Agent Check fields such as `safe_response`; workflow surfaces return Workflow Result fields such as `output`. The decision fields are intentionally aligned across both: `gate_decision`, `recommended_action`, `candidate_gate`, `aix`, `candidate_aix`, `violations`, and `audit_summary`.

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

Contract fixtures for valid and invalid Agent Events live in [`examples/agent_event_contract_fixtures.json`](../examples/agent_event_contract_fixtures.json). They cover route examples for `accept`, `revise`, `ask`, `defer`, and `refuse`, plus invalid cases for missing routes, malformed candidates, unsupported actions, unknown policy presets, and unapproved evidence sources.

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
if (
    result["gate_decision"] == "pass"
    and result["recommended_action"] == "accept"
    and result["aix"]["decision"] == "accept"
):
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

## Local HTTP Service

Agents that work best with HTTP tools can run AANA as the installed FastAPI policy service:

```powershell
aana-fastapi --host 127.0.0.1 --port 8766 --audit-log eval_outputs/audit/aana-fastapi.jsonl --rate-limit-per-minute 120
```

For production-like local use, set `AANA_BRIDGE_TOKEN` before starting the service. POST routes then require either `Authorization: Bearer <token>` or `X-AANA-Token: <token>`. The service rejects oversized POST bodies by default at `65536` bytes; use `--max-request-bytes` only when the deployment has a reviewed reason to change that limit. `--rate-limit-per-minute` adds a process-local per-client POST limit. With `--audit-log`, successful `/agent-check`, `/workflow-check`, and `/workflow-batch` calls append redacted audit records from the service process.

Use `GET /ready` before routing traffic. See [`fastapi-service.md`](fastapi-service.md) for public service startup, auth, structured error payloads, audit append guarantees, request-size limits, and deployment guidance. The legacy [`http-bridge-runbook.md`](http-bridge-runbook.md) covers `python scripts/aana_server.py` for repo-local playground, dashboard, and local demo workflows.

For audit trails, call `eval_pipeline.agent_api.audit_event_check(event, result)` after `check_event(event)`. The audit record keeps event IDs, adapter IDs, decisions, recommended actions, AIx score summaries, violation codes, and SHA-256 fingerprints, but excludes raw user requests, planned actions, evidence, and safe responses.

The CLI can append the same redacted audit record to JSONL:

```powershell
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py audit-summary --audit-log eval_outputs/audit/aana-audit.jsonl
```

Before connecting a real agent deployment, validate the selected operating gates:

```powershell
python scripts/aana_cli.py production-preflight
python scripts/aana_cli.py validate-deployment --deployment-manifest path/to/your-production-deployment.json
python scripts/aana_cli.py validate-governance --governance-policy path/to/your-governance-policy.json
python scripts/aana_cli.py validate-observability --observability-policy examples/observability_policy.json
python scripts/aana_cli.py release-check --deployment-manifest path/to/your-production-deployment.json --governance-policy path/to/your-governance-policy.json --observability-policy path/to/your-observability-policy.json
```

If the package is installed locally, the service is available as:

```powershell
aana-fastapi --host 127.0.0.1 --port 8766
```

Available routes:

- `GET /health`
- `GET /openapi.json`
- `GET /docs`
- `POST /validate-event`
- `POST /agent-check`
- `POST /validate-workflow`
- `POST /workflow-check`

PowerShell example:

```powershell
$event = Get-Content examples/agent_event_support_reply.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8766/validate-event -Body $event -ContentType 'application/json'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8766/agent-check -Body $event -ContentType 'application/json'
```

This is the easiest integration path for agent frameworks that expose local tools, webhooks, or HTTP request actions. Keep the service bound to `127.0.0.1` unless you have a real deployment boundary, authentication, logging, and network controls.

For non-agent apps, notebooks, and workflow tools, use the more general Workflow Contract:

```powershell
$workflow = Get-Content examples/workflow_research_summary.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8766/validate-workflow -Body $workflow -ContentType 'application/json'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8766/workflow-check -Body $workflow -ContentType 'application/json'
```

The OpenAPI route is useful for tools that can import an HTTP contract:

```powershell
Invoke-RestMethod http://127.0.0.1:8766/openapi.json
```

OpenClaw-style no-code and low-code entry points are documented in:

- [`openclaw-skill-conformance.md`](openclaw-skill-conformance.md)
- [`openclaw-plugin-install-use.md`](openclaw-plugin-install-use.md)
- [`../examples/openclaw/high-risk-workflow-examples.json`](../examples/openclaw/high-risk-workflow-examples.json)

## Integration Patterns

### Prompt-Level

Add an instruction to the agent:

```text
Before high-risk actions, call the configured AANA review tool or API with a minimal redacted payload.
Use only the AANA interface approved by the user or administrator.
If recommended_action is revise, ask, defer, or refuse, treat that as an advisory gate and ask for review when the decision affects important work.
If the result includes aix, use aix.decision as the score-derived route and never proceed when aix.hard_blockers is non-empty.
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

Expose an approved AANA checker as a named local tool. The tool should accept a minimal redacted review payload in memory and return `gate_decision`, `recommended_action`, `aix`, `violations`, and `safe_response`.

### HTTP-Level

Expose the local bridge as an agent tool:

```text
POST http://127.0.0.1:8766/validate-event
Content-Type: application/json
Body: the AANA agent event

POST http://127.0.0.1:8766/agent-check
Content-Type: application/json
Body: the AANA agent event
```

Use `/validate-event` to catch malformed events before execution. The `/agent-check` response shape matches the CLI and Python API: `gate_decision`, `recommended_action`, `aix`, `candidate_aix`, `violations`, `safe_response`, and the full adapter result. CLI and SDK responses also expose `architecture_decision`, the public AANA decision surface with route, AIx score, hard blockers, evidence refs used/missing, authorization state, correction/recovery suggestion, and audit-safe log metadata.

For direct pre-tool-call checks:

```powershell
aana pre-tool-check --event examples/agent_tool_precheck_private_read.json
```

For tools that ingest OpenAPI, point them at:

```text
http://127.0.0.1:8766/openapi.json
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
