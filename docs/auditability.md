# AANA Auditability

AANA decisions must emit an audit-safe log event. The event is metadata-only and
is designed for operational review, metrics, dashboards, incident analysis, and
human-review queues without storing raw prompts, candidates, evidence text,
tool arguments, safe responses, secrets, or private records.

## Required Decision Event

Every checked answer or action should expose `audit_safe_log_event` through the
result's `architecture_decision` or the persisted audit JSONL record.

Required fields:

- `route`: `accept`, `revise`, `ask`, `defer`, or `refuse`
- `gate_decision`
- `candidate_gate`
- `aix_score`
- `aix_decision`
- `hard_blockers`
- `missing_evidence`
- `evidence_refs.used`
- `evidence_refs.missing`
- `authorization_state`
- `latency_ms`
- `raw_payload_logged: false`

For tool calls, the event may include `tool_name`, `tool_category`,
`risk_domain`, and `proposed_argument_keys`. It must not include proposed
argument values.

## Summary Tooling

Use the CLI to validate, summarize, export metrics, and produce reviewer
artifacts:

```powershell
python scripts/aana_cli.py audit-validate --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py audit-summary --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/aana-metrics.json
python scripts/aana_cli.py audit-reviewer-report --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/aana-reviewer-report.md
```

`audit-summary` includes decision cases:

- `allowed`: direct accepts
- `blocked`: revise, ask, refuse, or failed-gate interventions
- `deferred`: deferred routes
- `false_positive`: records labeled by human review as false positives

False positives are not inferred automatically. Add a human review marker such
as `{"review": {"outcome": "false_positive"}}` to a redacted audit record or
external review artifact before counting it as a false positive.

## Retention Policy

Local JSONL audit logs are development and pilot artifacts, not the production
audit store. Production deployments should write audit records to an append-only
internal sink with:

- least-privilege writer and reader roles
- immutable or tamper-evident storage
- daily or release-bound SHA-256 integrity manifests
- legal-hold support
- lifecycle deletion only after the approved retention window
- no raw artifact retention unless separately approved

The internal pilot policy lives at
`examples/audit_retention_policy_internal_pilot.json` and can be validated with:

```powershell
python scripts/validate_audit_retention_policy.py
```

## Redaction Policy

Audit records may store:

- adapter or tool identifiers
- workflow or event IDs
- route, gate decision, candidate gate, and execution mode
- AIx score, AIx decision, hard blockers, and violation codes
- evidence source IDs and missing evidence markers
- authorization state and human-review route
- latency and connector/freshness failures
- SHA-256 fingerprints and lengths for correlating with approved secure stores

Audit records must not store:

- raw user messages, prompts, candidates, draft responses, or safe responses
- raw evidence text, full CRM/order/account records, attachments, or files
- payment data, private identifiers, secrets, tokens, or internal notes
- tool argument values

Run `audit-validate` and `audit_redaction_report` before sharing audit
artifacts outside the trusted environment.
