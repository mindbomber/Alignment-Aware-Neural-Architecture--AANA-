# AANA Starter Pilot Kits

Starter pilot kits are self-contained, synthetic workflow packs for showing AANA to pilot users without private data. They sit between the browser playground and a real shadow-mode integration: the data is fake, but the Workflow Contract, adapter checks, redacted audit records, and metrics export are real.

The same three kits are surfaced as product-family landing pages:

- [`docs/enterprise/index.html`](enterprise/index.html) for operational enterprise workflows.
- [`docs/personal-productivity/index.html`](personal-productivity/index.html) for local irreversible personal actions.
- [`docs/government-civic/index.html`](government-civic/index.html) for public-service, procurement, grant, records, privacy, eligibility, and policy workflows.

When served by the HTTP bridge, those pages are available at `/enterprise`,
`/personal-productivity`, and `/government-civic`, with browser links into the
playground and the matching one-command pilot kit.

## Included Kits

- `enterprise` - CRM support reply, email send, ticket update, data export, access permission, code review, deployment readiness, and incident response.
- `personal_productivity` - Email guardrail, calendar scheduling, file operation guardrail, booking/purchase, and research grounding.
- `government_civic` - Procurement/vendor risk, grant/application review, public-records privacy redaction, policy memo grounding, benefits triage, legal safety routing, and publication check.

Each kit includes:

- `manifest.json` - pilot audience, surfaces, and exit criteria.
- `adapter_config.json` - adapter pack, risk posture, evidence mode, and expected operating surface.
- `synthetic_data.json` - redacted synthetic evidence records with source IDs and timestamps.
- `workflows.json` - workflow examples that reference the synthetic evidence records.
- `expected_outcomes.json` - expected gate behavior and minimum metrics.

## Run

Run every starter kit:

```powershell
python scripts/pilots/run_starter_pilot_kit.py --kit all
```

Run one pack:

```powershell
python scripts/pilots/run_starter_pilot_kit.py --kit enterprise
python scripts/pilots/run_starter_pilot_kit.py --kit personal_productivity
python scripts/pilots/run_starter_pilot_kit.py --kit government_civic
```

The development shortcut is:

```powershell
python scripts/dev.py starter-kits
```

## Outputs

Each run writes one output directory per kit under `eval_outputs/starter_pilot_kits/<kit-id>/`:

- `materialized_workflows.json` - the exact Workflow Contract batch request.
- `audit.jsonl` - redacted audit records with fingerprints and decision metadata.
- `metrics.json` - flat dashboard metrics from the audit log.
- `report.json` - machine-readable scenario report.
- `report.md` - human-readable pilot report.

The audit records do not store raw prompt, candidate, evidence, output, or safe-response text.

## Pilot Use

A pilot user can run a realistic scenario by choosing a kit, reviewing the synthetic evidence, running the command, and reading `report.md`. The expected pattern for these starter workflows is that AANA blocks the unsafe candidate, recommends a safer revision, records the violation classes, and produces audit/metrics artifacts that a reviewer can inspect.

Before using real data, replace the synthetic evidence records with connector-backed structured evidence objects and run the same workflow in local shadow mode.
