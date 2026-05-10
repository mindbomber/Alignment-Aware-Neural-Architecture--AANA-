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
- edge and runtime rate limiting

Repo-local tests can prove the local runtime behavior for redaction, audit shape, bridge config, token redaction, fixture-based CRM note blocking, fixture-based attachment blocking, and bridge rate limiting. They cannot prove live connector permissions, immutable audit retention, edge rate limits, identity-provider behavior, or production owner approval.

## Completed Internal-Pilot Review

The internal-pilot security review now has executable sections for:

- Bridge auth/token handling: POST routes require bearer or `X-AANA-Token` credentials when configured, token files are reread for rotation, `/config` reports only token source metadata, and bridge logs redact token-like values.
- Connector permissions: support connector manifests declare least-privilege read-only scopes, denied write/delete/send/raw-export/admin scopes, reviewed data classes, reviewer, and review date. External production still needs environment-owner evidence for the selected CRM, order, ticket, email, billing, and DLP systems.
- PII and attachment metadata: audit records remain metadata-only and attachment bodies are not stored. Attachment checks may use `attachment_id`, filename/content fingerprints, content type, size, source id, and DLP classification.
- Rate limiting: the runtime enforces `--rate-limit-per-minute`; the internal-pilot Kubernetes config declares matching edge limit, burst, and per-authenticated-client scope. Production deployments must enforce both layers.
- Secrets scanning: `scripts/validation/validate_secrets_scan.py` scans deployment, runtime, docs, examples, scripts, and tests with `examples/secrets_scan_allowlist.json`. The allowlist is limited to synthetic redaction/auth test literals and documentation examples.

Validate the full security review with:

```powershell
python scripts/validation/validate_security_privacy_review.py
python scripts/validation/validate_secrets_scan.py
python scripts/validation/validate_security_hardening.py
```

The broader security hardening gate also validates CI secret scanning, dependency audit wiring, public-demo safe defaults, and the malicious-agent threat model in [aana-security-threat-model.md](aana-security-threat-model.md).

## Audit Retention

The local audit format is JSONL and intentionally metadata-only. JSONL is a test/export handoff format, not the production audit store.

For the internal pilot, the approved audit-retention policy is `examples/audit_retention_policy_internal_pilot.json`. It requires an append-only immutable sink, at least 365 days of retention, lifecycle deletion only when no legal hold is active, least-privilege reader/admin roles, create-only runtime writer permissions, daily chained SHA-256 integrity manifests, and raw artifact storage set to `none`.

Production support audit records must remain decision metadata only. They may store adapter/workflow IDs, gate/action decisions, violation codes, AIx summaries, hard blockers, evidence source IDs, fingerprints, execution mode, latency, connector/freshness failures, and human-review routes. They must not store raw customer messages, raw candidate responses, full CRM records, payment or billing data, internal notes, attachment bodies, secrets, tokens, raw evidence, or safe-response text.

Validate the policy and redaction proof with:

```powershell
python scripts/validation/validate_audit_retention_policy.py
```

This validator generates support Workflow Contract and Agent Event audit records from canonical fixtures, validates the audit schema, and scans the serialized records for raw support request, candidate, evidence, CRM, payment, internal-note, and attachment text.

## Secrets Scanning

The repository contains synthetic secret-like strings in tests and fixtures to verify redaction behavior. The repo-local gate uses `examples/secrets_scan_allowlist.json` and fails on unapproved credential-looking literals in source, deployment manifests, connector configuration, docs, tests, and examples. Production secret scanning must reuse this allowlist, add environment-specific secret-manager evidence, and fail on unapproved findings in deployment manifests, connector configuration, logs, and audit artifacts.

CI runs both the repo-local scanner and a gitleaks scan with `.gitleaks.toml`. The allowlist is restricted to synthetic fixtures and generated evidence snapshots.

## Dependency Audit

CI installs the API extra and runs `pip-audit`. A dependency vulnerability should block promotion until the dependency is patched, pinned to a safe version, removed, or explicitly risk-accepted outside this repo-local gate.

## Public Demo Safety

Hosted demos must stay synthetic-only. Public browser demos must not store secrets or execute real sends, deletes, purchases, deploys, exports, or connector writes. The security hardening gate checks `docs/demo/scenarios.json` and `docs/tool-call-demo/app.js` for those safe defaults.

## Rate Limiting

The HTTP bridge exposes `--rate-limit-per-minute` as a per-client runtime control. The internal-pilot deployment manifest also declares edge limit and burst settings. Production deployments must enforce edge limits, authenticated caller quotas, burst limits, and alerting for repeated `429` responses.
