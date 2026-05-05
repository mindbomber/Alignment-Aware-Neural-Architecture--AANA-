# Hosted Demo Option

Canonical entry point: [Try Demo](try-demo/index.md).

The hosted demo is a static GitHub Pages surface for trying AANA without cloning the repository or running the local bridge.

The repository is demo-ready and pilot-ready for controlled evaluation, but it is not production-certified by itself. The hosted demo is also not a certification surface. Production readiness requires live evidence connectors, domain owner signoff, audit retention, observability, and human review paths.

Open:

```text
https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/demo/
```

Local preview:

```powershell
python -m http.server 8000 --directory docs
```

Then open:

```text
http://127.0.0.1:8000/demo/
```

## Safety Boundary

The hosted demo is intentionally static:

- synthetic examples only
- no user secrets
- no token input
- no authenticated API calls
- no real sends
- no file deletes or moves
- no deploys or migrations
- no payments, bookings, or purchases
- no private data exports

The browser loads only `docs/demo/scenarios.json` and reveals precomputed AANA outcomes. It does not run the Python verifier stack and does not submit user input to any service.

## What It Shows

The first hosted demo pack includes:

- enterprise CRM support reply
- developer deployment readiness
- personal email send guardrail
- civic grant/application review
- research answer grounding

Each scenario shows:

- request
- risky candidate answer or action
- synthetic evidence
- candidate gate
- recommended action
- final AIx and candidate AIx
- verifier violations
- safe response
- decision metadata

## When To Use The Local Runtime Instead

Use the local CLI, Python API, HTTP bridge, or Docker runtime when you need:

- live adapter execution
- custom candidate text
- real workflow batches with redacted evidence
- audit JSONL output
- metrics exports
- release checks
- shadow-mode evaluation

The hosted demo is for first-contact evaluation only. It explains the AANA behavior without granting AANA access to a user workspace or production system.
