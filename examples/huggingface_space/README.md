# AANA Agent Action Contract v1 Space

This local Hugging Face Space artifact is the repo-owned source for the public
"try AANA" demo. It accepts the frozen Agent Action Contract v1 fields and
returns the same route decision used by the Python SDK, FastAPI service, and MCP
tool.

AANA is a pre-action control layer for AI agents: agents propose actions, AANA checks evidence/auth/risk, and tools execute only when the route is accept.

Core runtime pattern:

```text
agent proposes -> AANA checks -> tool executes only if route == accept
```

This is the difference reviewers should inspect: AANA turns pre-tool safety into
a typed contract, route table, hard execution rule, and audit-safe decision
event instead of relying only on prompts, classifiers, LLM judges, or
framework-specific middleware.

Frozen required fields:

- `tool_name`
- `tool_category`
- `authorization_state`
- `evidence_refs`
- `risk_domain`
- `proposed_arguments`
- `recommended_route`

The Space should call `aana.check_tool_call` with these fields and display
`accept`, `ask`, `defer`, or `refuse` along with AIx score, hard blockers,
evidence refs, authorization state, recovery guidance, and an audit-safe log
event.

Public evidence links:

- Model card: https://huggingface.co/mindbomber/aana
- Peer-review evidence pack: https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack
- Public artifact hub: https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4

Current diagnostic boundary: safety/adversarial prompt routing is useful but
incomplete, FinanceBench-style QA evidence routing is controlled and not an
official leaderboard claim, and governance/compliance routing is diagnostic
rather than legal, regulatory, or platform-policy certification.

Integration validation v1 is now included in the evidence pack: held-out
tool-call cases validate route parity, blocked-tool non-execution,
decision-shape parity, audit completeness, and schema behavior across CLI, SDK,
FastAPI, MCP, and middleware surfaces.
