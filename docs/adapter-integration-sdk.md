# AANA Adapter Integration SDK

The Adapter Integration SDK gives app developers small helpers for calling AANA
without hand-building Agent Event or Workflow Contract JSON.

## Python

Use the local in-process runtime:

```python
import aana

client = aana.AANAClient(shadow_mode=True)

request = client.workflow_request(
    adapter="research_summary",
    request="Answer using only Source A.",
    candidate="The result is proven by Source C.",
    evidence=client.evidence(
        "Source A: The claim is uncertain.",
        source_id="source-a",
        retrieved_at="2026-05-05T00:00:00Z",
    ),
    constraints=["Use approved sources only."],
)

result = client.workflow_check(request)
```

Use a running HTTP bridge:

```python
import os
import aana

client = aana.client(
    base_url="http://127.0.0.1:8765",
    token=os.environ["AANA_BRIDGE_TOKEN"],
    shadow_mode=True,
)

result = client.agent_check(
    adapter_id="support_reply",
    user_request="Draft a support reply with verified account facts.",
    candidate_action="Promise a refund without verified eligibility.",
    available_evidence=client.evidence(
        "Refund eligibility: unknown.",
        source_id="crm-record",
        retrieved_at="2026-05-05T00:00:00Z",
    ),
)
```

Public helpers:

- `aana.AANAClient`
- `aana.client(...)`
- `aana.normalize_evidence(...)`
- `aana.build_workflow_request(...)`
- `aana.build_agent_event(...)`

## TypeScript

The TypeScript package lives under `sdk/typescript`.

```ts
import { AanaClient, workflowRequest } from "@aana/integration-sdk";

const client = new AanaClient({
  baseUrl: "http://127.0.0.1:8765",
  token: process.env.AANA_BRIDGE_TOKEN,
  shadowMode: true
});

const request = workflowRequest({
  adapter: "research_summary",
  request: "Answer using only Source A.",
  candidate: "The result is proven by Source C.",
  evidence: client.evidence("Source A: The claim is uncertain.", {
    source_id: "source-a",
    retrieved_at: new Date().toISOString()
  }),
  constraints: ["Use approved sources only."]
});

const result = await client.workflowCheck(request);
```

Public helpers:

- `AanaClient`
- `createAanaClient(...)`
- `normalizeEvidence(...)`
- `workflowRequest(...)`
- `agentEvent(...)`

## Integration Rule

For enforced flows, proceed with the original action only when:

- `gate_decision` is `pass`
- `recommended_action` is `accept`
- `aix.hard_blockers` is empty

For early pilots, use shadow mode so AANA observes proposed actions, writes
redacted telemetry, and reports would-pass/revise/defer/refuse metrics without
changing production behavior.

