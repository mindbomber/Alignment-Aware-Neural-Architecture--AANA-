# AANA MCP-Bench Submission Plan

Result label: `planned_external_benchmark_submission`

This document tracks the next step after the MSB / MCP Security Bench protocol artifact. MCP-Bench evaluates tool-using LLM agents on complex real-world MCP tasks, so AANA should be submitted as a paired control layer around a base agent, not as a standalone model row.

## Benchmark Fit

[MCP-Bench](https://github.com/Accenture/mcp-bench) is a strong AANA target because it measures whether an agent can discover, select, and use MCP tools across real task dependencies. AANA's differentiated claim is not that it is the base planner. The claim is:

`agent proposes -> AANA checks -> agent executes only if allowed`

The right submission should therefore compare the same base model in two conditions:

- base agent alone
- base agent plus AANA pre-tool-call gate

## Official Leaderboard Boundary

The current public leaderboard at [mcpbench/mcp-bench](https://huggingface.co/spaces/mcpbench/mcp-bench) reports model-level task-completion and tool-use metrics. It is not currently shaped as a safety/control-layer leaderboard.

Because of that, AANA should not claim an MCP-Bench leaderboard result from a static task-file conversion alone. A valid submission needs a real MCP-Bench run with AANA inserted before tool execution.

## Proposed Run

Base agent:

- Start with one available model already supported by the MCP-Bench runner.
- Prefer a lower-cost model first for smoke testing, then a stronger model if the scaffold works.

Conditions:

1. `base_agent`: unmodified MCP-Bench runner.
2. `base_agent_plus_aana`: same model, same tasks, same judge, same server setup, with AANA gating every proposed MCP tool call.

Repo-owned wrapper:

```bash
python scripts/run_mcp_bench_aana_ablation.py \
  --mcp-bench-dir ../mcp-bench \
  --models o4-mini \
  --tasks-file tasks/mcpbench_tasks_single_runner_format.json \
  --task-limit 1 \
  --output-dir eval_outputs/mcp_bench_aana_ablation
```

The script runs the plain condition first, then patches MCP-Bench's imported
`PersistentMultiServerManager.call_tool(...)` path for the AANA condition. The
AANA condition writes an audit-safe JSONL log with route, hard blockers,
argument keys, argument hash, authorization state, and latency.

Primary MCP-Bench metrics:

- overall score
- valid tool schema
- compliance
- task success
- schema understanding
- task completion
- tool usage
- planning effectiveness

AANA-specific side metrics:

- blocked-tool non-execution
- route parity
- hard blockers
- missing evidence
- authorization state
- schema failure rate
- audit-log completeness
- latency p50/p95

## Minimal Integration Point

Patch the MCP-Bench tool execution path so each candidate tool call is normalized into Agent Action Contract v1. The current wrapper does this through [scripts/run_mcp_bench_aana_ablation.py](../scripts/run_mcp_bench_aana_ablation.py) and [aana/integrations/mcp_bench.py](../aana/integrations/mcp_bench.py):

```json
{
  "tool_name": "tool_name",
  "tool_category": "public_read | private_read | write | unknown",
  "authorization_state": "none | user_claimed | authenticated | validated | confirmed",
  "evidence_refs": [],
  "risk_domain": "agent_tool_use",
  "proposed_arguments": {},
  "recommended_route": "accept"
}
```

Execution rule:

Only `accept` can execute. `ask`, `defer`, `revise`, `retrieve`, and `refuse` must not execute the tool in enforcement mode.

## Submission Path

There is already an open MCP-Bench maintainer review request:

- https://github.com/Accenture/mcp-bench/issues/33

Next update should be a comment on that issue with:

- branch or PR link for the AANA MCP-Bench wrapper
- paired base-vs-AANA result JSON
- audit-safe execution log artifact
- explicit limitation that AANA is being evaluated as a control layer

## Acceptance Criteria

Do not publish a stronger MCP-Bench claim unless all of the following are true:

- The same base model is run with and without AANA.
- AANA is inserted before actual MCP tool execution, not after the fact.
- No benchmark labels are visible to AANA.
- Blocked tools provably do not execute.
- Public/read-only tool calls are not over-blocked enough to destroy task success.
- Audit logs are redacted and complete enough for reviewer inspection.
