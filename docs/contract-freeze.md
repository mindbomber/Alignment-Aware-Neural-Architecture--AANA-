# AANA Contract Freeze

Contract Freeze is the repo-local compatibility gate for public AANA integration surfaces. It defines which JSON shapes and version fields are stable enough for CLI, Python API, HTTP bridge, agent, workflow, skill/plugin, and evidence-integration users to depend on.

The primary public APIs are the Workflow Contract and the Agent Event Contract. New app, agent, CLI, SDK, HTTP, and low-code integrations should enter AANA through one of those contracts instead of depending on lower-level adapter runner internals.

Run it with:

```powershell
python scripts/aana_cli.py contract-freeze
python scripts/aana_cli.py contract-freeze --json
python scripts/dev.py contract-freeze
```

`release-check` also runs the contract freeze gate.

## Frozen Contracts

The current freeze version is `0.1`. These surfaces are frozen at the current repo-local compatibility level:

- Agent Event Contract
- agent check result
- Workflow Request Contract
- Workflow Batch Request Contract
- workflow result
- workflow batch result
- adapter JSON contract
- AIx runtime score block
- structured evidence object
- evidence registry
- redacted audit record
- audit metrics export
- audit integrity manifest
- AIx audit drift report

## Version Rules

Compatible changes may keep the current version:

- adding optional fields,
- adding new enum values only when older clients safely ignore them,
- adding new schemas or docs,
- tightening examples without changing accepted payloads.

Breaking changes require a version bump and migration notes:

- renaming or removing a required field,
- removing, renaming, or changing the meaning of a primary public API property,
- changing field meaning,
- changing accepted action or gate semantics,
- changing default routing behavior,
- changing redaction guarantees,
- making an optional field required,
- changing AIx score, decision, or hard-blocker semantics.

Version fields:

- `event_version` for agent events,
- `agent_check_version` for agent check results,
- `contract_version` for workflow requests/results,
- `aix_version` for AIx blocks,
- `registry_version` for evidence registries,
- `audit_record_version` for audit records,
- `audit_metrics_export_version` for metrics exports,
- `audit_integrity_manifest_version` for audit manifests.
- `audit_drift_report_version` for AIx drift reports.

## Compatibility Fixtures

The freeze gate validates:

- adapter gallery examples,
- all gallery adapter JSON files,
- checked-in agent event examples,
- Agent Event Contract valid/invalid fixtures for accept, revise, ask, defer, refuse, malformed candidates, unsupported actions, policy preset mismatches, route mismatches, and evidence source validation,
- structured workflow request example,
- workflow batch example,
- canonical Workflow Contract adapter-family examples for enterprise, personal productivity, and government/civic pilot surfaces,
- evidence registry,
- evidence mock connector fixtures for CRM/support, email, calendar, IAM, CI, deployment, billing, and data export,
- generated redacted audit record,
- generated audit metrics export,
- generated AIx audit drift report.

Required compatibility docs include this file, the Workflow Contract guide, agent integration guidance, the HTTP bridge runbook, OpenClaw skill conformance guidance, plugin install/use guidance, evidence integration contract guidance, audit observability hardening guidance, and pilot surface certification guidance.

The goal is not to prove every adapter behavior. The goal is to prevent accidental interface drift across the public surfaces that external agents and pilots will call.

## Internal Boundaries

Lower-level adapter execution code, including the current adapter runner implementation, is an implementation detail. It may be refactored, split into modules, or replaced as long as the frozen public contracts keep the same behavior or receive a documented version bump. External integrations should not import runner helpers, domain-specific verifier functions, or repair internals directly.

Public runtime surfaces must route through the primary contracts:

- Python SDK and typed runtime calls use Workflow Contract request/result objects.
- Agent integrations use Agent Event request/result objects.
- HTTP bridge routes `/workflow-check`, `/workflow-batch`, `/agent-check`, and `/playground/check` must return contract-shaped results or a thin wrapper around them.
- CLI `workflow-check`, `workflow-batch`, and gallery `run` must return Workflow Result shapes.
- Direct adapter-file execution is a diagnostics path only and must identify itself as outside the primary public API.
