# AANA Architecture Map

AANA is organized as a control layer around agents:

```text
agent proposes -> AANA checks -> tool/action executes only when route == accept
```

## Runtime Surfaces

```text
CLI / SDK / FastAPI / MCP / middleware
          |
          v
Agent Action Contract v1
          |
          v
AANA gate and verifier stack
          |
          +--> adapters
          +--> evidence/auth checks
          +--> route semantics
          +--> audit event
          |
          v
accept | revise | retrieve | ask | defer | refuse
```

## Components

| Component | Role | Main paths |
| --- | --- | --- |
| CLI | Local developer entrypoint for checks, audit summaries, bundle certification, and validation. | `aana/cli.py`, `scripts/aana_cli.py` |
| Python SDK | Importable runtime API for `check_tool_call`, `gate_action`, wrappers, and middleware helpers. | `aana/sdk.py`, `aana/middleware.py` |
| TypeScript SDK | JS/TS contract helpers and API client for agent apps. | `sdk/typescript/` |
| FastAPI | Optional HTTP policy service for agents that call AANA over the network. | `aana/fastapi_app.py`, `eval_pipeline/fastapi_app.py` |
| MCP | Tool/server integration path for MCP-compatible agents. | `eval_pipeline/mcp_server.py`, `scripts/integrations/aana_mcp_server.py` |
| Adapters | Domain/family verifier logic and manifests for privacy, grounded QA, tool-use, governance, security, and domain risk. | `aana/adapters/`, `eval_pipeline/adapter_runner/` |
| Bundles | Product groupings that declare core adapters, evidence connectors, human-review needs, and validation coverage. | `aana/bundles/` |
| Registry | Canonical source for adapter IDs, bundle IDs, aliases, routes, datasets, and evidence connectors. | `aana/registry.py`, `aana/canonical_ids.py` |
| Validators | Harmony gates that prevent drift across contracts, docs, bundles, packaging, security, and claims. | `aana/validate_platform.py`, `scripts/validation/` |

## Contract Flow

1. An agent, tool wrapper, CLI command, API caller, or MCP tool emits an Agent Action Contract v1 event.
2. The event includes `tool_name`, `tool_category`, `authorization_state`, `evidence_refs`, `risk_domain`, `proposed_arguments`, and `recommended_route`.
3. AANA validates the event shape, evidence safety, authorization state, route semantics, and adapter-specific constraints.
4. AANA returns the shared decision shape: route, AIx score, hard blockers, missing evidence, authorization state, recovery suggestion, and audit-safe event.
5. Wrappers and middleware fail closed: only `accept` may execute.

## Bundle Flow

```text
adapter manifests
      |
      v
bundle manifests
      |
      v
bundle certification
      |
      v
platform validator
```

Bundles such as `enterprise`, `personal_productivity`, and `government_civic` do not replace adapters. They declare which adapters and evidence connectors are required for a product surface, when human review is required, and what validation coverage must exist before stronger claims.

## Validation Flow

The main platform gate is:

```powershell
python scripts/validate_aana_platform.py --timeout 240
```

It runs adapter layout, repo organization, contract freeze, integration parity, bundle certification, HF dataset split governance, public claims policy, security hardening, packaging hardening, evidence-artifact checks, and versioning checks.

Use this map when adding a new adapter, SDK wrapper, API route, MCP tool, bundle, benchmark artifact, or public claim. New work should connect through the same contract, registry, route semantics, audit event, and validation gates.

For the canonical repo layout and script grouping policy, see [repo-organization.md](repo-organization.md).
