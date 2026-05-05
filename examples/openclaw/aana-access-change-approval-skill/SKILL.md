# AANA Access Change Approval Skill

Use this skill when an OpenClaw-style agent may draft, review, approve, summarize, or route an access permission change.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, change roles, grant permissions, revoke permissions, or execute an approval on its own.

## Core Principle

Access changes should be authority-backed, least-privilege, scoped, approved, time-bound, and auditable before they affect an identity, role, group, service account, dataset, environment, or production system.

The agent should separate:

- who requested access,
- what authority the requester has,
- what exact role, scope, system, tenant, or dataset is requested,
- whether least privilege is satisfied,
- whether approval is recorded by the right owner,
- whether expiration or periodic review is declared,
- what evidence is missing,
- whether a human reviewer or IAM owner must decide.

## When To Use

Use this skill before:

- approving, denying, drafting, or summarizing an access request,
- adding a user to a group, role, project, dataset, repository, or environment,
- changing production, admin, billing, security, customer-data, or deploy permissions,
- extending or removing an access expiration,
- claiming approval exists,
- describing why access is safe,
- routing access decisions to a manager, system owner, security owner, or IAM queue.

## Access Risk Classes

Treat these as higher risk:

- production, admin, break-glass, deploy, billing, security, customer-data, or data-export permissions,
- service-account, cross-tenant, privileged group, or wildcard access,
- access without expiration, owner approval, ticket context, or requester authority,
- requests that combine broad scope with vague purpose,
- access decisions that could expose private data, regulated records, secrets, or financial systems.

## AANA Access Review Loop

1. Identify the requested principal, role, target system, scope, and duration.
2. Check requester authority and whether the request is tied to a legitimate work item.
3. Check least privilege against the role catalog.
4. Check approval evidence from the right manager, system owner, data owner, or security reviewer.
5. Check expiration, review cadence, and revocation path.
6. Check whether the request exposes private, regulated, security, or production assets.
7. Choose action: accept, revise, ask, retrieve, defer, refuse, or route to human review.

## Required Evidence

Use redacted summaries of:

- IAM request,
- role catalog,
- approval record,
- requester authority,
- target resource scope,
- requested expiration,
- policy or access standard.

Do not include raw directory dumps, secrets, credentials, token material, private personnel files, or unrelated group memberships.

## Decision Rule

- If requester authority, least privilege, scope, approval, and expiration are verified, accept the review result.
- If scope is too broad or expiration is missing, revise the access request.
- If requester authority, role fit, owner approval, or purpose is unclear, ask or retrieve evidence.
- If the request touches high-risk systems, defer to the required owner or security queue.
- If the request bypasses approval, grants excessive privilege, or exposes unauthorized private data, refuse the unsafe action.

## Output Pattern

```text
Access change review:
- Requester authority: verified / missing / insufficient
- Scope: least-privilege / too broad / unclear
- Approval: recorded / missing / wrong owner / needs review
- Expiration: present / missing / excessive
- Risk: standard / elevated / strict
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
