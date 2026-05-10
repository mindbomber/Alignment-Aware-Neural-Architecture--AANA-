# AANA Standard Publication Package

AANA should be published as a standard developers can wrap around agents:

```text
agent proposes -> AANA checks -> agent executes only if allowed
```

Public claim: AANA makes agents more auditable, safer, more grounded, and more controllable.

## Package Surfaces

| Surface | Artifact | Purpose |
| --- | --- | --- |
| Python package | `pyproject.toml`, `aana/` | Runtime SDK, runtime CLI, middleware, API entrypoint wrappers, and audit utilities. |
| TypeScript SDK | `sdk/typescript/package.json` | JavaScript/TypeScript helpers and HTTP client. |
| FastAPI service | `eval_pipeline/fastapi_app.py` | HTTP API with `/pre-tool-check`, `/agent-check`, `/health`, token auth, and redacted audit JSONL. |
| Benchmark/eval tooling | `scripts/`, `eval_pipeline/hf_dataset_registry.py`, `eval_pipeline/hf_calibration.py` | Calibration, benchmark, and evidence-pack tooling. This is repo-local/dev tooling, not runtime core, and is not installed as public console scripts. |
| Model/dataset cards | `docs/huggingface-model-card.md`, `docs/huggingface-dataset-card.md` | Public Hugging Face-ready descriptions with explicit evidence boundaries. |
| Agent Action Contract spec | `docs/agent-action-contract-v1.md`, `schemas/agent_tool_precheck.schema.json` | The seven-field public pre-execution contract. |

## Package Naming

The current Python distribution is `aana-eval-pipeline`; this is a transitional legacy name from the earlier evaluation-pipeline phase. The import package, CLI, and platform-facing language are already `aana`.

The intended future PyPI distribution target is `aana`. Do not perform that rename as part of routine cleanup. A rename requires migration notes, a compatibility window for `aana-eval-pipeline`, preserved `import aana`, and stable `aana`, `aana-fastapi`, and `aana-validate-platform` CLI behavior.

## Release Gate

Before publishing or updating public package surfaces, run:

```powershell
python scripts/validation/validate_aana_standard_publication.py --require-existing-artifacts
python scripts/validation/validate_packaging_hardening.py --require-existing-artifacts
```

The validator checks:

- Python metadata, import package, runtime-only CLI scripts, package include/exclude rules, and FastAPI optional dependencies.
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
