# Pilot Surface Certification

Pilot certification is the repo-local readiness score for the public ways a pilot can call AANA. It is intended to answer a simple question: can a local user evaluate AANA through the CLI, Python API, HTTP bridge, adapters, evidence contracts, audit logs, metrics, and docs without needing private production data?

Run it with:

```powershell
python scripts/aana_cli.py pilot-certify
python scripts/aana_cli.py pilot-certify --json
python scripts/dev.py pilot-certify
```

The command fails if a required pilot surface is missing a gate or the weighted readiness score falls below the public pilot threshold.

The human-readable output starts with a score:

```text
AANA pilot certification: pass - 100.0/100 (pilot_ready, 11 surface(s), 37 gate(s)).
```

The JSON output includes the same public contract under `summary.score_percent`, `summary.readiness_level`, `summary.surfaces`, `summary.gates`, `summary.failures`, and `summary.warnings`.

## Score Meaning

- `pilot_ready`: no failed surfaces and score is at least `90.0`.
- `pilot_ready_with_warnings`: no failed surfaces, score is at least `90.0`, and one or more gates are warnings.
- `not_pilot_ready`: at least one required surface failed or the score is below `90.0`.

Gate status maps to score as follows:

- `pass`: full gate weight.
- `warn`: half gate weight.
- `fail`: zero gate weight and the surface is not ready.

## Surfaces

The matrix covers:

- CLI
- Python API
- HTTP bridge
- adapters
- Agent Event Contract
- Workflow Contract
- skills/plugins
- evidence
- audit/metrics
- docs
- contract freeze

## Gate Meaning

`pass` means the repo-local pilot requirement is present and usable. `fail` means the pilot should not proceed through that surface until the missing contract, fixture, doc, or readiness check is fixed.

The certification command does not replace real deployment approval. It checks repository readiness, not external TLS, secret storage, immutable audit infrastructure, real evidence-source authorization, production dashboards, domain-owner signoff, or live human-review queues.

For the stricter line between demo, pilot, and enforced production use, run `python scripts/aana_cli.py production-certify` with a production certification policy, deployment manifest, governance policy, evidence registry, observability policy, redacted shadow-mode audit log, and external production evidence manifest. See `docs/production-certification.md`.

## Expected Matrix

Current repo-local pilot readiness requires:

- CLI command matrix contains core agent, workflow, evidence, audit, contract, release, and certification commands.
- Python API exposes typed runtime helpers, audit review helpers, and evidence mock connector helpers.
- HTTP bridge exposes `/ready`, `/health`, OpenAPI, agent checks, workflow checks, batch checks, playground routes, demo routes, and dashboard metrics.
- Adapter gallery validates, adapter files exist, example inputs and expected outcomes are present, and adapters declare explicit AIx tuning.
- Agent Event Contract has schemas, examples, and valid/invalid fixtures.
- Workflow Contract has structured examples, batch examples, source-registry validation, and adapter-family examples.
- Skills/plugins have conformance docs, install/use docs, high-risk examples, and runtime connector metadata.
- Evidence has registry coverage, mock connector fixtures, and evidence integration contract docs.
- Audit/metrics has schema validation, redaction checks, metrics export validation, dashboard payload generation, and AIx drift report generation.
- Docs cover setup, hosted demo, integration recipes, pilot kits, design-partner pilots, shadow mode, metrics, pilot certification, production certification, and user-facing surfaces.
- Contract freeze passes with compatibility fixtures.
