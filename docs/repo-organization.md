# Repository Organization

AANA keeps the public runtime small and separates product surfaces from research and evaluation tooling.

## Public Runtime

The default installed Python surface is:

- `aana` - CLI for local checks, audit summaries, bundle certification, and runtime validation.
- `aana-fastapi` - FastAPI policy service.
- `aana-validate-platform` - full platform harmony gate.

The import package remains `aana`. The current distribution name, `aana-eval-pipeline`, is a transitional legacy name until a planned migration to the cleaner `aana` package name.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `aana/` | Runtime SDK, CLI entrypoints, FastAPI wrapper, middleware, registry, adapters, and bundles. |
| `eval_pipeline/` | Shared runtime internals plus research/eval support modules. |
| `sdk/typescript/` | TypeScript SDK and HTTP client helpers. |
| `examples/` | Synthetic examples, API events, integration demos, and public demo fixtures. |
| `docs/` | Product docs, architecture docs, evidence reports, and publication guidance. |
| `scripts/` | Repo-local validation, benchmark, HF, publication, pilot, demo, and development helpers. |
| `tests/` | Unit tests, contract tests, integration smoke tests, and platform validation tests. |
| `docs/evidence/peer_review/` | Reviewed evidence artifacts that are intentionally tracked. |
| `eval_outputs/` | Generated local outputs, ignored by git. |
| `diagnostics/probes/` | Explicitly quarantined probe/diagnostic code that cannot support public claims. |

## Script Layout

Top-level `scripts/` is intentionally limited to compatibility and development entrypoints:

- `aana_cli.py`
- `aana_fastapi.py`
- `aana_server.py`
- `dev.py`
- `validate_aana_platform.py`

Everything else belongs in grouped folders:

- `scripts/adapters/`
- `scripts/benchmarks/`
- `scripts/demos/`
- `scripts/evals/`
- `scripts/hf/`
- `scripts/integrations/`
- `scripts/pilots/`
- `scripts/publication/`
- `scripts/validation/`

## Canonical Names

The canonical government/civic bundle ID is `government_civic`. The older `civic_government` spelling is an alias for backward compatibility only and should not appear in new public paths or examples.

## Evidence Policy

Generated outputs stay under `eval_outputs/` and are not tracked. Intentional peer-review artifacts move to `docs/evidence/peer_review/` and must be listed in `docs/evidence/artifact_manifest.json` with result label, source split, public-claim eligibility, and reproduction command.

## Validation

Run:

```powershell
python scripts/validation/validate_repo_organization.py
python scripts/validate_aana_platform.py --timeout 240
```

The repo organization validator fails on stale public command paths, tracked layout drift, missing organization docs, and alias leakage outside backward-compatible surfaces.
