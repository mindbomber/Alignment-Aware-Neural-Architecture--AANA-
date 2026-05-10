# AANA: A Pre-Action Control Layer For Auditable AI Agents

## Summary

AANA is a pre-action control layer for AI agents: agents propose actions, AANA
checks evidence, authorization, and risk, and tools execute only when the route
is `accept`.

The current claim is intentionally narrow. AANA is useful as an
audit/control/verification/correction layer around agents. It is not yet proven
as a raw agent-performance engine.

## Problem

Agentic systems can propose useful actions, but the moment an agent can call
tools, read private data, write records, send messages, deploy code, or answer
from retrieved evidence, the key question changes:

```text
Should this proposed answer or action execute now, with this evidence,
authorization state, risk domain, and audit record?
```

Prompt instructions, moderation classifiers, LLM judges, and framework-specific
middleware help, but they often leave the final execution rule implicit or tied
to one runtime. AANA makes that rule explicit and testable.

## Architecture

AANA wraps a base agent or model instead of replacing it:

```text
agent proposes -> AANA checks -> tool executes only if route == accept
```

The runtime architecture is:

```text
S = (f_theta, E_phi, R, Pi_psi, G)
```

- `f_theta`: the base model, app, or agent that proposes an answer or tool call.
- `E_phi`: verifier stack for evidence, authorization, risk, route, and schema.
- `R`: retrieval or evidence-recovery layer.
- `Pi_psi`: correction policy that can revise, retrieve, ask, defer, or refuse.
- `G`: final alignment gate that emits a route and audit-safe decision event.

AANA is designed to answer an operational deployment question, not to replace
model training or post-training alignment: for this proposed action, should the
system accept, revise, retrieve, ask, defer, or refuse?

## Contract

The public Agent Action Contract v1 freezes the seven required fields used for
pre-tool-call checks:

- `tool_name`
- `tool_category`
- `authorization_state`
- `evidence_refs`
- `risk_domain`
- `proposed_arguments`
- `recommended_route`

The execution rule is uniform across CLI, SDK, API, MCP, and middleware:

```text
Only route == accept can execute.
```

All other routes must block the original action and return recovery guidance:

- `revise`: repair the answer or action and recheck.
- `retrieve`: collect missing evidence and recheck.
- `ask`: ask the user for missing information or authorization.
- `defer`: escalate to stronger evidence, review, or a human workflow.
- `refuse`: stop the unsafe, unsupported, or unauthorized action.

## Experiments

The current evidence pack tests AANA as a control layer, not as a standalone
agent. Results are labeled as held-out, diagnostic, validation, or protocol
artifacts according to the public claims policy.

Main experiment families:

- Privacy/PII: checks whether AANA catches sensitive data before unsafe output,
  logging, or tool use.
- Grounded QA/hallucination: checks whether unsupported answers route to
  revise, retrieve, or defer instead of being accepted blindly.
- Agent tool-use control: compares permissive execution, contract-only gating,
  deterministic AANA, and optional semantic verification on tool-call traces.
- Public/private read routing: checks whether harmless public reads are allowed
  while private identity-bound reads require adequate authorization.
- Authorization robustness: perturbs evidence with missing, stale,
  contradictory, mislabeled, or malformed authorization signals.
- Safety/adversarial prompt routing: tests unsafe-request routing while
  tracking safe-prompt over-refusal.
- Finance and governance diagnostics: tests evidence-bound routing in
  higher-risk answer and policy contexts.
- Integration validation: verifies route parity, blocked-tool non-execution,
  audit completeness, schema behavior, and latency across CLI, Python SDK,
  TypeScript SDK, FastAPI, MCP, OpenAI Agents SDK, LangChain, AutoGen, and
  CrewAI examples.

Observed pattern:

- A plain permissive agent preserves safe allow but does not block unsafe or
  unauthorized actions.
- Simple classifiers and prompt-only guards can improve blocking but tend to
  over-block safe cases.
- Contract-only gates are useful but brittle when evidence is noisy.
- AANA's value appears strongest when the proposed action is missing evidence,
  permission, scope, or route justification, because AANA can check, recover,
  ask, defer, or refuse before execution.

## Failures

The experiments also exposed real weaknesses:

- Early tool-use runs over-blocked because AANA treated noisy or incomplete
  schemas too literally.
- Public/private read routing worked best when authorization fields were clean;
  noisy evidence required a separate robustness experiment.
- Privacy/PII improvements increased recall but needed calibration to reduce
  false positives and restore safe allow rate.
- Grounded QA improved on checkable numeric/entity cases, but subtle baseless
  claims and semantic contradictions required stronger sentence-level
  verification.
- Safety/adversarial routing remains incomplete. Deterministic AANA preserves
  safe allow but misses many harmful prompts; semantic verification improves
  recall but must be calibrated before held-out use.
- Finance and governance results are diagnostic, not official leaderboard,
  legal, regulatory, or platform-policy certification.

These failures are part of the public evidence. They define where AANA should
be improved and where stronger claims are not justified yet.

## Limitations

AANA should not be described as generally aligned, production-certified, or
superior to raw agents on task success.

Current limitations:

- Some labels are policy-derived from AANA evaluation scripts, not independent
  human-review labels.
- Current experiments evaluate routing before execution, not arbitrary
  end-to-end agent success.
- Stronger claims require benchmark-maintainer accepted protocols, external
  human-reviewed labels, or production pilots with domain-owner signoff.
- Adapter performance depends on evidence quality, authorization signals,
  connector design, and deployment policy.
- AANA can over-block when evidence is missing, stale, contradictory, or poorly
  represented.
- Public demos use safe synthetic executors; production deployments still need
  security review, audit retention policy, incident response, and connector
  permission review.

## How To Reproduce

Run the full local platform validation gate:

```powershell
python scripts\validate_aana_platform.py --timeout 240
```

Run the integration-stack proof:

```powershell
python scripts\validation\validate_agent_integrations.py
```

Rebuild the peer-review evidence pack:

```powershell
python scripts\publication\build_peer_review_evidence_pack.py
```

Validate a downloaded Hugging Face evidence pack:

```powershell
python scripts\reproduce.py --pack-dir .
```

## Public Artifacts

- Try AANA: <https://huggingface.co/spaces/mindbomber/aana-demo>
- Model card: <https://huggingface.co/mindbomber/aana>
- Peer-review evidence pack: <https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack>
- Public artifact hub: <https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4>
- Agent Action Contract v1: [agent-action-contract-v1.md](agent-action-contract-v1.md)
- Detailed agent-action report: [aana-agent-action-technical-report.md](aana-agent-action-technical-report.md)

## Review Request

The most useful peer-review feedback is concrete:

- Are routes correct?
- Are false positives acceptable?
- Is evidence handling sufficient?
- Does this generalize beyond examples?

Please include the event, AANA decision, expected route, and evidence context
when reporting failures.
