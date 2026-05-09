# AANA Standard Publication Package

AANA should be published as a standard developers can wrap around agents:

```text
agent proposes -> AANA checks -> agent executes only if allowed
```

Public claim: AANA is an architecture for making agents more auditable, safer, more grounded, and more controllable.

## Package Surfaces

| Surface | Artifact | Purpose |
| --- | --- | --- |
| Python package | `pyproject.toml`, `aana/` | Local SDK, CLI, middleware, validators, and audit utilities. |
| TypeScript SDK | `sdk/typescript/package.json` | JavaScript/TypeScript helpers and HTTP client. |
| FastAPI service | `eval_pipeline/fastapi_app.py` | HTTP API with `/pre-tool-check`, `/agent-check`, `/health`, token auth, and redacted audit JSONL. |
| Benchmark/eval tooling | `eval_pipeline/hf_dataset_registry.py`, `eval_pipeline/hf_calibration.py`, `scripts/validate_hf_dataset_*` | Calibration, benchmark, and evidence-pack tooling. This is not runtime core. |
| Model/dataset cards | `docs/huggingface-model-card.md`, `docs/huggingface-dataset-card.md` | Public Hugging Face-ready descriptions with explicit evidence boundaries. |
| Agent Action Contract spec | `docs/agent-action-contract-v1.md`, `schemas/agent_tool_precheck.schema.json` | The seven-field public pre-execution contract. |

## Release Gate

Before publishing or updating public package surfaces, run:

```powershell
python scripts/validate_aana_standard_publication.py --require-existing-artifacts
python scripts/validate_packaging_hardening.py --require-existing-artifacts
```

The validator checks:

- Python metadata, import package, CLI scripts, and FastAPI optional dependencies.
- TypeScript package metadata and build script.
- FastAPI docs and expected API routes.
- Hugging Face model/dataset card templates and boundary language.
- Agent Action Contract v1 schema and required seven-field contract.
- Packaging boundaries for Python, TypeScript, FastAPI, eval tooling, docs, and cards.

For publication-specific steps, use [packaging-release-checklist.md](packaging-release-checklist.md).

## External Publishing Boundary

This repository can be made publish-ready locally without immediately publishing to PyPI, npm, Hugging Face, or any official benchmark channel. External publication should happen only after a final human release review confirms:

- package names and owners,
- tokens and permissions,
- version number,
- release notes,
- public evidence language,
- no benchmark probe results merged into public claims.
