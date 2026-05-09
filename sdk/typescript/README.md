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

Agent Action Contract pre-tool-call gate:

```ts
import {
  AanaClient,
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

const localResult = checkToolPrecheck(event);
if (shouldExecuteTool(localResult)) {
  // Execute the tool call.
}

const bridge = new AanaClient({ baseUrl: "http://127.0.0.1:8765" });
const bridgeResult = await bridge.toolPrecheck(event);
```

Framework middleware wrappers:

```ts
import {
  mcpToolMiddleware,
  openAIAgentsToolMiddleware,
  shouldExecuteTool
} from "@aana/integration-sdk";

const guardedMcpHandler = mcpToolMiddleware(
  "get_public_status",
  (args: { service: string }) => ({ status: args.service })
);

const guardedAgentTool = openAIAgentsToolMiddleware(
  "get_recent_transactions",
  (args: { account_id: string }) => ({ ok: true }),
  {
    authorization_state: "authenticated",
    risk_domain: "finance"
  }
);
```

Proceed with the original action only when the returned AANA result has
`gate_decision: "pass"`, `recommended_action: "accept"`, and no AIx hard
blockers.

If a wrapper blocks, it never calls the wrapped function in enforcement mode.
With `raiseOnBlock: true`, wrappers throw `AanaToolExecutionBlocked` and expose
the standardized `error` object on the exception. With `raiseOnBlock: false`,
the wrapper returns the gate object with:

```ts
result.error?.error_type === "aana_tool_execution_blocked";
result.error?.recovery_suggestion;
result.execution_allowed === false;
```
