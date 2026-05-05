# AANA Incident Communications Skill

Use this skill when an OpenClaw-style agent may draft, revise, approve, publish, or summarize an incident update for customers, status pages, executives, support teams, or internal responders.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, update a status page, notify customers, page responders, or execute incident actions on its own.

## Core Principle

Incident communications should be faithful to the incident timeline, clear about customer impact, honest about mitigation status, careful with ETA claims, and approved before publication.

The agent should separate:

- confirmed incident facts,
- suspected or unconfirmed causes,
- customer-visible impact,
- mitigation and recovery status,
- open unknowns,
- ETA or commitment language,
- private operational notes,
- approval state for external communication.

## When To Use

Use this skill before:

- posting or drafting a status page update,
- sending customer or executive incident communications,
- summarizing incident impact or mitigation,
- claiming root cause, resolution, affected scope, severity, or ETA,
- translating internal on-call notes into customer-visible language,
- routing incident updates for communications approval.

## Incident Risk Classes

Treat these as higher risk:

- active incidents, security incidents, data exposure, payment failures, outages, degraded service, public status pages, regulatory or contractual impact,
- root-cause claims before postmortem approval,
- ETA, restoration, compensation, SLA, legal, or compliance promises,
- details from private on-call notes, customer data, logs, credentials, infrastructure topology, or vulnerability context,
- mismatch between internal timeline, customer impact, and external wording.

## AANA Incident Review Loop

1. Identify the audience, channel, severity, and proposed update.
2. Check severity and customer impact against the incident timeline.
3. Check mitigation status and whether the update overstates recovery.
4. Check ETA, root-cause, SLA, and compensation claims.
5. Check private operational details and sensitive customer information.
6. Check status page or communications approval policy.
7. Choose action: accept, revise, ask, retrieve, defer, refuse, or route to human review.

## Required Evidence

Use redacted summaries of:

- incident timeline,
- status page policy,
- on-call notes,
- affected services,
- mitigation state,
- communications approval state.

Do not include raw logs, credentials, customer records, private responder notes, exploit details, internal topology, or unapproved root-cause details.

## Decision Rule

- If severity, impact, mitigation, ETA language, privacy, and approval are verified, accept the update.
- If wording overstates impact, recovery, root cause, or ETA, revise.
- If customer impact or current mitigation state is unclear, retrieve evidence or ask the incident owner.
- If external communication approval is missing, defer to communications or incident command.
- If the update leaks private data or asserts false incident facts, refuse the unsafe portion.

## Output Pattern

```text
Incident communications review:
- Severity: confirmed / unclear / mismatched
- Customer impact: supported / overstated / missing
- Mitigation: accurate / overstated / stale
- ETA: supported / unsupported / removed
- Approval: approved / missing / needs incident command
- Decision: accept / revise / ask / retrieve / defer / refuse
```

## AANA Runtime Result Handling

When a configured AANA checker or bridge returns a result, treat it as an action gate, not as background advice:

- Proceed only when `gate_decision` is `pass`, `recommended_action` is `accept`, and `aix.hard_blockers` is empty.
- If `recommended_action` is `revise`, use the safe response or revise the plan, then recheck before acting.
- If `recommended_action` is `ask`, ask the user for the missing information before acting.
- If `recommended_action` is `defer`, route to stronger evidence, a domain owner, a review queue, or a human reviewer.
- If `recommended_action` is `refuse`, do not perform the unsafe part of the action.
- If `aix.decision` disagrees with `recommended_action`, follow the stricter route.
- Treat `candidate_aix` as the risk score for the proposed candidate before correction, not as permission to act.
- Never use a high numeric `aix.score` to override hard blockers, missing evidence, or a non-accept recommendation.

For audit needs, store only redacted decision metadata such as adapter id, `gate_decision`, `recommended_action`, AIx summary, hard blockers, violation codes, and fingerprints. Do not store raw prompts, candidates, private records, evidence, secrets, safe responses, or outputs from the skill.
