# AANA Security Threat Model

AANA is a control and audit layer between an agent and consequential answers or actions. The primary security assumption is adversarial: a malicious agent, compromised planner, prompt injection, or manipulated tool result may try to bypass AANA, hide risk, or force execution.

## Assets

- User approval state, authorization state, and evidence references.
- Tokens, API keys, passwords, connector credentials, and session state.
- Private account identifiers, customer IDs, payment IDs, card IDs, user IDs, and similar identity-bound records.
- Tool arguments for sends, deletes, purchases, deploys, exports, permission changes, and other writes.
- Audit records, audit summaries, AIx scores, hard blockers, and decision routes.

## Trust Boundaries

- Agent output is untrusted until AANA checks it.
- Tool calls are untrusted until the Agent Action Contract is validated.
- Evidence is untrusted unless it carries source id, trust tier, redaction status, freshness, and provenance.
- Public demos are untrusted user-input surfaces and must never execute real sends, deletes, purchases, deploys, exports, or connector writes.
- Audit storage is metadata-only. Raw prompts, full candidates, raw evidence, tokens, passwords, private account IDs, and full tool arguments must not be stored.

## Threats

- Prompt injection tells the agent to ignore AANA, fake an `accept`, remove blockers, or call a tool directly.
- The agent sets `recommended_route: accept` for an unknown, write, private-read, or under-authorized tool call.
- The agent hides sensitive values inside tool arguments, evidence refs, logs, safe responses, exception messages, or audit metadata.
- A tool result fabricates authorization, confirmation, policy evidence, or freshness.
- A malicious agent retries until a weaker route appears, or switches from enforcement mode to shadow mode.
- A public demo is modified to call live services, send emails, delete files, purchase items, deploy code, or export private data.
- CI or dependency drift introduces vulnerable packages or accidentally commits credentials.

## Required Controls

- Fail closed on malformed schemas, missing auth, unknown tools, contradictory evidence, and validation errors.
- Execute only when the final route is `accept`, hard blockers are empty, and enforcement mode is active.
- Treat shadow mode as observe-only; shadow telemetry may report would-block or would-intervene but must not permit execution in production.
- Store only redacted audit metadata: route, AIx score, hard blockers, missing evidence, evidence source ids, authorization state, latency, and fingerprints.
- Reject audit records containing raw tokens, passwords, private account IDs, full tool arguments, raw prompts, raw candidates, raw evidence, or safe-response text.
- Run secret scanning and dependency audit checks in CI.
- Keep public demos synthetic-only with no real side effects and no required secrets.

## Bypass Resistance

AANA cannot rely on an agent promising to call it. Integrations must wrap execution:

```text
agent proposes -> AANA checks -> wrapper executes only if AANA accepts
```

The wrapper, middleware, API service, or runtime must be the enforcement point. If an agent can call the tool directly, it can bypass AANA. Production deployments should put sensitive tools behind AANA-aware middleware or policy enforcement that rejects unchecked calls.

## Residual Risk

These controls do not prove production security by themselves. Live deployments still need connector permission review, token rotation, edge rate limiting, immutable audit storage, incident response, dependency update ownership, and domain-owner signoff.
