# AANA Maintainer Review / Benchmark Submission Request

Status: `maintainer_review_request`

This pack asks MCP-Bench and MCP Security Bench maintainers to review whether
AANA can be evaluated as a control layer or wrapper around an existing base
agent.

It is not an official leaderboard claim.

## One-Sentence Claim

AANA is a pre-action control layer for AI agents: agents propose actions, AANA
checks evidence/auth/risk, and tools execute only when the route is `accept`.

## What We Are Asking Maintainers To Review

We are asking benchmark maintainers whether a control-layer submission track is
acceptable.

Proposed paired protocol:

1. Run the benchmark's normal base agent/model path.
2. Run the same base agent/model with AANA inserted immediately before actual
   tool execution.
3. Hide benchmark labels from AANA.
4. Keep the base model, task set, judge, server setup, and prompts the same
   across both conditions where the benchmark permits it.
5. Report normal benchmark metrics plus control-layer side metrics.

Runtime pattern:

```text
base agent proposes -> AANA checks -> tool executes only if route == accept
```

## Why AANA Is Not A Standalone Model Row

AANA should not be treated as a better base model or raw agent-performance
engine. It is a verifier/gate/correction layer around proposed tool calls.

The benchmark question is therefore:

```text
Does adding AANA before tool execution reduce unsafe/private/write executions
while preserving safe public reads, task success, and auditability?
```

## Agent Action Contract v1

Each proposed tool call is normalized into:

```json
{
  "tool_name": "tool_or_mcp_method",
  "tool_category": "public_read | private_read | write | unknown",
  "authorization_state": "none | user_claimed | authenticated | validated | confirmed",
  "evidence_refs": [],
  "risk_domain": "agent_tool_use",
  "proposed_arguments": {},
  "recommended_route": "accept"
}
```

Execution rule:

```text
Only accept can execute.
```

Routes `ask`, `defer`, `revise`, `retrieve`, and `refuse` must not execute the
original tool call in enforcement mode.

## Proposed Metrics

Benchmark-native metrics:

- task success
- tool-call success
- valid tool-name rate
- schema compliance
- task completion score
- tool selection score
- planning effectiveness

AANA control-layer side metrics:

- blocked-tool non-execution rate
- unsafe/private/write execution rate
- safe public-read allow rate
- route counts: `accept`, `ask`, `defer`, `revise`, `retrieve`, `refuse`
- schema failure rate
- audit-log completeness
- authorization-state routing accuracy
- latency p50/p95
- false-positive / over-block examples

## MCP-Bench Request

Target: <https://github.com/Accenture/mcp-bench>

Existing maintainer thread:
<https://github.com/Accenture/mcp-bench/issues/33>

Repo-owned implementation:

- wrapper: [aana/integrations/mcp_bench.py](../aana/integrations/mcp_bench.py)
- paired runner: [scripts/benchmarks/run_mcp_bench_aana_ablation.py](../scripts/benchmarks/run_mcp_bench_aana_ablation.py)
- unsafe/private/write diagnostic slice:
  [scripts/benchmarks/run_mcp_bench_unsafe_injection_slice.py](../scripts/benchmarks/run_mcp_bench_unsafe_injection_slice.py)
- detailed submission plan: [aana-mcp-bench-submission-plan.md](aana-mcp-bench-submission-plan.md)

Current local evidence:

- Clean-env six-task MCP-Bench slice:
  - base task success: `1.000`
  - base + AANA task success: `1.000`
  - AANA decisions: `81 accept`, `0 blocked`
  - AANA latency: p50 `2.778 ms`, p95 `7.911 ms`
- Unsafe/private/write injection slice:
  - plain unsafe executions: `6`
  - AANA unsafe executions: `0`
  - blocked-tool non-execution rate: `1.000`
  - safe public-read allow rate: `1.000`
  - AANA routes: `2 accept`, `4 ask`, `2 defer`

MCP-Bench-specific ask:

1. Would MCP-Bench accept a control-layer/wrapper submission track?
2. Should the next run use a benchmark-native task subset, a dedicated safety
   slice, or a maintainer-provided task list?
3. Which side metrics belong in a report without confusing them with raw
   model/task-performance leaderboard metrics?
4. Would maintainers prefer a PR, standalone result artifact, or continued
   discussion first?

## MSB / MCP Security Bench Request

Target: <https://github.com/dongsenzhang/MSB>

Existing maintainer thread:
<https://github.com/dongsenzhang/MSB/issues/3>

Repo-owned artifact:

- submission artifact doc: [aana-msb-mcp-security-bench.md](aana-msb-mcp-security-bench.md)
- runner: [scripts/benchmarks/run_msb_mcp_security_bench.py](../scripts/benchmarks/run_msb_mcp_security_bench.py)
- result JSON:
  [docs/evidence/peer_review/msb_mcp_security_bench_aana_results.json](evidence/peer_review/msb_mcp_security_bench_aana_results.json)

Current protocol-level evidence:

- cases: `124`
- MSB attack cases: `60`
- AANA attack block rate / unsafe-action recall: `1.000`
- safe public-read allow rate: `1.000`
- benign consequential-action control rate: `0.930`
- schema failure rate: `0.000`
- route-family accuracy: `0.976`

MSB-specific limitation:

The current artifact converts Hugging Face dataset task/template rows into
Agent Action Contract v1 events. It is not a full replay of the MSB GitHub
harness over the complete generated attack execution logs.

MSB-specific ask:

1. Should AANA be inserted into MSB's native harness before MCP tool execution?
2. Should the result be submitted as a PR, standalone result artifact, or issue
   discussion?
3. Which MSB metrics should control-layer submissions report alongside attack
   block rate and safe public-read preservation?
4. Should maintainers audit the transformed labels/events before any stronger
   public claim is made?

## Links For Maintainers

- Try AANA: <https://huggingface.co/spaces/mindbomber/aana-demo>
- Agent Action Contract v1:
  <https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/agent-action-contract-v1.md>
- Short technical report:
  <https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/aana-pre-action-control-layer-technical-report.md>
- Peer-review evidence pack:
  <https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack>
- Public roadmap:
  <https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/public-roadmap.md>

## Claim Boundary

Do not claim:

- official MCP-Bench leaderboard status,
- official MSB leaderboard status,
- raw agent-performance superiority,
- production certification,
- or benchmark-maintainer acceptance before maintainers explicitly accept the
  protocol.

Acceptable current claim:

```text
AANA has protocol-level and local diagnostic evidence as a pre-tool-call
control layer. Stronger claims require a maintainer-accepted benchmark protocol
or external human-reviewed labels.
```
