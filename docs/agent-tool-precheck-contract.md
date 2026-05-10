# AANA Agent Action Contract v1

Every agent runtime should emit this event before executing a tool call or
consequential action. AANA uses it to route the action to `accept`, `ask`,
`defer`, or `refuse`.

Canonical public spec: [Agent Action Contract v1](agent-action-contract-v1.md)

Schema: `schemas/agent_tool_precheck.schema.json`

Examples: `examples/sdk/agent_tool_precheck_examples.json`

## Required Fields

| Field | Meaning |
| --- | --- |
| `tool_name` | Exact tool/function name the agent intends to call. |
| `tool_category` | One of `public_read`, `private_read`, `write`, `unknown`. |
| `authorization_state` | One of `none`, `user_claimed`, `authenticated`, `validated`, `confirmed`. |
| `evidence_refs` | Redacted references showing why the category and authorization state are believed. |
| `risk_domain` | Primary risk surface, such as `finance`, `devops`, `hr`, `legal`, or `public_information`. |
| `proposed_arguments` | Arguments the agent intends to pass, with secrets/private values redacted where possible. |
| `recommended_route` | Runtime's proposed route before AANA applies the final gate: `accept`, `ask`, `defer`, or `refuse`. |

The public v1 minimum is the seven fields above. `schema_version:
"aana.agent_tool_precheck.v1"` remains supported as an optional compatibility
marker for existing pre-tool-check integrations.

## Routing Rule

- `public_read`: can be accepted without identity auth when evidence shows the data is public or non-sensitive.
- `private_read`: requires at least `authenticated`.
- `write`: requires `validated` or `confirmed`; high-risk writes should generally require `confirmed`.
- `unknown`: should route to `ask`, `defer`, or `refuse`, not direct execution.

The gate applies the stricter route between AANA's computed route and the
runtime's `recommended_route`. For example, if AANA would accept but the runtime
recommends `defer`, the final route is `defer`.

## Local Gate

Python API:

```python
from eval_pipeline.pre_tool_call_gate import gate_pre_tool_call

result = gate_pre_tool_call(event)
```

CLI:

```bash
python scripts/integrations/aana_tool_precheck.py path/to/event.json
```

Response fields:

| Field | Meaning |
| --- | --- |
| `gate_decision` | `pass` only when the final route is `accept` and there are no hard blockers. |
| `recommended_action` | Final route: `accept`, `ask`, `defer`, or `refuse`. |
| `aana_route` | Route computed from the schema fields before runtime route tightening. |
| `runtime_recommended_route` | Runtime's proposed route from the event. |
| `aix` | AIx-style score, decision, components, and hard blockers. |
| `hard_blockers` | Failed constraints that must prevent direct execution. |
| `reasons` | Machine-readable routing explanations. |

## Why This Exists

The external trace benchmark showed that a text classifier alone over-defers or
misroutes real agent traces. AANA needs typed tool surfaces and explicit
authorization-state detectors before learned calibration is applied.
