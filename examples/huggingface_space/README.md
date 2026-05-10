---
title: AANA Demo
sdk: gradio
app_file: app.py
license: mit
python_version: "3.11"
short_description: Try AANA's pre-action agent control layer.
pinned: false
---

# Try AANA In 2 Minutes

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

The Space calls `aana.check_tool_call` with these fields and displays:

- route: `accept`, `ask`, `defer`, or `refuse`
- AIx score
- hard blockers
- missing evidence
- authorization state
- recovery guidance
- audit-safe log event
- blocked-tool non-execution proof from a synthetic executor

The synthetic executor is intentionally safe: it records that it would have run
only when AANA returns `accept`. It cannot send, delete, purchase, deploy,
export, or access private data.

Public evidence links:

- Model card: https://huggingface.co/mindbomber/aana
- Peer-review evidence pack: https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack
- Public artifact hub: https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4
- Short technical report: https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/aana-pre-action-control-layer-technical-report.md

Peer-review request:

- Are routes correct?
- Are false positives acceptable?
- Is evidence handling sufficient?
- Does this generalize beyond examples?

Please post critique in the Space discussion:
https://huggingface.co/spaces/mindbomber/aana-demo/discussions/1

Current diagnostic boundary: safety/adversarial prompt routing is useful but
incomplete, FinanceBench-style QA evidence routing is controlled and not an
official leaderboard claim, and governance/compliance routing is diagnostic
rather than legal, regulatory, or platform-policy certification.

Integration validation v1 is now included in the evidence pack: held-out
tool-call cases validate route parity, blocked-tool non-execution,
decision-shape parity, audit completeness, and schema behavior across CLI, SDK,
FastAPI, MCP, and middleware surfaces.
