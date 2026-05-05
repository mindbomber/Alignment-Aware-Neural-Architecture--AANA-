# AANA Personal Productivity Family

The Personal Productivity family packages AANA for local assistants that handle
everyday irreversible actions: send, schedule, delete, move, write, buy,
publish, cite, and share.

## Core Pack

- Email send guardrail.
- Calendar scheduling.
- File operation guardrail.
- Purchase/booking guardrail.
- Research answer grounding.
- Publication check.
- Meeting summary checker.

## Evidence Connectors

- Local files through `workspace_files`.
- Email draft metadata through `email_send`.
- Calendar free/busy through `calendar`.
- Browser/cart quote through `browser_cart_quote`.
- Citation/source registry through `citation_source_registry`.
- Local approval state through `local_approval`.

Connector contracts are read-only evidence boundaries. They may retrieve and
normalize redacted evidence, but they must not send email, update calendars,
write or delete files, submit payment, publish content, or share summaries.

## Agent Skills

- Before I send: `examples/openclaw/aana-email-send-guardrail-skill/`.
- Before I delete/move/write: `examples/openclaw/aana-file-operation-guardrail-skill/`.
- Before I book/buy: `examples/openclaw/aana-purchase-booking-guardrail-skill/`.
- Before I answer with citations: `examples/openclaw/aana-research-grounding-skill/`.
- Before I schedule: `examples/openclaw/aana-calendar-scheduling-guardrail-skill/`.

Each skill must honor the AANA runtime result. If `recommended_action` is
`revise`, `ask`, `retrieve`, `defer`, or `refuse`, the agent should not claim
that the irreversible action was completed.

## Demo App

The local desktop/browser demo is synthetic first and local-only by default:

```powershell
python scripts/run_local_demos.py
```

It exposes seven scenarios and shows gate decision, recommended action,
candidate AIx, final AIx, verifier findings, safe response, and redacted audit
preview.

## Certification

Run:

```powershell
python scripts/run_starter_pilot_kit.py --kit personal_productivity
python scripts/aana_cli.py personal-certify --json
```

The certification checks that the personal core pack, evidence connector
contracts, skills, local browser demo, redacted audit export, metrics JSON, and
Markdown report are present and consistent.
