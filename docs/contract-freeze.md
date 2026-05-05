# AANA Contract Freeze

Contract Freeze is the repo-local compatibility gate for public AANA integration surfaces. It defines which JSON shapes and version fields are stable enough for CLI, Python API, HTTP bridge, agent, workflow, skill/plugin, and evidence-integration users to depend on.

Run it with:

```powershell
python scripts/aana_cli.py contract-freeze
python scripts/aana_cli.py contract-freeze --json
python scripts/dev.py contract-freeze
```

`release-check` also runs the contract freeze gate.

## Frozen Contracts

The current freeze version is `0.1`. These surfaces are frozen at the current repo-local compatibility level:

- adapter JSON contract
- Agent Event Contract
- agent check result
- Workflow Request Contract
- Workflow Batch Request Contract
- workflow result
- workflow batch result
- AIx runtime score block
- structured evidence object
- evidence registry
- redacted audit record
- audit metrics export
- audit integrity manifest

## Version Rules

Compatible changes may keep the current version:

- adding optional fields,
- adding new enum values only when older clients safely ignore them,
- adding new schemas or docs,
- tightening examples without changing accepted payloads.

Breaking changes require a version bump and migration notes:

- renaming or removing a required field,
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

## Compatibility Fixtures

The freeze gate validates:

- adapter gallery examples,
- all gallery adapter JSON files,
- checked-in agent event examples,
- Agent Event Contract valid/invalid fixtures for accept, revise, ask, defer, refuse, malformed candidates, unsupported actions, policy preset mismatches, route mismatches, and evidence source validation,
- structured workflow request example,
- workflow batch example,
- evidence registry,
- generated redacted audit record,
- generated audit metrics export.

The goal is not to prove every adapter behavior. The goal is to prevent accidental interface drift across the public surfaces that external agents and pilots will call.
