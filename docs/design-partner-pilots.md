# Design Partner Pilots

The design-partner pilot milestone turns the local AANA runtime into a repeatable field-evaluation package. The goal is to run 3 to 5 controlled pilots, collect real failure modes, friction points, and adoption blockers, and keep all runtime artifacts redacted.

The checked-in controlled pilots are:

- Enterprise support operations: CRM replies, ticket updates, data exports, IAM changes.
- Developer tooling and release: code review, deployment readiness, API contract changes, database migrations.
- Personal productivity actions: email send, calendar scheduling, file operations, booking/purchase.
- Civic and government-style workflows: procurement risk, grant review, claim triage, policy memo grounding.

Run all pilots:

```powershell
python scripts/pilots/run_design_partner_pilots.py --pilot all
```

Run one pilot:

```powershell
python scripts/pilots/run_design_partner_pilots.py --pilot developer_tooling_release
```

Attach field feedback after a partner session:

```powershell
python scripts/pilots/run_design_partner_pilots.py --pilot enterprise_support_ops --feedback-dir path/to/redacted-feedback
```

The feedback directory should contain files named `<pilot_id>.json`, using the generated `feedback_template.json` shape from each pilot output folder.

## Output

Each pilot writes:

- `audit.jsonl`: redacted AANA audit records.
- `metrics.json`: audit-to-metrics export.
- `dashboard.json`: dashboard-ready metrics payload.
- `aix_drift.json`: AIx drift review.
- `audit_integrity_manifest.json`: SHA-256 audit integrity manifest.
- `reviewer_report.md`: audit reviewer handoff.
- `workflow_batch.json`: materialized Workflow Contract batch.
- `feedback_template.json`: structured partner feedback form.
- `field_notes_template.md`: interview notes template.
- `report.json` and `report.md`: pilot summary and artifact index.

## Data Rules

Use synthetic data or partner-redacted data only. Do not place raw customer, patient, legal, financial, government case, credential, payment, or private file content in repo artifacts. If a partner wants to test real data, run AANA in their controlled environment and export only redacted audit and feedback summaries.

## What To Collect

Failure modes:

- missed risks
- overblocking
- weak evidence mapping
- unsafe safe responses
- wrong adapter choice
- human-review routing gaps

Friction points:

- unclear setup
- unclear output
- hard-to-supply evidence
- poor fit with existing tools
- latency or workflow interruption
- confusing docs

Adoption blockers:

- security review
- data access
- procurement
- audit retention
- human-review ownership
- unacceptable false positives or false negatives
- unclear return on workflow value

## Exit Criteria

This milestone is repo-ready when the controlled pilots run and generate redacted artifacts. It is field-complete only after 3 to 5 actual design-partner sessions attach feedback files and the combined report shows captured failure modes, friction points, and adoption blockers.
