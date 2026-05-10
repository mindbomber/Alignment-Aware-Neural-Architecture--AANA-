# AANA Agent Contract SDK

The AANA agent contract SDK lets an agent runtime check tool calls before
execution. The runtime emits a small `aana.agent_tool_precheck.v1` event, AANA
validates it, and the gate returns `accept`, `ask`, `defer`, or `refuse`.

Public claim: AANA is a pre-action control layer for AI agents: agents propose actions, AANA checks evidence/auth/risk, and tools execute only when the route is accept. The SDK exposes that architecture through
an `architecture_decision` envelope that includes the route, AIx score, hard
blockers, evidence refs, authorization state, correction/recovery suggestion,
and audit-safe log event.

Proceed with the tool call only when:

- `gate_decision == "pass"`
- `recommended_action == "accept"`
- `hard_blockers` is empty
- `aix.hard_blockers` is empty

## Python

```python
import aana

event = aana.build_tool_precheck_event(
    tool_name="get_recent_transactions",
    tool_category="private_read",
    authorization_state="authenticated",
    evidence_refs=[
        aana.tool_evidence_ref(
            source_id="auth.email.lookup",
            kind="auth_event",
            trust_tier="verified",
            redaction_status="redacted",
            summary="User identity was authenticated.",
        )
    ],
    risk_domain="finance",
    proposed_arguments={"account_id": "acct_redacted", "limit": 10},
    recommended_route="accept",
)

result = aana.check_tool_call(event)
if aana.should_execute_tool(result):
    pass  # Execute the tool call.

print(result["architecture_decision"]["route"])
print(result["architecture_decision"]["aix_score"])
print(result["architecture_decision"]["hard_blockers"])
```

Bridge client:

```python
client = aana.AANAClient(base_url="http://127.0.0.1:8765", token="...")
result = client.tool_precheck(event)
```

Alias for action-first runtimes:

```python
decision = aana.gate_action(event)
```

CLI:

```powershell
aana pre-tool-check --event examples/agent_tool_precheck_private_read.json
aana evidence-pack --require-existing-artifacts
```

Agent wrapping helpers:

```python
guarded = aana.wrap_agent_tool(
    send_customer_email,
    metadata={
        "tool_category": "write",
        "authorization_state": "confirmed",
        "risk_domain": "customer_support",
        "evidence_refs": [
            aana.tool_evidence_ref(source_id="approval.user-confirmed-send", kind="approval")
        ],
    },
)

result = guarded(to="customer@example.com", body="Approved draft")
decision = guarded.aana_last_gate["result"]["architecture_decision"]
```

## TypeScript

```ts
import {
  checkToolPrecheck,
  shouldExecuteTool,
  toolEvidenceRef,
  toolPrecheckEvent
} from "@aana/integration-sdk";

const event = toolPrecheckEvent({
  toolName: "get_recent_transactions",
  toolCategory: "private_read",
  authorizationState: "authenticated",
  evidenceRefs: [
    toolEvidenceRef({
      source_id: "auth.email.lookup",
      kind: "auth_event",
      trust_tier: "verified",
      redaction_status: "redacted",
      summary: "User identity was authenticated."
    })
  ],
  riskDomain: "finance",
  proposedArguments: { account_id: "acct_redacted", limit: 10 },
  recommendedRoute: "accept"
});

const result = checkToolPrecheck(event);
if (shouldExecuteTool(result)) {
  // Execute the tool call.
}
```

Bridge client:

```ts
const result = await client.toolPrecheck(event);
```

## Bridge Routes

- `GET /schemas/agent-tool-precheck.schema.json`
- `POST /validate-tool-precheck`
- `POST /tool-precheck`

The bridge route uses the same deterministic schema-based gate as the local
Python and TypeScript helpers.

