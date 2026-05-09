# Agent Action Contract Quickstart

Public claim: AANA makes agents more auditable, safer, more grounded, and more controllable.

Stable public spec: [AANA Agent Action Contract v1](agent-action-contract-v1.md).

Use this when an agent is about to call a tool, send a message, write data, read private records, publish, deploy, buy, book, or take another consequential action.

The pattern is:

```text
agent proposes -> AANA checks -> agent executes only if allowed
```

## Minimal Python Example

```python
import aana

decision = aana.check_tool_call({
    "tool_name": "send_email",
    "tool_category": "write",
    "authorization_state": "user_claimed",
    "evidence_refs": ["draft_id:123"],
    "risk_domain": "customer_support",
    "proposed_arguments": {"to": "customer@example.com"},
    "recommended_route": "accept"
})

print(decision["architecture_decision"])
```

This returns `ask`, not `accept`, because a write action needs validated authorization and explicit confirmation before execution.

Example result shape:

```json
{
  "route": "ask",
  "aix_score": 0.72,
  "hard_blockers": ["write_missing_validation_or_confirmation"],
  "evidence_refs": {
    "used": ["draft_id:123"],
    "missing": ["write_missing_validation_or_confirmation"]
  },
  "authorization_state": "user_claimed",
  "tool_name": "send_email",
  "tool_category": "write",
  "risk_domain": "customer_support",
  "correction_recovery_suggestion": "Ask the user or runtime for the missing authorization, confirmation, or evidence before execution."
}
```

Only execute the tool when all of these are true:

- `gate_decision == "pass"`
- `recommended_action == "accept"`
- `architecture_decision.route == "accept"`
- `hard_blockers` is empty
- `aix.hard_blockers` is empty

## Confirmed Write Example

```python
decision = aana.check_tool_call({
    "tool_name": "send_email",
    "tool_category": "write",
    "authorization_state": "confirmed",
    "evidence_refs": ["draft_id:123", "approval:user-confirmed-send"],
    "risk_domain": "customer_support",
    "proposed_arguments": {"to": "customer@example.com"},
    "recommended_route": "accept"
})

if aana.should_execute_tool(decision):
    send_email(to="customer@example.com")
```

## Routes

- `accept`: execute within the checked scope.
- `ask`: ask for missing authorization, confirmation, or evidence.
- `defer`: route to stronger evidence, a domain owner, or human review.
- `refuse`: do not execute because a hard blocker prevents safe action.

## Full Contract Fields

- `tool_name`: the function or tool the agent wants to call.
- `tool_category`: `public_read`, `private_read`, `write`, or `unknown`.
- `authorization_state`: `none`, `user_claimed`, `authenticated`, `validated`, or `confirmed`.
- `evidence_refs`: string refs for quickstarts or structured refs for production.
- `risk_domain`: domain such as `customer_support`, `finance`, `devops`, `legal`, `pharma`, or `unknown`.
- `proposed_arguments`: redacted tool arguments.
- `recommended_route`: the runtime route before AANA applies stricter checks.

For production integrations, prefer structured evidence refs from
`aana.tool_evidence_ref(...)`. Those refs standardize `source_id`, `kind`,
`trust_tier`, `redaction_status`, `freshness`, and `provenance`. Keep raw
private data out of the event; public audit logs and claims require safe
redaction plus fresh, provenance-backed evidence.

