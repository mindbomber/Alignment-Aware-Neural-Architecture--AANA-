# AANA Data Export Guardrail Skill

Use this skill before an OpenClaw-style agent exports, downloads, shares, syncs, copies, uploads, emails, or publishes files, records, datasets, reports, logs, messages, or account data.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, or export data on its own.

## Core Principle

Data export should be narrow, authorized, necessary, privacy-safe, and reversible where possible. Broad or sensitive exports require explicit approval and review.

## Required Checks

- exact dataset, files, records, fields, date range, and recipient/destination
- reason the export is necessary
- private data, secrets, personal data, customer data, logs, account records, and regulated information
- authorization, ownership, and sharing permission
- format, redaction, retention, and deletion expectations
- whether a smaller summary, aggregate, or filtered export is enough

## Decision Rule

- If export is narrow, necessary, authorized, and privacy-safe, proceed.
- If scope, recipient, fields, or purpose are unclear, ask.
- If sensitive data is included, redact, narrow, or route to review.
- If broad, bulk, cross-account, or external export is requested, require approval.
- If export is unauthorized, excessive, or privacy-violating, block.

## Output Pattern

```text
AANA data export gate:
- Export: files / records / dataset / logs / report / messages / account_data
- Scope: narrow / broad / bulk / cross_account / unknown
- Destination: local / user / external / public / unknown
- Privacy: clear / needs_redaction / sensitive / regulated
- Approval: approved / required / unclear / denied
- Decision: proceed / narrow / ask / redact / request_approval / route_to_review / block
```
