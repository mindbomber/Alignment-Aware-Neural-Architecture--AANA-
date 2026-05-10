# AANA Enterprise Family

The Enterprise family packages AANA around operational risk before customer, code, deployment, data, access, billing, and incident actions.

Use the Enterprise pack when an agent or workflow may:

- reply to customers or update support tickets;
- send email to internal or external recipients;
- export data or discuss data access;
- approve IAM or permission changes;
- review code, pull requests, releases, or deployments;
- publish incident communications;
- answer billing or account-adjacent questions.

## Core Pack

The Enterprise core pack is fixed to these production-candidate adapters:

- `crm_support_reply`
- `email_send_guardrail`
- `ticket_update_checker`
- `data_export_guardrail`
- `access_permission_change`
- `code_change_review`
- `deployment_readiness`
- `incident_response_update`

The local family page is available at:

```text
http://127.0.0.1:8788/enterprise
```

Each adapter card shows risk tier, required evidence, supported surfaces, example inputs and outputs, AIx tuning, and a link into the web playground.

## Evidence Connectors

Enterprise certification expects connector contracts for:

- CRM: `crm_support`
- Ticketing: `ticketing`
- Email: `email_send`
- IAM: `iam`
- CI/GitHub: `ci`
- Deployment: `deployment`
- Billing: `billing`
- Data warehouse/export: `data_export`

These connectors are read-only evidence contracts. They do not send mail, grant access, deploy, export data, post incident updates, or perform irreversible actions. Production implementations must return fresh, source-scoped, redacted evidence summaries with source IDs and trust metadata.

## Agent Skills

The Enterprise family includes instruction-only skills for:

- support draft review;
- release/deployment gating;
- code and pull request review;
- access-change approval;
- incident communications.

Skills must respect AANA runtime results. They may only proceed when `gate_decision` is `pass`, `recommended_action` is `accept`, and `aix.hard_blockers` is empty. Otherwise they must revise, ask, defer, refuse, or route to human review.

## Pilot Surface

Enterprise pilots are packaged through:

- Docker bridge;
- GitHub Action;
- web playground;
- shadow mode;
- metrics dashboard;
- redacted audit export.

Run the starter kit:

```powershell
python scripts/pilots/run_starter_pilot_kit.py --kit enterprise
```

Review the outputs:

```text
docs/evidence/peer_review/starter_pilot_kits/enterprise/audit.jsonl
docs/evidence/peer_review/starter_pilot_kits/enterprise/metrics.json
docs/evidence/peer_review/starter_pilot_kits/enterprise/report.md
```

## Enterprise Certification

Run:

```powershell
python scripts/aana_cli.py enterprise-certify --json
```

The certification command checks:

- Enterprise core adapters and starter workflows;
- required evidence connectors and mock connector normalization;
- Enterprise agent skill files and runtime-result handling;
- packaged pilot surfaces;
- redacted audit export;
- production certification policy controls;
- risk-tier AIx threshold floors;
- declared shadow-mode pass window.

Passing Enterprise certification means the repo-local Enterprise family is packaged for controlled pilots. It does not mean a real organization is production-certified. Production enforcement still requires live connector implementations, live shadow-mode traffic, domain-owner signoff, immutable audit retention, and human-review queues.
