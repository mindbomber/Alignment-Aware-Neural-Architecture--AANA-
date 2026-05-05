# Audit And Observability Hardening

Milestone 9 makes AANA audit output reviewable without exposing raw checked text. The repo-local audit path now has four handoff artifacts:

- redacted audit JSONL,
- flat audit metrics JSON,
- AIx drift report JSON,
- Markdown reviewer report.

Run the local audit workflow:

```powershell
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py audit-validate --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/aana-metrics.json
python scripts/aana_cli.py audit-drift --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/aana-aix-drift.json
python scripts/aana_cli.py audit-manifest --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/manifests/aana-audit-integrity.json
python scripts/aana_cli.py audit-reviewer-report --audit-log eval_outputs/audit/aana-audit.jsonl --metrics eval_outputs/audit/aana-metrics.json --drift-report eval_outputs/audit/aana-aix-drift.json --manifest eval_outputs/audit/manifests/aana-audit-integrity.json --output eval_outputs/audit/aana-reviewer-report.md
```

## Validation

`audit-validate` checks that each JSONL record:

- declares `audit_record_version`,
- uses a known `record_type`,
- has `created_at`, gate/action fields, AIx summary, and input fingerprints,
- does not include raw prompt, request, candidate, evidence, constraints, safe response, or output fields.

The audit record may preserve fingerprints, text lengths, adapter IDs, gate decisions, recommended actions, violation codes, AIx scores, AIx decisions, and hard blockers.

## Metrics

`audit-metrics` converts redacted records into stable dashboard keys:

- gate/action counts,
- violation counts,
- adapter counts,
- record-type counts,
- AIx average/min/max score,
- AIx decision counts,
- AIx hard-blocker counts.

Latency remains unavailable from audit JSONL unless runtime telemetry adds it.

## AIx Drift

`audit-drift` reads the same redacted log and checks AIx release-review thresholds:

- minimum average AIx score,
- minimum per-record AIx score,
- maximum hard blockers,
- allowed AIx decisions.

The drift report can optionally compare current metrics to a previous metrics export with `--baseline-metrics`.

## Reviewer Report

`audit-reviewer-report` writes a Markdown summary intended for release reviewers. It includes schema/redaction status, gate/action counts, AIx distribution, top violations, drift issues, and optional integrity-manifest hashes.

This report is a local review artifact. Production deployments still need immutable audit storage, retention policy, dashboard ingestion, alert routing, and accountable human review.
