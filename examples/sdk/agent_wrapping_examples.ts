import {
  gateToolCall,
  mcpToolMiddleware,
  openAIAgentsToolMiddleware,
  toolEvidenceRef,
  wrapAgentTool
} from "../../sdk/typescript/src/index";

// Pattern: agent proposes -> AANA checks -> tool executes only if allowed.

const getPublicStatus = wrapAgentTool(
  "get_public_status",
  (args: { service: string }) => ({ service: args.service, status: "ok" }),
  {
    tool_category: "public_read",
    authorization_state: "none",
    risk_domain: "public_information"
  },
  {
    onDecision: (gate) => console.log(gate.result.architecture_decision)
  }
);

const sendCustomerEmail = openAIAgentsToolMiddleware(
  "send_customer_email",
  (args: { to: string; body: string }) => ({ sent: true, to: args.to }),
  {
    tool_category: "write",
    authorization_state: "confirmed",
    risk_domain: "customer_support",
    evidence_refs: [
      toolEvidenceRef({
        source_id: "approval.user-confirmed-send",
        kind: "approval",
        trust_tier: "verified",
        redaction_status: "redacted",
        summary: "User confirmed the final customer email send."
      })
    ]
  }
);

const searchPublicDocs = mcpToolMiddleware(
  "search_public_docs",
  (args: { query: string }) => ({ result: `public lookup for ${args.query}` }),
  {
    tool_category: "public_read",
    authorization_state: "none",
    risk_domain: "research"
  }
);

const directGate = gateToolCall({
  toolName: "send_customer_email",
  proposedArguments: { to: "customer@example.com", body: "Approved draft" },
  metadata: {
    tool_category: "write",
    authorization_state: "confirmed",
    risk_domain: "customer_support",
    evidence_refs: [
      toolEvidenceRef({
        source_id: "approval.user-confirmed-send",
        kind: "approval"
      })
    ]
  }
});

console.log(getPublicStatus({ service: "docs" }));
console.log(sendCustomerEmail({ to: "customer@example.com", body: "Approved draft" }));
console.log(searchPublicDocs({ query: "AANA pre-tool-call contract" }));
console.log(directGate.result.architecture_decision?.route);
