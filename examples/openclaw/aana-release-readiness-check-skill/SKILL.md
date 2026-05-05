# AANA Release Readiness Check Skill

Use this skill before an OpenClaw-style agent creates a release, tag, changelog, package, marketplace listing, deployment note, artifact, or public version snapshot.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, or create releases on its own.

## Core Principle

Releases should be evidence-backed, scoped, documented, tested, permissioned, and reversible where possible. Do not publish release claims without matching artifacts and validation.

## Required Checks

- version, tag, artifact, branch, package, and release target
- tests, checks, or evidence supporting release claims
- changelog, migration notes, docs, examples, and known limitations
- security, secrets, dependencies, generated files, and large artifacts
- rollback path, compatibility, breaking changes, and user impact
- explicit approval for publishing the release or tag

## Release Risk Classes

Treat these as higher risk:

- public releases, marketplace listings, production deployments, security fixes, breaking changes, migrations, and package publishing,
- claims about safety, reliability, compliance, benchmark performance, compatibility, or production readiness,
- unverified artifacts, wrong version numbers, stale docs, missing changelogs, generated files, large files, or secrets,
- releases without rollback, known limitations, migration instructions, or test evidence.

## Evidence Rules

Do not publish release claims unless they match available evidence. If tests were not run, say so. If artifacts were not verified, block or request verification before release.

## Artifact And Version Rules

Verify that the tag, package, artifact, docs, changelog, and release notes refer to the same version and commit. Check that downloads, examples, and marketplace references point to the intended artifacts.

## Review Payload

When using a configured AANA checker, send only a minimal redacted review payload:

- `release_target`
- `evidence_status`
- `docs_status`
- `artifact_status`
- `approval_status`
- `release_risks`
- `blocker_reason`
- `safe_alternative`
- `recommended_action`

Do not include secrets, private release notes, credentials, full logs, or unrelated repository data when a redacted summary is enough.

## Decision Rule

- If artifacts, tests, docs, scope, and approval are ready, proceed.
- If tests, docs, artifacts, or changelog are missing, revise or retrieve evidence.
- If breaking changes, security impact, or public claims are involved, route to review.
- If release approval is missing, request approval.
- If the release is unsupported, unsafe, or misleading, block.

## Output Pattern

```text
AANA release gate:
- Target: tag / release / package / deployment_note / marketplace_listing
- Evidence: sufficient / partial / missing / failing / unknown
- Docs: ready / missing / stale / incomplete
- Artifacts: ready / missing / mismatched / unverified
- Approval: approved / required / unclear / denied
- Decision: proceed / revise / retrieve / request_approval / route_to_review / block
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

