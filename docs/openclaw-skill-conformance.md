# OpenClaw Skill Conformance

This document defines the minimum behavior for AANA OpenClaw-style skills and plugins.

## When To Call AANA

Call AANA before an agent sends, publishes, books, buys, exports, deletes, moves, writes, commits, deploys, changes permissions, shares private data, answers with citations, routes medical/legal/financial content, or performs another action that is hard to undo.

Call AANA when any of these are true:

- the action depends on private, regulated, account, billing, payment, medical, legal, financial, HR, customer, security, deployment, or government data,
- evidence is incomplete, stale, untrusted, or outside the approved source registry,
- the candidate makes a factual, policy, pricing, eligibility, refund, health, legal, tax, investment, security, release, or customer-impact claim,
- the action has external side effects or irreversible consequences,
- the user asked for a guardrail, review, approval, or audit trail.

If no configured AANA checker or bridge is available, use manual review and do not treat missing automation as permission to proceed.

## Runtime Result Rule

Skills and plugins must treat the AANA result as an action gate:

- Proceed only when `gate_decision` is `pass`, `recommended_action` is `accept`, and `aix.hard_blockers` is empty.
- If `recommended_action` is `revise`, revise with the safe response or rerun the check before acting.
- If `recommended_action` is `ask`, ask the user for missing information.
- If `recommended_action` is `defer`, route to stronger evidence, a domain owner, a review queue, or a human reviewer.
- If `recommended_action` is `refuse`, do not perform the unsafe part of the action.
- If `aix.decision` disagrees with `recommended_action`, use the stricter route.
- If `candidate_aix` is present, treat it as the score for the proposed action before correction, not as approval for final action.
- Never use a high numeric `aix.score` to override hard blockers or a non-accept recommended action.

## Audit Boundary

Skills should not write audit logs by default. When an audit record is required, use the configured AANA runtime or approved host audit tool and store only redacted decision metadata:

- adapter or workflow id,
- gate decision,
- recommended action,
- AIx score and decision summary,
- hard blockers,
- violation codes,
- fingerprints or redacted summaries.

Do not store raw prompts, candidates, private records, evidence, safe responses, secrets, access tokens, payment data, medical records, legal files, or full customer/account records in skill-created notes.

## Skill Boundary

Instruction-only skills must not install dependencies, execute commands, infer local checker paths, call network services, write event files, persist memory, or silently expand task scope.

Runtime connector plugins may call only the reviewed bridge endpoint configured by the user or administrator. They must reject non-loopback bridge URLs, respect bridge errors, and return bridge responses without promising direct action.

## High-Risk Examples

Canonical high-risk skill examples are indexed in [`examples/openclaw/high-risk-workflow-examples.json`](../examples/openclaw/high-risk-workflow-examples.json). The examples map skill surfaces to adapter ids, workflow fixture files, expected risk, required evidence, and the required agent behavior when AANA returns `revise`, `ask`, `defer`, or `refuse`.
