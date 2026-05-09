# Authorization State Hardening

AANA treats `authorization_state` as a declared runtime signal, then checks whether redacted evidence refs support that declaration.

## States

- `none`: no authorization evidence.
- `user_claimed`: the user says they are allowed, but no runtime authentication exists.
- `authenticated`: identity/session was verified.
- `validated`: the target object, policy, ownership, or eligibility was checked.
- `confirmed`: the user or authorized actor explicitly approved the exact action.

## Routing Rules

- Public reads can run without identity auth only when the tool and arguments are truly public/non-sensitive.
- Reads involving account, customer, employee, patient, payment, order, ticket, or similar identity-bound arguments are treated as private reads even if declared `public_read`.
- Private reads need at least `authenticated`.
- Writes need validation and explicit confirmation.
- High-risk writes such as delete, transfer, pay, purchase, reset, send, deploy, grant, or revoke require `confirmed` evidence before execution.
- If declared authorization is stronger than the evidence supports, AANA downgrades the effective state and fails closed.

The gate returns `authorization_report` with declared state, evidence-supported state, effective state, support labels, and downgrade status.
