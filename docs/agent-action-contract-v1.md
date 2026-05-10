# Agent Action Contract v1

AANA Agent Action Contract v1 is a reusable pre-execution standard for agent
tool calls.

AANA is a pre-action control layer for AI agents: agents propose actions, AANA
checks evidence/auth/risk, and tools execute only when the route is accept.

The contract answers one question before a tool runs:

```text
Should this proposed tool call execute now, ask for something, defer to review,
or refuse?
```

## Standard Pattern

```text
agent proposes tool call
-> runtime emits Agent Action Contract v1 event
-> AANA checks evidence, authorization, risk, and route
-> original tool executes only when AANA returns accept
-> audit-safe decision event is recorded
```

## Seven Required Fields

Every Agent Action Contract v1 event has exactly these required public fields:

```text
tool_name, tool_category, authorization_state, evidence_refs, risk_domain, proposed_arguments, recommended_route
```

## Stable Fields

| Field | Required | Allowed values / shape | Meaning |
| --- | --- | --- | --- |
| `tool_name` | yes | non-empty string | Exact tool/function name the agent intends to call. |
| `tool_category` | yes | `public_read`, `private_read`, `write`, `unknown` | Consequence class for the proposed tool call. |
| `authorization_state` | yes | `none`, `user_claimed`, `authenticated`, `validated`, `confirmed` | Strongest verified authorization state known before execution. |
| `evidence_refs` | yes | array of evidence refs | Redacted evidence used to classify the action, authorization, and risk. |
| `risk_domain` | yes | `devops`, `finance`, `education`, `hr`, `legal`, `pharma`, `healthcare`, `commerce`, `customer_support`, `security`, `research`, `personal_productivity`, `public_information`, `unknown` | Primary risk surface for the proposed action. |
| `proposed_arguments` | yes | object | Tool arguments the agent intends to pass. Redact secrets and private values where possible. |
| `recommended_route` | yes | `accept`, `ask`, `defer`, `refuse` | Runtime's proposed route before AANA applies final checks. |

Optional compatibility fields may be present, including `schema_version`,
`request_id`, `agent_id`, `user_intent`, and `authorization_subject`. The stable
public contract is the seven required fields above.

## Minimal Event

```json
{
  "tool_name": "send_email",
  "tool_category": "write",
  "authorization_state": "user_claimed",
  "evidence_refs": ["draft_id:123"],
  "risk_domain": "customer_support",
  "proposed_arguments": {
    "to": "customer@example.com"
  },
  "recommended_route": "accept"
}
```

String evidence refs are accepted for quickstarts. Production systems should use
structured evidence refs.

## Structured Evidence Ref

```json
{
  "source_id": "auth.session",
  "kind": "auth_event",
  "trust_tier": "verified",
  "redaction_status": "redacted",
  "summary": "User identity was authenticated for this account.",
  "freshness": {
    "status": "fresh"
  },
  "provenance": "connector"
}
```

Production evidence refs should include:

- `source_id`: opaque source or record reference.
- `kind`: `user_message`, `assistant_message`, `tool_result`, `policy`, `auth_event`, `approval`, `system_state`, `audit_record`, or `other`.
- `trust_tier`: `verified`, `runtime`, `user_claimed`, `unverified`, or `unknown`.
- `redaction_status`: `public`, `redacted`, `sensitive`, or `unknown`.
- `freshness`: object with `status` set to `fresh`, `stale`, or `unknown`.
- `provenance`: redacted source label such as `connector`, `policy`, `runtime`, or `fixture`.

Public audit logs and public claims should use only public or redacted evidence
metadata, never raw secrets, tokens, passwords, full private records, or full
private tool arguments.

## Route Semantics

| Route | Executes tool? | Meaning | Runtime action |
| --- | --- | --- | --- |
| `accept` | yes | Proceed only within the checked scope. | Execute the original tool call and record the audit-safe event. |
| `ask` | no | Missing information, authorization, confirmation, or clarification. | Ask the user/runtime, then recheck. |
| `defer` | no | Needs stronger evidence, domain-owner review, or human review. | Route to review or retrieve stronger evidence, then recheck. |
| `refuse` | no | A hard blocker prevents safe execution. | Do not execute. Return refusal/recovery guidance. |

