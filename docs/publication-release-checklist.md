# AANA Publication Release Checklist

Use this checklist before publishing any AANA artifact to PyPI, npm, or Hugging Face. The goal is to keep runtime packaging, public claims, examples, and evidence artifacts aligned.

## Required Preflight

- [ ] Run the standard pre-release platform gate: `python scripts/validate_aana_platform.py --timeout 240`.
- [ ] Run `python scripts/validation/validate_packaging_hardening.py --require-existing-artifacts`.
- [ ] Run `python scripts/validation/validate_aana_standard_publication.py --require-existing-artifacts`.
- [ ] Run `python scripts/validation/validate_security_hardening.py`.
- [ ] Confirm no raw secrets, API keys, tokens, private prompts, private account IDs, or unredacted private data are present.
- [ ] Confirm no generated `eval_outputs/` files are tracked unless moved into a reviewed evidence/artifact path with manifest coverage.
- [ ] Confirm public claims still say AANA is an audit/control/verification/correction layer, not a proven raw agent-performance engine.

## PyPI

- [ ] Confirm current distribution name and migration status: `aana-eval-pipeline` is transitional; import package and CLI remain `aana`.
- [ ] Confirm public console scripts are limited to `aana`, `aana-fastapi`, and `aana-validate-platform`.
- [ ] Confirm default install excludes repo-local `scripts*`, `tests*`, and `evals*`.
- [ ] Confirm FastAPI dependencies remain behind the `api` extra.
- [ ] Confirm eval dependencies remain behind the `eval` extra.
- [ ] Run `python -m build`.
- [ ] Run `twine check dist/*`.
- [ ] Inspect the built wheel metadata and entrypoints before upload.
- [ ] Do a human release review of README, docs, license, version, and changelog/release notes.

## npm

- [ ] Confirm package metadata in `sdk/typescript/package.json`.
- [ ] Confirm the TypeScript SDK only exposes contract/client/middleware helpers and does not bundle Python eval artifacts.
- [ ] Run `cd sdk/typescript && npm install`.
- [ ] Run `cd sdk/typescript && npm run build`.
- [ ] Run `cd sdk/typescript && npm pack --dry-run`.
- [ ] Inspect the packed file list before publishing.
- [ ] Confirm npm owner/access settings and publication scope.

## Hugging Face

- [ ] Validate HF dataset registry and split governance.
- [ ] Validate calibration vs held-out vs external-reporting separation.
- [ ] Review `docs/huggingface-model-card.md`.
- [ ] Review `docs/huggingface-dataset-card.md`.
- [ ] Confirm Space demo remains synthetic-only and cannot send, delete, purchase, deploy, export, or access real private data.
- [ ] Confirm benchmark artifacts are labeled as calibration, held-out, diagnostic, probe-only, or external_reporting.
- [ ] Confirm no probe-only or diagnostic result is presented as a stronger public claim.
- [ ] Link the model card, dataset card, Space, evidence pack, and technical report consistently.

## Final Signoff

- [ ] Release owner reviewed the artifact bundle.
- [ ] Security/privacy reviewer approved publication.
- [ ] Claim boundary reviewer approved public wording.
- [ ] Reproduction commands are present for any published benchmark/evidence artifact.
- [ ] Publication target, version, date, and commit SHA are recorded in release notes.
