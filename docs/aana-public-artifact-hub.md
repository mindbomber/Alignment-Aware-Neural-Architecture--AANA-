# AANA Public Artifact Hub

This is the canonical public artifact map for AANA.

Public claim: AANA makes agents more auditable, safer, more grounded, and more controllable.

Claim boundary: AANA is currently positioned as an audit/control/verification
and correction layer around agents. It is not yet proven as a raw
agent-performance engine and must not be claimed to have raw agent-performance
superiority.

## What AANA Adds

AANA is not just a prompt guardrail, moderation classifier, LLM-as-judge prompt,
or framework-specific middleware. It defines a typed pre-action contract and a
uniform enforcement rule:

```text
agent proposes -> AANA checks -> tool executes only if route == accept
```

The public artifacts let reviewers inspect whether AANA provides structured
evidence/auth-aware routing, hard blockers, correction/recovery suggestions,
audit-safe logs, and the same decision shape across CLI, SDK, API, MCP, and
middleware surfaces.

## Canonical Hub

- Hugging Face collection:
  <https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4>

## Artifacts

| Surface | Purpose | Link |
|---|---|---|
| Model repo | AANA architecture card, limitations, and usage. | <https://huggingface.co/mindbomber/aana> |
| Dataset repo | AANA eval cases, held-out/validation splits, result artifacts, and reproduction script. | <https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack> |
| Space | Live "try AANA" demo for candidate answers/actions, evidence, routes, AIx score, and hard blockers. | <https://huggingface.co/spaces/mindbomber/aana-demo> |
| Technical report | Architecture interpretation, limitations, benchmark boundary, and reviewer questions. | <https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/aana-agent-action-technical-report.md> |

## Bundle ID Policy

`government_civic` is the canonical product-bundle ID. `civic_government` is
kept as a backward-compatible alias for older starter-pilot-kit paths and
commands.

## Reviewer Path

1. Start with the model repo for the architecture boundary and usage pattern.
2. Run the Space to inspect AANA routing behavior interactively.
3. Inspect the dataset repo for measured privacy, grounded QA, tool-use, and
   integration validation artifacts.
4. Read the technical report for the architecture interpretation, limitations,
   and open reviewer questions.
5. Use the [public review and adoption guide](public-review-and-adoption.md) to
   challenge route correctness, evidence handling, authorization assumptions,
   blocked-tool non-execution, audit safety, and integration parity.

## Peer-Review Package Contents

The dataset repo includes a machine-readable peer-review manifest at
`data/aana_peer_review_package_manifest.json` with:

- exact AANA package version and git commit
- eval case counts and source artifacts
- calibration split vs held-out split boundaries
- metrics for privacy, grounded QA, tool-use, and integration validation
- failure cases and false positives
- unsupported domains and public-claim boundaries
- integration latency measurements
- commands to reproduce the package and validation checks

## Current Diagnostic Updates

- Safety/adversarial prompt routing: deterministic AANA preserves safe allow
  but misses many harmful prompts; a diversified request-level verifier improves
  harmful-request recall while conservative calibration protects safe allow.
  AdvBench transfer remains weak, so this is not a content-moderation claim.
- Finance/high-risk QA: a controlled FinanceBench diagnostic shows supported
  filing answers are allowed and unsupported finance overclaims are routed to
  revise/defer. This is not official FinanceBench leaderboard evidence or
  investment-advice evaluation.
- Governance/compliance policy routing: a small diagnostic over Hugging Face
  policy-doc metadata plus repo-heldout policy cases shows citation,
  missing-evidence, private-data export, destructive-action, and human-review
  routing behavior. This is not legal, regulatory, or platform-policy
  certification.
- Integration validation v1: held-out tool-call cases show route parity,
  blocked-tool non-execution, decision-shape parity, audit completeness, and
  zero schema failures across CLI, Python SDK, TypeScript SDK, FastAPI, MCP, and
  middleware surfaces. This validates platform wiring, not raw agent task
  success.

## What This Hub Does Not Claim

- It does not claim AANA is production-certified.
- It does not claim AANA is a generally superior base agent.
- It does not merge probe-enabled or answer-key-style diagnostic results into
  public benchmark claims.
- It does not replace benchmark-maintainer or independent human-reviewed
  evaluation for stronger leaderboard claims.
