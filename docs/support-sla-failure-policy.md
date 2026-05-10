# Support SLA and Failure Policy

AANA support guardrails must have a conservative route when the runtime cannot decide. The source of truth is `examples/support_sla_failure_policy.json`.

Required fallback behavior:

- Evidence unavailable -> `retrieve` or `ask`
- CRM unavailable -> `defer`
- Verification missing -> `ask`
- Privacy risk -> `refuse`
- Policy ambiguity -> `defer`
- Bridge unavailable for irreversible support actions -> fail closed with `refuse` or `defer`
- Bridge unavailable for draft-only support responses -> fail advisory in advisory mode, otherwise `ask` or `defer` depending on enforcement mode

Irreversible support actions include email send, refund execution, account closure, deletion, chargeback, cancellation, and data export. These actions must not proceed only because the bridge or runtime is unavailable.

Draft support replies may continue only in shadow or advisory mode when a human review path exists. In enforced mode, draft checks should hold with `ask` or `defer` until AANA can evaluate the Workflow Contract or Agent Event.

## SLA Targets

The repo-local defaults are intentionally conservative:

- support drafts target 1500 ms and time out to `ask`
- CRM-backed drafts target 2000 ms and time out to `defer`
- support email sends target 1500 ms and time out to `refuse`

Production deployments may tighten these targets, but they must not weaken the failure routes without domain owner signoff.

## Audit

Failure-policy audit records should preserve adapter ID, workflow ID, gate decision, recommended action, fallback condition ID, audit code, AIx summary, violation codes, evidence source IDs, fingerprints, execution mode, and human review route.

Audit must not store raw customer messages, raw candidate responses, full CRM records, payment data, internal notes, attachment bodies, secrets, or tokens.

## Validation

```powershell
python scripts/validation/validate_support_sla_failure_policy.py
```

The release gate runs this validator as a production-profile check.
