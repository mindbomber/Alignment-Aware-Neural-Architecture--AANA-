# Alignment-Aware Neural Architecture (AANA)

[![CI](https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/actions/workflows/ci.yml/badge.svg)](https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Status: Alpha Research](https://img.shields.io/badge/status-alpha%20research-orange.svg)](ROADMAP.md)
[![Try AANA](https://img.shields.io/badge/Hugging%20Face-Try%20AANA-yellow.svg)](https://huggingface.co/spaces/mindbomber/aana-demo)
[![Evidence Pack](https://img.shields.io/badge/evidence-peer%20review%20pack-blueviolet.svg)](https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack)
[![Agent Action Contract v1](https://img.shields.io/badge/contract-Agent%20Action%20v1-2ea44f.svg)](docs/agent-action-contract-v1.md)
[![Roadmap](https://img.shields.io/badge/roadmap-public-lightgrey.svg)](docs/public-roadmap.md)

Public site: https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/

Try AANA in 2 minutes: https://huggingface.co/spaces/mindbomber/aana-demo

Hosted static demo: https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/demo/

Static docs demo: [docs/tool-call-demo/index.html](docs/tool-call-demo/index.html)

![AANA repository social preview](assets/github-social-preview.png)

AANA is a pre-action control layer for AI agents: agents propose actions, AANA checks evidence/auth/risk, and tools execute only when the route is accept.

Current evidence boundary: AANA is production-candidate as an audit/control/verification/correction layer. AANA is not yet proven as a raw agent-performance engine. See [docs/aana-production-candidate-evidence-pack.md](docs/aana-production-candidate-evidence-pack.md).

Theoretical anchor: AANA is grounded in the correction-capacity versus optimization-pressure framing:

```text
dA/dt = -pi * epsilon * (1 - gamma) - Lambda + C - Phi
```

Here `pi` is optimization pressure, `epsilon` is constraint misclassification, `gamma` is feedback fidelity, `Lambda` is irreversible or path-dependent loss, `C` is correction capacity, and `Phi` is viable-region drift. The platform's practical rule is that consequential agent actions need correction capacity to scale with divergence pressure: `C >= pi * epsilon * (1 - gamma) + Lambda + Phi`.

AANA is not production-certified by local tests alone. Public surfaces should describe AANA as demo-ready, pilot-ready, or production-candidate until live evidence connectors, domain owner signoff, audit retention, observability, human review path, security review, deployment manifest, incident response plan, and measured pilot results are complete. Passing `pilot-certify`, `release-check`, or local tests does not certify production safety.

## Recommended Local Path

Use AANA first as a runtime guardrail layer: install the package, run `aana` checks locally, wrap one consequential tool, and only then add API or middleware surfaces. The Workflow Contract, Agent Event Contract, and Agent Action Contract are the product path; eval workflows, benchmark runners, and research scripts under `scripts/` are validation tooling, not the public runtime interface.

```powershell
python -m pip install -e .
aana doctor
aana run travel_planning
aana workflow-check --workflow examples/workflow_research_summary.json --audit-log eval_outputs/audit/local-onboarding.jsonl
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/aana-bridge.jsonl
aana audit-summary --audit-log eval_outputs/audit/local-onboarding.jsonl
```

## What AANA Adds

Most agent safety tools fit into one bucket: prompt instructions, moderation/classification, LLM-as-judge review, framework middleware, or opaque provider-side model alignment. AANA standardizes the pre-action decision itself:

```text
agent proposes -> AANA checks -> tool executes only if route == accept
```

AANA adds:

- a structured Agent Action Contract,
- evidence/auth-aware routing with `accept`, `revise`, `retrieve`, `ask`, `defer`, and `refuse`,
- hard execution rules so wrapped tools do not execute unless AANA allows them,
- correction and recovery guidance,
- audit-safe decision logs,
- cross-surface parity across CLI, Python SDK, TypeScript SDK, FastAPI, MCP, and agent middleware.

The value is not that AANA is a smarter base agent. The value is that AANA makes consequential agent actions inspectable, enforceable, and reviewable before execution.

## Adoption Signals

Looking for a first contribution?

- Browse [good first integration issues](https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/labels/good%20first%20integration).
- Request an adapter or integration with the GitHub issue templates.
- Report safety/control failures with a redacted Agent Action Contract event.
- Run the example stack in [examples/integrations](examples/integrations): plain Python, OpenAI Agents SDK, LangChain, FastAPI API guard, and MCP all prove blocked tools do not execute.

## Quick Start

Clone and install locally:

```powershell
git clone https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-.git
cd Alignment-Aware-Neural-Architecture--AANA-
python -m pip install -e .
```

Run a pre-tool-call check:

```powershell
aana pre-tool-check --event examples/agent_tool_precheck_private_read.json
```

Run an agent-output check:

```powershell
aana agent-check --event examples/agent_event_support_reply.json
```

Start the local FastAPI policy service:

```powershell
aana-fastapi --host 127.0.0.1 --port 8766
```

Then use:

- `GET /health`
- `POST /pre-tool-check`
- `POST /agent-check`
- OpenAPI docs at `http://127.0.0.1:8766/docs`

No LLM API key is required for deterministic local checks. Provider keys are only needed for live model-loop experiments or optional semantic verifier paths.

## Agent Action Contract Standard

The public contract v1 fields are:

```json
{
  "tool_name": "send_email",
  "tool_category": "write",
  "authorization_state": "user_claimed",
  "evidence_refs": [{
    "source_id": "draft:123",
    "kind": "draft",
    "trust_tier": "user_provided",
    "redaction_status": "redacted",
    "summary": "User-provided draft exists.",
    "provenance": "agent_runtime",
    "freshness": "current"
  }],
  "risk_domain": "customer_support",
  "proposed_arguments": {"to": "customer@example.com"},
  "recommended_route": "accept"
}
```

AANA returns a decision shape with:

- `route`
- AIx score
- hard blockers
- missing evidence
- authorization state
- recovery suggestion
- audit-safe log event

See the clean reusable standard at [docs/agent-action-contract-v1.md](docs/agent-action-contract-v1.md) and the quickstart at [docs/agent-action-contract-quickstart.md](docs/agent-action-contract-quickstart.md).

## Python SDK

```python
import aana

decision = aana.check_tool_call({
    "tool_name": "get_recent_transactions",
    "tool_category": "private_read",
    "authorization_state": "authenticated",
    "evidence_refs": [{
        "source_id": "auth.session",
        "kind": "auth_context",
        "trust_tier": "system",
        "redaction_status": "redacted",
        "summary": "User authenticated for account view.",
        "provenance": "session",
        "freshness": "current"
    }],
    "risk_domain": "finance",
    "proposed_arguments": {"account_id": "acct_demo", "limit": 5},
    "recommended_route": "accept"
})

if decision["route"] == "accept":
    ...
```

Wrap a tool:

```python
guarded = aana.wrap_agent_tool(send_email)
```

Wrapped tools execute only when AANA returns `accept`. See [docs/aana-agent-contract-sdk.md](docs/aana-agent-contract-sdk.md), [docs/python-runtime-api.md](docs/python-runtime-api.md), and [docs/agent-framework-middleware.md](docs/agent-framework-middleware.md).

## TypeScript SDK

The TypeScript SDK lives in [sdk/typescript](sdk/typescript). It provides Agent Action Contract helpers and an HTTP client for the AANA service.

See [sdk/typescript/README.md](sdk/typescript/README.md).

## API Service

The FastAPI service exposes AANA as an internal policy service for agents that cannot import the Python SDK directly.

Core routes:

- `GET /health`
- `POST /pre-tool-check`
- `POST /agent-check`

The service supports bearer-token auth, request-size limits, OpenAPI docs, and optional redacted audit JSONL logging. See [docs/fastapi-service.md](docs/fastapi-service.md).

## Integrations

Use the same AANA decision shape across:

- OpenAI Agents SDK
- LangChain
- FastAPI API guard
- AutoGen
- CrewAI
- MCP tool calls
- plain Python/TypeScript functions

Main integration proof:

```powershell
python scripts/validation/validate_agent_integrations.py
```

Expected result:

```text
pass -- passed=15/15
```

For the full walkthrough, see [docs/openai-agents-quickstart.md](docs/openai-agents-quickstart.md), [docs/integrate-runtime/index.md](docs/integrate-runtime/index.md), and [examples/integrations](examples/integrations).

## Evidence And Peer Review

Start here:

- [Try AANA in 2 minutes](https://huggingface.co/spaces/mindbomber/aana-demo)
- [Agent Action Contract v1 standard](docs/agent-action-contract-v1.md)
- [AANA public artifact hub](https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4)
- [AANA peer-review evidence pack](https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack)
- [AANA Hugging Face Space](https://huggingface.co/spaces/mindbomber/aana-demo)
- [Public review and adoption guide](docs/public-review-and-adoption.md)
- [AANA head-to-head findings](docs/aana-head-to-head-findings.md)
- [Short technical report: AANA as a pre-action control layer](docs/aana-pre-action-control-layer-technical-report.md)
- [AANA agent-action technical report](docs/aana-agent-action-technical-report.md)
- [Public roadmap](docs/public-roadmap.md)
- [Maintainer review / benchmark submission request](docs/maintainer-review-benchmark-submission-request.md)
- [Review outreach posting guide](docs/review-outreach-posting-guide.md)
- [Production-candidate evidence pack](docs/aana-production-candidate-evidence-pack.md)
- [Reviewed evidence artifact manifest](docs/evidence/artifact_manifest.json)
- [Research and evaluation workflows](docs/research-evaluation-workflows.md)
- [Repository organization](docs/repo-organization.md)

Benchmark and dataset results are labeled as calibration, held-out, diagnostic, probe, or external-reporting artifacts. They should not be presented as proof that AANA is a raw agent-performance engine. See [docs/public-claims-policy.md](docs/public-claims-policy.md) and [docs/benchmark-reporting-policy.md](docs/benchmark-reporting-policy.md).

## Platform Validation

Run the full platform harmony gate:

```powershell
aana-validate-platform
```

This checks adapter layout, contract freeze, integration parity, bundle certification, HF dataset split governance, public claims policy, security hardening, packaging hardening, versioning, and publication surfaces.

Additional publication gates:

```powershell
python scripts/validation/validate_aana_standard_publication.py --require-existing-artifacts
python scripts/validation/validate_packaging_hardening.py --require-existing-artifacts
```

The default Python install exposes three top-level commands: `aana`, `aana-fastapi`, and `aana-validate-platform`. Benchmark runners, HF experiments, publication tools, and research validators remain grouped under `scripts/`.

The current Python distribution name is the transitional legacy name `aana-eval-pipeline`; the import package and CLI are already `aana`. The intended future distribution target is `aana`, but that rename requires migration notes, a compatibility window, and preserved CLI/import behavior.

## Repository Map

- `aana/` - runtime SDK, CLI entrypoints, middleware, registry, adapters, and bundles.
- `eval_pipeline/` - shared runtime internals plus research/eval support modules.
- `sdk/typescript/` - TypeScript SDK.
- `examples/` - synthetic fixtures, integration demos, API examples, and demo sources.
- `docs/` - product docs, architecture docs, evidence reports, and publication guidance.
- `scripts/` - repo-local validation, benchmark, HF, and development tooling.
- `tests/` - unit and platform validation tests.
- `papers/` - research manuscripts connected to AANA.
- `eval_outputs/` - generated local outputs, intentionally ignored by git.

## More Docs

- [Try Demo](docs/try-demo/index.md)
- [Public Review And Adoption](docs/public-review-and-adoption.md)
- [Community Issue Intake And PR Targeting](docs/community-issue-intake.md)
- [Build Adapter](docs/build-adapter/index.md)
- [Evidence Handling](docs/evidence-handling.md)
- [Architecture Map](docs/architecture-map.md)
- [Repository Organization](docs/repo-organization.md)
- [Auditability](docs/auditability.md)
- [Authorization State](docs/authorization-state.md)
- [Security Threat Model](docs/aana-security-threat-model.md)
- [AANA Standard Publication Package](docs/aana-standard-publication.md)
- [Packaging Release Checklist](docs/packaging-release-checklist.md)
- [Publication Release Checklist](docs/publication-release-checklist.md)
- [HF Dataset Strategy](docs/hf-dataset-strategy.md)
- [HF Dataset Proof Report](docs/hf-dataset-proof-report.md)

## Safety Notes

- Review generated outputs before sharing them publicly.
- Do not commit `.env`, API keys, raw private prompts, or unpublished data.
- Public demos are synthetic-only and cannot send, delete, purchase, deploy, or export.
- Local validation does not certify production deployment. Production use still needs live evidence connectors, domain owner signoff, audit retention, observability, human review, security review, deployment manifest, incident response, and measured pilot results.

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
