# AANA Packaging Release Checklist

AANA has six separate publication surfaces:

| Surface | Boundary |
| --- | --- |
| Python package | Runtime SDK, CLI, middleware helpers, audit utilities, and optional API/eval entrypoints. |
| TypeScript SDK | Browser/Node helper package and HTTP client. |
| FastAPI service | Optional API surface installed through the Python `api` extra. |
| Docs and cards | GitHub Pages docs plus Hugging Face model/dataset card templates. |
| Benchmark/eval tooling | Calibration, HF dataset, benchmark, and evidence-pack tooling. This is not the runtime core claim. |
| Examples | Synthetic-only quickstarts, integration demos, API fixtures, and the Hugging Face Space demo source. |

Each surface must keep a clear boundary:

- Python package: importable `aana` runtime and CLI entrypoints; benchmark dependencies stay optional.
- TypeScript SDK: npm package under `sdk/typescript`; no Python eval artifacts.
- FastAPI service: HTTP policy service through the `api` extra; not a benchmark runner.
- Docs/cards: public docs, cards, reports, and claim boundaries; no executable demo ownership.
- Benchmark/eval tooling: offline calibration and reporting; not required for core runtime use.
- Examples: synthetic demos only; no real credentials, sends, deletes, purchases, deploys, exports, or benchmark answer keys.

## Current Python Name

The current public Python distribution is `aana-eval-pipeline`, while the import package is `aana`.

Do not rename the public distribution in a drive-by release. A cleaner future name may make sense, but only with migration care:

- keep `import aana` stable,
- publish migration notes before changing distribution names,
- keep the old distribution available for a migration window,
- keep CLI aliases or compatibility shims for existing users.

## Required Gate

Run this before PyPI, npm, Hugging Face, or service publication:

```powershell
python scripts/validate_packaging_hardening.py --require-existing-artifacts
python scripts/validate_aana_standard_publication.py --require-existing-artifacts
python scripts/validate_security_hardening.py
```

The manifest gate is [examples/packaging_release_manifest.json](../examples/packaging_release_manifest.json). It must declare every surface boundary plus the release checklist for PyPI, npm, and Hugging Face.

## PyPI

- Confirm `python_package`, `fastapi_service`, `benchmark_eval_tooling`, `docs_and_cards`, and `examples` boundaries are still valid.
- Confirm distribution name, owner, version, and migration notes.
- Run `python -m build`.
- Run `twine check dist/*`.
- Confirm default install remains useful without benchmark-only dependencies.
- Confirm FastAPI dependencies remain in the `api` extra.
- Confirm eval dependencies remain in the `eval` extra.

## npm

- Confirm `typescript_sdk`, `docs_and_cards`, and `examples` boundaries are still valid.
- Confirm package owner and access for `@aana/integration-sdk`.
- Run `cd sdk/typescript && npm install`.
- Run `cd sdk/typescript && npm run build`.
- Run `cd sdk/typescript && npm pack --dry-run`.

## Hugging Face

- Confirm `docs_and_cards`, `benchmark_eval_tooling`, and `examples` boundaries are still valid.
- Validate HF dataset registry, calibration plan, and proof report.
- Review the model and dataset cards by hand.
- Confirm public claims say AANA is an audit/control/verification/correction layer.
- Confirm benchmark probe or diagnostic results are not used as public claims.

## Service

- Install with the `api` extra.
- Run the FastAPI tests.
- Confirm token auth, rate limits, request-size limits, and redacted audit JSONL logging.
- Confirm public demos remain synthetic-only and cannot send, delete, purchase, deploy, or export.
