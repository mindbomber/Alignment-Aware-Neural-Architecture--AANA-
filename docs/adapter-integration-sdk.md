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

client = aana.SupportAANAClient(
    base_url="http://127.0.0.1:8765",
    token=os.environ["AANA_BRIDGE_TOKEN"],
    shadow_mode=True,
)

workflow = client.workflow_request(
    adapter="crm",
    request="Draft a refund reply using only verified account facts.",
    candidate="Hi Maya, order #A1842 is eligible for a full refund and your card ending 4242 will be credited in 3 days.",
    evidence=[
        client.evidence_object(
            "CRM record: customer name is Maya Chen. Order ID and refund eligibility are unavailable.",
            source_id="crm-record",
            retrieved_at="2026-05-05T00:00:00Z",
        ),
        client.evidence_object(
            "Support policy: verify refund eligibility before promising credits or timelines.",
            source_id="support-policy",
            retrieved_at="2026-05-05T00:00:00Z",
        ),
    ],
)

result = client.workflow_check(workflow)
```

Agent Event path for an agent framework:

```python
event = client.agent_event(
    adapter_id="draft",
    user_request="Draft a support reply with verified account facts.",
    candidate_action="Promise a refund without verified eligibility.",
    available_evidence=client.evidence(
        "Refund eligibility: unknown.",
        source_id="crm-record",
        retrieved_at="2026-05-05T00:00:00Z",
    ),
)

result = client.agent_check(event)
```

Public helpers:

- `aana.AANAClient`
- `aana.SupportAANAClient`
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

Support aliases are also available through `SupportAANAClient`; `crm`, `draft`,
`email`, `ticket`, and `billing` resolve to the supported support adapter IDs.

Public helpers:

- `AanaClient`
- `createAanaClient(...)`
- `normalizeEvidence(...)`
- `workflowRequest(...)`
- `agentEvent(...)`

## Integration Rule

All SDK helpers build either the Workflow Contract or Agent Event Contract and
call the same runtime paths used by the CLI and HTTP bridge. Do not call
adapter runner modules or verifier internals from an app integration.

For enforced flows, proceed with the original action only when:

- `gate_decision` is `pass`
- `recommended_action` is `accept`
- `aix.hard_blockers` is empty

For early pilots, use shadow mode so AANA observes proposed actions, writes
redacted telemetry, and reports would-pass/revise/defer/refuse metrics without
changing production behavior.
