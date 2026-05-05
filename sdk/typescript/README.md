# AANA TypeScript Integration SDK

This package contains dependency-light helpers for apps that call a local AANA
HTTP bridge.

```ts
import { AanaClient, workflowRequest, normalizeEvidence } from "@aana/integration-sdk";

const aana = new AanaClient({
  baseUrl: "http://127.0.0.1:8765",
  token: process.env.AANA_BRIDGE_TOKEN,
  shadowMode: true
});

const evidence = normalizeEvidence("Source A: The claim is uncertain.", {
  source_id: "source-a",
  retrieved_at: new Date().toISOString(),
  trust_tier: "verified",
  redaction_status: "redacted"
});

const request = workflowRequest({
  adapter: "research_summary",
  request: "Answer using only Source A.",
  candidate: "The result is proven by Source C.",
  evidence,
  constraints: ["Use approved sources only."]
});

const result = await aana.workflowCheck(request);
```

Proceed with the original action only when the returned AANA result has
`gate_decision: "pass"`, `recommended_action: "accept"`, and no AIx hard
blockers.

