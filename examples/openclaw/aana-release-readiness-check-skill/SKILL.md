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
