---
license: mit
tags:
  - agent-control
  - evaluation
  - auditability
  - safety
  - hallucination-detection
  - pii
pretty_name: AANA Control-Layer Evidence Pack
---

# AANA Control-Layer Evidence Pack

This dataset card template describes public AANA validation artifacts used to evaluate AANA as an audit/control/verification/correction layer.

AANA makes agents more auditable, safer, more grounded, and more controllable.

## Intended Use

The evidence pack is for:

- Calibration analysis.
- Held-out validation.
- External reporting of measured AANA behavior.
- Reproducible audit/control-layer comparisons.

It is not for training and reporting on the same split. Never use the same split for tuning and public claims.

## What AANA Adds For Reviewers

The reviewed claim is not that AANA replaces a capable base agent. The reviewed
claim is that AANA standardizes and validates the control layer around proposed
agent actions:

```text
agent proposes -> AANA checks -> tool executes only if route == accept
```

The artifacts test whether AANA can provide:

- a structured Agent Action Contract before execution,
- evidence and authorization-aware routing,
- hard blockers that prevent wrapped tool execution,
- correction/recovery suggestions for ask, retrieve, revise, defer, or refuse,
- audit-safe decision metadata,
- matching decision shape across CLI, SDK, FastAPI, MCP, and middleware surfaces.

## Dataset Families

- Privacy and PII routing.
- Grounded QA and hallucination checks.
- Agent tool-use and MCP-style tool calls.
- Cross-domain action gating.
- Customer support, finance, ecommerce/retail, research, and security adapter validation.

## Expected Metrics

- Unsafe-action recall.
- Private-read/write gating quality.
- Unsupported-claim recall.
- PII recall and redaction correctness.
- False positive rate.
- Safe allow rate.
- Ask/defer/refuse route quality.
- Schema failure rate.
- Integration latency.

## Current Diagnostic Findings

- Safety/adversarial prompt routing: deterministic AANA preserves safe allow but misses many harmful prompts; a diversified request-level verifier improves harmful-request recall while conservative calibration protects safe allow. AdvBench transfer remains weak, so this is not a content-moderation claim.
- Finance/high-risk QA: a controlled FinanceBench diagnostic shows supported filing answers are allowed and unsupported finance overclaims are routed to revise/defer. This is not official FinanceBench leaderboard evidence or investment-advice evaluation.
- Governance/compliance policy routing: a small diagnostic over Hugging Face policy-doc metadata plus repo-heldout policy cases shows citation, missing-evidence, private-data export, destructive-action, and human-review routing behavior. This is not legal, regulatory, or platform-policy certification.
- Integration validation v1: held-out tool-call cases show route parity, blocked-tool non-execution, decision-shape parity, audit completeness, and zero schema failures across CLI, Python SDK, TypeScript SDK, FastAPI, MCP, and middleware surfaces. This validates platform wiring, not raw agent task success.

## Peer-Review Manifest

The public peer-review dataset includes
`data/aana_peer_review_package_manifest.json`, which records the exact AANA
package version, git commit, eval case counts, calibration-vs-held-out split
boundaries, metrics, failure cases, false positives, unsupported domains,
latency, and commands to reproduce the package.

## Split Isolation

Public reports must identify whether each split was used for:

- `calibration`
- `heldout_validation`
- `external_reporting`

The same split must not be used for both adapter tuning and public performance claims.

## Current Evidence Boundary

AANA is production-candidate as an audit/control/verification/correction layer.

AANA is not yet proven as a raw agent-performance engine. This dataset card should not be used to imply that AANA alone outperforms base planners on raw task success or has raw agent-performance superiority.

## Related Artifacts

- Public artifact hub: `https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4`
- Public peer-review evidence pack: `https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack`
- Dataset registry: `examples/hf_dataset_validation_registry.json`
- HF dataset proof report: `docs/hf-dataset-proof-report.md`
- Production-candidate evidence pack: `docs/aana-production-candidate-evidence-pack.md`
- Agent Action Contract v1: `docs/agent-action-contract-v1.md`

