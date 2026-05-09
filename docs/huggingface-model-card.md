---
license: mit
library_name: aana
tags:
  - agent-control
  - agent-safety
  - auditability
  - groundedness
  - tool-use
  - verification
pipeline_tag: text-classification
---

# AANA: Agent Action Control Architecture

AANA makes agents more auditable, safer, more grounded, and more controllable.

This card describes AANA as a control-layer architecture and runtime package, not as a standalone frontier model. The intended pattern is:

```text
agent proposes -> AANA checks -> agent executes only if allowed
```

## What AANA Adds

Most existing approaches are prompt instructions, moderation/classification,
LLM-as-judge review, framework middleware, or opaque provider-side model
alignment. AANA is different because it standardizes the pre-action decision
itself:

```text
agent proposes -> AANA checks -> tool executes only if route == accept
```

AANA adds:

- A public Agent Action Contract v1 for pre-tool-call checks.
- Evidence/auth-aware routing across `accept`, `revise`, `retrieve`, `ask`, `defer`, and `refuse`.
- Hard execution rules: wrapped tools do not execute unless AANA returns `accept` with no hard blockers or schema failures.
- Correction and recovery suggestions for missing evidence, missing authorization, unsupported claims, or human-review escalation.
- Audit-safe decision metadata: route, AIx score, hard blockers, missing evidence, authorization state, and redacted log event.
- Python SDK, TypeScript SDK, CLI, FastAPI, MCP, and middleware surfaces with validated decision-shape parity.

## Public Boundary

AANA is production-candidate as an audit/control/verification/correction layer.

AANA is not yet proven as a raw agent-performance engine. Current evidence should be interpreted as support for action gating, verification, correction, and auditability claims, not as proof that AANA alone improves end-to-end task success across arbitrary agent benchmarks or has raw agent-performance superiority.

## Minimal Usage

```python
import aana

decision = aana.check_tool_call({
    "tool_name": "send_email",
    "tool_category": "write",
    "authorization_state": "user_claimed",
    "evidence_refs": [{"source_id": "draft_id:123", "kind": "tool_result"}],
    "risk_domain": "customer_support",
    "proposed_arguments": {"to": "customer@example.com"},
    "recommended_route": "accept",
})

print(decision["architecture_decision"]["route"])
```

Execute only when AANA returns `accept`, no hard blockers, and the relevant workflow policy allows the action.

## API Surface

- Python package: `aana`
- CLI: `aana agent-check`, `aana pre-tool-check`, `aana audit-summary`, `aana evidence-pack`
- FastAPI service: `POST /pre-tool-check`, `POST /agent-check`, `GET /health`
- TypeScript SDK: `@aana/integration-sdk`
- Contract spec: `docs/agent-action-contract-v1.md`

## Evidence Links

- Public artifact hub: `https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4`
- AANA Space: `https://huggingface.co/spaces/mindbomber/aana-demo`
- Peer-review evidence pack: `https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack`
- Production-candidate evidence pack: `docs/aana-production-candidate-evidence-pack.md`
- HF dataset proof report: `docs/hf-dataset-proof-report.md`
- Agent-action technical report: `docs/aana-agent-action-technical-report.md`
- Agent Action Contract v1: `docs/agent-action-contract-v1.md`

## Current Diagnostic Findings

- Safety/adversarial prompt routing: deterministic AANA preserves safe allow but misses many harmful prompts; a diversified request-level verifier improves harmful-request recall while conservative calibration protects safe allow. AdvBench transfer remains weak, so this is not a content-moderation claim.
- Finance/high-risk QA: a controlled FinanceBench diagnostic shows supported filing answers are allowed and unsupported finance overclaims are routed to revise/defer. This is not official FinanceBench leaderboard evidence or investment-advice evaluation.
- Governance/compliance policy routing: a small diagnostic over Hugging Face policy-doc metadata plus repo-heldout policy cases shows citation, missing-evidence, private-data export, destructive-action, and human-review routing behavior. This is not legal, regulatory, or platform-policy certification.
- Integration validation v1: held-out tool-call cases show route parity, blocked-tool non-execution, decision-shape parity, audit completeness, and zero schema failures across CLI, Python SDK, TypeScript SDK, FastAPI, MCP, and middleware surfaces. This validates platform wiring, not raw agent task success.

## Limitations

- Domain adapters require held-out validation before stronger claims.
- AANA can over-block if evidence or authorization state is incomplete.
- AANA does not replace a capable planner, retrieval system, domain policy source, or human escalation path.
- Production deployments still need live connector review, audit retention policy, incident response, security review, and domain-owner signoff.

