# AANA + Apart Research Collaboration Brief

## Purpose

AANA may complement Apart Research projects that study AI safety, agent
security, model evaluation, dark patterns, memory/context attacks, cyber
capability evaluation, and model-edit side effects.

This brief is intended for a narrow, research-first outreach. It should not be
read as an Apart endorsement, partnership announcement, or claim that AANA
solves the underlying research problems. The goal is to identify one small
compatibility experiment where AANA can turn evaluation evidence into runtime
governance signals, hard blockers, remediation guidance, and redacted audit
artifacts.

## Best-Fit Surfaces

| Apart surface | AANA contribution angle | Why it fits |
| --- | --- | --- |
| Inference-time agent security | Add AANA as a practical pre-action gate for agent tools and workflow actions. | AANA already answers whether an agent action should `accept`, `revise`, `ask`, `defer`, or `refuse`. |
| DarkBench / dark-pattern evaluation | Map dark-pattern findings into AIx `B` component scores, manipulation violation codes, and hard blockers. | Dark-pattern evals need deployment-facing human-impact controls. |
| Prompt-worms / memory-context attacks | Add evidence-boundary and tool-call gating for suspicious memory or context influence. | AANA can block exfiltration, require trusted evidence, and log redacted decision metadata. |
| 3CB / cyber capability benchmarking | Provide defensive runtime controls for cyber-tool execution boundaries. | AANA can require authorization/evidence and fail closed for offensive or unauthorized actions. |
| SpecificityPlus / edit-failure benchmarks | Translate model-edit failures and side effects into deployment risk reports. | AANA can separate factual `P`, human-impact `B`, policy/scope `C`, and verifier-confidence `F` issues. |
| Interpretability starter / Neuron2Graph / DeepDecipher | Explore how interpretability evidence can support audit trails for blocked or escalated actions. | AANA can carry verifier and evidence summaries into AIx Reports without storing raw private data. |

## Strongest First Experiment

The lowest-friction starting point is an **AANA runtime governance wrapper for
inference-time agent security**:

```text
agent proposes tool/action
  -> AANA checks action contract, evidence, authorization, and risk
  -> AANA returns AIx score, hard blockers, and route
  -> action proceeds only when route == accept
  -> redacted audit record is written
```

This maps directly to Apart's interest in operational AI safety while staying
inside AANA's existing runtime-governance scope.

## Secondary Experiment

A second good target is a **DarkBench -> AIx Report adapter**:

```text
DarkBench result artifact
  -> AANA adapter maps dark-pattern categories into violation codes
  -> AIx Report summarizes human-impact risk, hard blockers, remediation,
     and monitoring requirements
```

This is useful if Apart wants benchmark outputs to become governance artifacts
that a safety reviewer, product owner, or compliance reviewer can inspect.

## What AANA Adds

AANA contributes:

- a stable Agent Action Contract and Workflow Contract;
- explicit action routes: `accept`, `revise`, `retrieve`, `ask`, `defer`,
  and `refuse`;
- AIx scores with `P`, `B`, `C`, and optional `F` components;
- hard blockers that override numeric scores;
- evidence-gap detection;
- fail-closed runtime behavior for consequential actions;
- redacted audit logs and reviewer reports;
- compatibility paths for CLI, Python SDK, TypeScript SDK, and FastAPI.

The value proposition is:

```text
Apart evaluates safety-relevant model or agent behavior.
AANA turns that evidence into runtime gates and audit-ready governance artifacts.
```

## Boundaries

AANA should be positioned as a complement to Apart's research, not a replacement
for it.

Acceptable claim:

```text
AANA can wrap selected Apart-style safety evaluations or agent-security traces
and produce deployment-facing AIx audit signals, hard blockers, evidence gaps,
and runtime action gates.
```

Avoid:

```text
AANA validates Apart's research.
AANA certifies models as safe.
AANA replaces DarkBench, 3CB, prompt-worms, interpretability work, or other
Apart evaluations.
```

## Suggested Outreach Message

```text
Hi Apart Research team,

I am working on AANA, an open-source runtime governance and AIx audit layer for
AI agents and high-risk AI workflows.

I noticed several Apart projects where AANA may be a useful compatibility layer,
especially inference-time agent security, DarkBench, prompt-worms, 3CB, and
SpecificityPlus. AANA's role would not be to replace those evaluations. The
goal would be to consume selected evaluation outputs or agent traces and turn
them into deployment-facing governance artifacts: AIx scores, hard blockers,
evidence gaps, remediation guidance, redacted audit logs, and fail-closed
runtime action gates.

Would you be open to a small compatibility experiment around one repo or
artifact shape? The lowest-friction starting point may be an inference-time
agent security trace or a DarkBench-style result artifact.

AANA repo:
https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-

I would be glad to keep the scope narrow and research-first: one fixture, one
adapter, one report, and a clear claim boundary.

Thank you,
Armando Sori
```

## Repo References

- Runtime contracts: `docs/agent-action-contract-v1.md`,
  `docs/workflow-contract.md`
- Runtime governance: `docs/python-runtime-api.md`,
  `docs/fastapi-service.md`
- AIx audit/reporting: `docs/aana-aix-audit-enterprise-ops-pilot-packet.md`
- MLCommons compatibility model:
  `docs/aana-mlcommons-integration-brief.md`
- Safety evidence examples:
  `docs/evidence/peer_review/safety_adversarial_hf_experiment_results.json`
