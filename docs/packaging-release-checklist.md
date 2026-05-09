# AANA Packaging Release Checklist

AANA has five separate publication surfaces:

| Surface | Boundary |
| --- | --- |
| Python package | Runtime SDK, CLI, middleware helpers, audit utilities, and optional API/eval entrypoints. |
| TypeScript SDK | Browser/Node helper package and HTTP client. |
| FastAPI service | Optional API surface installed through the Python `api` extra. |
| Benchmark/eval tooling | Calibration, HF dataset, benchmark, and evidence-pack tooling. This is not the runtime core claim. |
| Docs and cards | GitHub Pages docs plus Hugging Face model/dataset card templates. |

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

## PyPI

- Confirm distribution name, owner, version, and migration notes.
- Run `python -m build`.
- Run `twine check dist/*`.
- Confirm default install remains useful without benchmark-only dependencies.
- Confirm FastAPI dependencies remain in the `api` extra.
- Confirm eval dependencies remain in the `eval` extra.

## npm

- Confirm package owner and access for `@aana/integration-sdk`.
- Run `cd sdk/typescript && npm install`.
- Run `cd sdk/typescript && npm run build`.
- Run `cd sdk/typescript && npm pack --dry-run`.

## Hugging Face

- Validate HF dataset registry, calibration plan, and proof report.
- Review the model and dataset cards by hand.
- Confirm public claims say AANA is an audit/control/verification/correction layer.
- Confirm benchmark probe or diagnostic results are not used as public claims.

## Service

- Install with the `api` extra.
- Run the FastAPI tests.
- Confirm token auth, rate limits, request-size limits, and redacted audit JSONL logging.
- Confirm public demos remain synthetic-only and cannot send, delete, purchase, deploy, or export.
