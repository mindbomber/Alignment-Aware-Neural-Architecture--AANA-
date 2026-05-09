# AANA Agent Action Contract v1

The Agent Action Contract v1 is the public minimum event shape an agent runtime emits before a consequential tool call or action.

The contract is deliberately small:

```json
{
  "tool_name": "send_email",
  "tool_category": "write",
  "authorization_state": "user_claimed",
  "evidence_refs": ["draft_id:123"],
  "risk_domain": "customer_support",
  "proposed_arguments": {"to": "customer@example.com"},
  "recommended_route": "accept"
}
```

AANA checks this event and returns whether the runtime should `accept`, `ask`, `defer`, or `refuse`.

## Freeze Guarantee

Agent Action Contract v1 freezes the seven required fields and the four route names. A v1-compatible change must not remove, rename, reorder, or make optional any required v1 field:

```text
tool_name, tool_category, authorization_state, evidence_refs, risk_domain, proposed_arguments, recommended_route
```

The public route set is also frozen:

```text
accept, ask, defer, refuse
```

Runtimes must treat unknown future route values as fail-closed unless they explicitly opt into a newer contract version.

## Stable Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `tool_name` | yes | Exact tool/function name the agent intends to call. |
| `tool_category` | yes | `public_read`, `private_read`, `write`, or `unknown`. |
| `authorization_state` | yes | `none`, `user_claimed`, `authenticated`, `validated`, or `confirmed`. |
| `evidence_refs` | yes | Redacted evidence references used to classify the action and authorization state. |
| `risk_domain` | yes | Primary risk surface, such as `customer_support`, `finance`, `devops`, `legal`, `pharma`, `research`, or `unknown`. |
| `proposed_arguments` | yes | Tool arguments the agent intends to pass. Redact secrets and private values where possible. |
| `recommended_route` | yes | Runtime's proposed route before AANA applies stricter checks: `accept`, `ask`, `defer`, or `refuse`. |

Optional compatibility fields may be present, including `schema_version`, `request_id`, `agent_id`, `user_intent`, and `authorization_subject`. The stable public contract is the seven required fields above.

## Compatibility Name

The checked-in JSON schema remains at:

```text
schemas/agent_tool_precheck.schema.json
```

That filename and the optional `schema_version: "aana.agent_tool_precheck.v1"` value are kept for backward compatibility. Public documentation should call the contract **AANA Agent Action Contract v1**.

## Execution Rule

Only execute when all are true:

- `gate_decision == "pass"`
- `recommended_action == "accept"`
- `architecture_decision.route == "accept"` when using the SDK/API decision envelope
- `hard_blockers` is empty
- `aix.hard_blockers` is empty

## Route Semantics

- `accept`: execute only within the checked scope.
- `ask`: ask for missing authorization, confirmation, evidence, or clarification.
- `defer`: route to stronger evidence retrieval, a domain owner, or human review.
- `refuse`: do not execute because a hard blocker prevents safe action.

Route strictness is ordered as:

```text
accept < ask < defer < refuse
```

When the runtime's `recommended_route` is stricter than AANA's route, the stricter route wins. This keeps local runtimes free to refuse or defer even when AANA would otherwise accept.

## Versioning Rules

- v1 required fields are stable and must stay backward-compatible.
- `schema_version: "aana.agent_tool_precheck.v1"` is optional for v1 events and kept for existing pre-tool-check integrations.
- Future v2/v3 gates may add optional fields, richer classifiers, or new result metadata while still accepting valid v1 events.
- A future schema that changes required fields, route names, or enum values must use a new schema id and must not be silently treated as v1.
- Output envelopes may add optional fields, but `gate_decision`, `recommended_action`, `hard_blockers`, and audit-safe route metadata must remain backward-compatible.
- Old v1 clients should fail closed when they encounter an unknown route, unknown category, or non-negotiated schema version.

## Canonical Examples

Canonical schema-valid examples are checked in at:

```text
examples/agent_action_contract_cases.json
```

The examples cover safe public reads, authenticated private reads, private reads that must ask, confirmed writes, unsafe writes, and unknown tools that must defer.

## Production Guidance

- Treat `public_read` as non-sensitive/public only when evidence supports that classification.
- Treat `private_read` as identity-bound or account-bound; it needs at least `authenticated` authorization before direct acceptance.
- Treat `write` as consequential; it needs `validated` or `confirmed` authorization, and high-risk writes should require `confirmed`.
- Treat `unknown` as non-executable until classified.
- Keep raw private data out of `evidence_refs` and audit logs.