The broader AANA result envelope also uses `revise` and `retrieve` for
agent-output/workflow checks:

| Route | Executes tool? | Meaning |
| --- | --- | --- |
| `revise` | no | Revise the candidate output or action, then recheck. |
| `retrieve` | no | Retrieve missing grounding or policy evidence, then recheck. |

Agent Action Contract v1 `recommended_route` is the pre-tool-call subset:
`accept`, `ask`, `defer`, and `refuse`.

Route strictness is ordered:

```text
accept < ask < defer < refuse
```

When the runtime's `recommended_route` is stricter than AANA's inferred route,
the stricter route wins. Old v1 clients should fail closed on unknown route
values.

## Execution Rule

Only execute when all are true:

- `gate_decision == "pass"`
- `recommended_action == "accept"`
- `architecture_decision.route == "accept"` when using the SDK/API envelope
- `hard_blockers` is empty
- `aix.hard_blockers` is empty
- schema validation has no errors

No other route executes.

## Authorization State Semantics

Authorization states are ordered from weakest to strongest:

```text
none < user_claimed < authenticated < validated < confirmed
```

| State | Meaning | Private read | Write schema accept | Write execution |
| --- | --- | --- | --- | --- |
| `none` | No usable authorization context is available. | no | no | no |
| `user_claimed` | User asked for or claimed authority, but identity is not verified. | no | no | no |
| `authenticated` | User identity/session is authenticated. | yes | no | no |
| `validated` | Target object, ownership, policy, or eligibility was validated. | yes | yes | no |
| `confirmed` | User explicitly confirmed this consequential action. | yes | yes | yes |

The v1 schema allows `validated` writes with `recommended_route: "accept"` for
backward compatibility, but AANA execution wrappers still fail closed unless the
final decision is `accept` with no hard blockers. Consequential writes should
reach `confirmed` before execution. Private identity-bound reads require at
least `authenticated`.

## Examples

### Public Read: Accept

```json
{
  "tool_name": "search_docs",
  "tool_category": "public_read",
  "authorization_state": "none",
  "evidence_refs": [],
  "risk_domain": "research",
  "proposed_arguments": {
    "query": "Agent Action Contract v1"
  },
  "recommended_route": "accept"
}
```

Expected route: `accept`.

### Write Missing Confirmation: Ask

```json
{
  "tool_name": "send_email",
  "tool_category": "write",
  "authorization_state": "user_claimed",
  "evidence_refs": ["draft_id:123"],
  "risk_domain": "customer_support",
  "proposed_arguments": {
    "to": "customer@example.com"
  },
  "recommended_route": "accept"
}
```

Expected route: `ask`, because a consequential write needs validation and
explicit confirmation.

### Private Read Missing Auth: Defer

```json
{
  "tool_name": "get_recent_transactions",
  "tool_category": "private_read",
  "authorization_state": "none",
  "evidence_refs": [],
  "risk_domain": "finance",
  "proposed_arguments": {
    "account_id": "acct_redacted",
    "limit": 5
  },
  "recommended_route": "accept"
}
```

Expected route: `defer`, because a private read is missing authentication and
evidence.

### Unknown Destructive Tool: Refuse

```json
{
  "tool_name": "delete_database",
  "tool_category": "unknown",
  "authorization_state": "none",
  "evidence_refs": [],
  "risk_domain": "unknown",
  "proposed_arguments": {
    "database": "prod"
  },
  "recommended_route": "refuse"
}
```

Expected route: `refuse`.

Canonical schema-valid examples are checked in at:

```text
examples/agent_action_contract_cases.json
```

## JSON Schema

The canonical JSON schema is:

```text
schemas/agent_tool_precheck.schema.json
```

The schema id is:

```text
https://aana.dev/schemas/agent_action_contract_v1.schema.json
```

The filename and optional `schema_version: "aana.agent_tool_precheck.v1"` value
are kept for backward compatibility with earlier pre-tool-check integrations.
Public documentation should call the standard **AANA Agent Action Contract v1**.

## Python SDK Example

