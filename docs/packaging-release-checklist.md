# AANA Packaging Release Checklist

AANA has six separate publication surfaces:

| Surface | Boundary |
| --- | --- |
| Python package | Runtime SDK, runtime CLI, middleware helpers, audit utilities, and optional API service entrypoints. |
| TypeScript SDK | Browser/Node helper package and HTTP client. |
| FastAPI service | Optional API surface installed through the Python `api` extra. |
| Docs and cards | GitHub Pages docs plus Hugging Face model/dataset card templates. |
| Benchmark/eval tooling | Calibration, HF dataset, benchmark, and evidence-pack tooling. This is not the runtime core claim. |
| Examples | Synthetic-only quickstarts, integration demos, API fixtures, and the Hugging Face Space demo source. |

Each surface must keep a clear boundary:

- Python package: importable `aana` runtime and runtime CLI/API entrypoints; repo-local benchmark and HF experiment commands are not installed as public console scripts.
- TypeScript SDK: npm package under `sdk/typescript`; no Python eval artifacts.
- FastAPI service: HTTP policy service through the `api` extra; not a benchmark runner.
- Docs/cards: public docs, cards, reports, and claim boundaries; no executable demo ownership.
- Benchmark/eval tooling: offline calibration and reporting; not required for core runtime use.
- Examples: synthetic demos only; no real credentials, sends, deletes, purchases, deploys, exports, or benchmark answer keys.

## Python Distribution Name

The current public Python distribution is `aana-eval-pipeline`, while the import package and public CLI are `aana`.

Treat `aana-eval-pipeline` as a transitional legacy distribution name from the earlier research/eval phase, not as the long-term platform brand. The intended future distribution target is `aana`.

Do not rename the public distribution in a drive-by release. The rename should happen only with migration care:

- keep `import aana` stable,
- keep `aana`, `aana-fastapi`, and `aana-validate-platform` CLI behavior stable,
- publish migration notes before changing distribution names,
- keep the old distribution available for a migration window,
- keep CLI aliases or compatibility shims for existing users,
- avoid publishing new platform docs that imply `aana-eval-pipeline` is the permanent product name.

## Required Gate

Run this before PyPI, npm, Hugging Face, or service publication:

```powershell
python scripts/validation/validate_packaging_hardening.py --require-existing-artifacts
python scripts/validation/validate_aana_standard_publication.py --require-existing-artifacts
python scripts/validation/validate_security_hardening.py
```

The manifest gate is [examples/packaging_release_manifest.json](../examples/packaging_release_manifest.json). It must declare every surface boundary plus the release checklist for PyPI, npm, and Hugging Face.

For the concise step-by-step release checklist, use [publication-release-checklist.md](publication-release-checklist.md).

## PyPI

- Confirm `python_package`, `fastapi_service`, `benchmark_eval_tooling`, `docs_and_cards`, and `examples` boundaries are still valid.
- Confirm distribution name, owner, version, and migration notes. Until the rename is explicitly planned, `aana-eval-pipeline` remains transitional and `aana` remains the reserved future target.
- Run `python -m build`.
- Run `twine check dist/*`.
- Confirm default install remains useful without benchmark-only dependencies.
- Confirm public console scripts are limited to `aana`, `aana-fastapi`, and `aana-validate-platform`.
- Confirm FastAPI dependencies remain in the `api` extra.
- Confirm eval dependencies remain in the `eval` extra.
- Confirm `scripts*`, `tests*`, and `evals*` are excluded from the default wheel.

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
