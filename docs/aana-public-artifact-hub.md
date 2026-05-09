# AANA Public Artifact Hub

This is the canonical public artifact map for AANA.

Public claim: AANA is an architecture for making agents more auditable, safer,
more grounded, and more controllable.

Claim boundary: AANA is currently positioned as an audit/control/verification
and correction layer around agents. It is not yet proven as a raw
agent-performance engine.

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

## Reviewer Path

1. Start with the model repo for the architecture boundary and usage pattern.
2. Run the Space to inspect AANA routing behavior interactively.
3. Inspect the dataset repo for measured privacy, grounded QA, tool-use, and
   integration validation artifacts.
4. Read the technical report for the architecture interpretation, limitations,
   and open reviewer questions.

## What This Hub Does Not Claim

- It does not claim AANA is production-certified.
- It does not claim AANA is a generally superior base agent.
- It does not merge probe-enabled or answer-key-style diagnostic results into
  public benchmark claims.
- It does not replace benchmark-maintainer or independent human-reviewed
  evaluation for stronger leaderboard claims.
