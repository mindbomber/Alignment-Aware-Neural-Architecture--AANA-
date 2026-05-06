# Production MI Release Checklist

Status: milestone 15 production readiness gate.

Purpose: high-risk AANA actions must pass MI checks before direct execution. This checklist applies before sending, publishing, deploying, booking, purchasing, exporting, deleting, changing permissions, releasing code, or handing a consequential result to an external connector.

## Required Gate

Run `production_mi_readiness_gate(...)` on the result from `mi_boundary_batch(...)` or a pilot result that contains `mi_batch`.

Direct execution is allowed only when all release checks pass:

- MI boundary checks are present for the high-risk workflow.
- Every consequential handoff carries evidence metadata.
- No local or global AIx hard blockers exist.
- Global AIx is greater than or equal to the active accept threshold.
- Propagated assumptions, unsupported claims, stale evidence, and downstream premise links are resolved.

## Blocking Conditions

| Condition | Required route |
| --- | --- |
| MI checks missing | `defer` until the workflow is checked |
| evidence missing | `retrieve` evidence, then re-run MI |
| hard blockers exist | `refuse` or route to an approved human-review process |
| global AIx below threshold | `revise` or `defer`, then re-run MI |
| propagated assumptions unresolved | `revise` upstream output or `ask` for clarification, then re-run MI |

## Release Signoff

- Attach the redacted MI audit JSONL for the run.
- Attach the workflow or pilot result with raw private content excluded from release notes.
- Confirm the dashboard shows no unresolved propagated-risk signal for this workflow.
- Confirm the selected risk tier matches connectivity, irreversibility, privacy, security, and downstream blast radius.
- Confirm any human-review queue or incident channel exists before enabling direct execution.