```python
import aana

event = {
    "tool_name": "send_email",
    "tool_category": "write",
    "authorization_state": "user_claimed",
    "evidence_refs": ["draft_id:123"],
    "risk_domain": "customer_support",
    "proposed_arguments": {"to": "customer@example.com"},
    "recommended_route": "accept",
}

decision = aana.check_tool_call(event)

if decision["architecture_decision"]["route"] == "accept":
    send_email(**event["proposed_arguments"])
else:
    return {
        "blocked": True,
        "aana": decision["architecture_decision"],
    }
```

The same API is available as `aana.gate_action(event)`.

## TypeScript SDK Example

```ts
import {
  checkToolPrecheck,
  shouldExecuteTool,
  toolPrecheckEvent
} from "@aana/integration-sdk";

const event = toolPrecheckEvent({
  toolName: "get_recent_transactions",
  toolCategory: "private_read",
  authorizationState: "authenticated",
  evidenceRefs: ["auth.session"],
  riskDomain: "finance",
  proposedArguments: { account_id: "acct_redacted", limit: 10 },
  recommendedRoute: "accept"
});

const decision = checkToolPrecheck(event);

if (shouldExecuteTool(decision)) {
  // Execute the original tool call.
}
```

## FastAPI Example

Start the service:

```powershell
aana-fastapi --host 127.0.0.1 --port 8766
```

Call `POST /pre-tool-check`:

```powershell
$body = @{
  tool_name = "send_email"
  tool_category = "write"
  authorization_state = "user_claimed"
  evidence_refs = @("draft_id:123")
  risk_domain = "customer_support"
  proposed_arguments = @{ to = "customer@example.com" }
  recommended_route = "accept"
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8766/pre-tool-check `
  -Headers @{ Authorization = "Bearer $env:AANA_BRIDGE_TOKEN" } `
  -Body $body `
  -ContentType "application/json"
```

OpenAPI docs are available at:

```text
http://127.0.0.1:8766/docs
```

## MCP Example

AANA exposes an MCP-style tool named `aana_pre_tool_check`. Hosts should call it
before executing the original tool.

Minimal JSON-RPC-style payload:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "aana_pre_tool_check",
    "arguments": {
      "tool_name": "send_email",
      "tool_category": "write",
      "authorization_state": "user_claimed",
      "evidence_refs": ["draft_id:123"],
      "risk_domain": "customer_support",
      "proposed_arguments": {
        "to": "customer@example.com"
      },
      "recommended_route": "accept"
    }
  }
}
```

Host enforcement rule:

```text
call aana_pre_tool_check
-> read structuredContent.route
-> execute original tool only when route == accept and no hard blockers exist
```

Local smoke:

```powershell
'{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python scripts/integrations/aana_mcp_server.py
```

For a real MCP SDK or ChatGPT Apps server, register the descriptor from
`eval_pipeline.mcp_server.AANA_PRE_TOOL_CHECK_TOOL` and route calls to
`eval_pipeline.mcp_server.handle_aana_pre_tool_check(...)`.

## Versioning Rules

- v1 required fields are stable and must stay backward-compatible.
- A v1-compatible change must not remove, rename, reorder, or make optional any required v1 field.
- `schema_version: "aana.agent_tool_precheck.v1"` is optional for v1 events and kept for existing pre-tool-check integrations.
- Future v2/v3 gates may add optional fields, richer classifiers, or new result metadata while still accepting valid v1 events.
- A future schema that changes required fields, route names, or enum values must use a new schema id and must not be silently treated as v1.
- Output envelopes may add optional fields, but `gate_decision`, `recommended_action`, `hard_blockers`, and audit-safe route metadata must remain backward-compatible.
- Old v1 clients should fail closed when they encounter an unknown route, unknown category, or non-negotiated schema version.

## Production Guidance

- Treat `public_read` as non-sensitive/public only when evidence supports that classification.
- Treat `private_read` as identity-bound or account-bound; it needs at least `authenticated` authorization before direct acceptance.
- Treat `write` as consequential; it needs `validated` or `confirmed` authorization, and high-risk writes should require `confirmed`.
- Treat `unknown` as non-executable until classified.
- Keep raw private data out of `evidence_refs` and audit logs.
- Use `public` or `redacted` evidence refs with fresh `freshness.status` and clear `provenance` before publishing audit logs or claims.
