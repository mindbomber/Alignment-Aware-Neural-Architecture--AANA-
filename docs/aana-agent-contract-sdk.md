# AANA Agent Contract SDK

The AANA agent contract SDK lets an agent runtime check tool calls before
execution. The runtime emits a small `aana.agent_tool_precheck.v1` event, AANA
validates it, and the gate returns `accept`, `ask`, `defer`, or `refuse`.

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

result = aana.check_tool_precheck(event)
if aana.should_execute_tool(result):
    pass  # Execute the tool call.
```

Bridge client:

```python
client = aana.AANAClient(base_url="http://127.0.0.1:8765", token="...")
result = client.tool_precheck(event)
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
