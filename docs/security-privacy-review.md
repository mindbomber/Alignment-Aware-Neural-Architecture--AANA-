# AANA Support Security And Privacy Review

AANA can be demo-ready, pilot-ready, or production-candidate as a runtime guardrail layer for support workflows. This repository is not production-certified by local tests alone. A production deployment still needs live evidence connector review, domain owner signoff, audit retention approval, observability, staffed human review paths, security review, deployment manifest, incident response plan, and measured pilot results.

The executable source of truth for this review is `examples/security_privacy_review_support.json`. The release gate validates that every deployment-blocking control remains declared and tied to either repo-local tests or external deployment evidence.

## Support Data Flow

1. The agent submits a Workflow Contract or Agent Event with an adapter id, request, candidate output/action, allowed actions, and evidence metadata.
2. AANA checks the candidate with support verifiers for invented account/order facts, unsupported refund promises, private payment/account data, internal CRM note leakage, verification bypass, recipient risk, unsafe attachments, and irreversible send risk.
3. The correction policy returns one of `accept`, `revise`, `retrieve`, `ask`, `defer`, or `refuse`.
4. The runtime emits metadata-only audit records: adapter id, workflow or event id, gate decision, recommended action, violation codes, AIx details, hard blockers, evidence source ids, fingerprints, execution mode, and human review route.

Raw customer messages, raw candidates, full CRM records, payment data, internal notes, attachments, secrets, and tokens must not be stored in audit records or bridge logs.

## Deployment Controls

The review tracks these controls:

- support data-flow threat model
- raw prompt/candidate log leakage
- token/auth handling
- evidence connector permission review
- PII redaction review
- attachment metadata handling
- internal CRM note exposure tests
- audit retention policy
- secrets scanning
- rate limiting plan

Repo-local tests can prove the local runtime behavior for redaction, audit shape, bridge config, token redaction, fixture-based CRM note blocking, fixture-based attachment blocking, and bridge rate limiting. They cannot prove live connector permissions, immutable audit retention, edge rate limits, identity-provider behavior, or production owner approval.

## Audit Retention

The local audit format is JSONL and intentionally metadata-only. A production deployment must define retention period, storage location, immutable write controls, access policy, deletion/legal-hold behavior, and reviewer access before support traffic is routed through AANA.

## Secrets Scanning

The repository contains synthetic secret-like strings in tests and fixtures to verify redaction behavior. Production secret scanning must use an allowlist for those fixture paths and must fail on unapproved secrets in source, deployment manifests, connector configuration, logs, and audit artifacts.

## Rate Limiting

The HTTP bridge exposes `--rate-limit-per-minute` as a per-client local control. Production deployments should also enforce edge limits, authenticated caller quotas, burst limits, and alerting for repeated `429` responses.
