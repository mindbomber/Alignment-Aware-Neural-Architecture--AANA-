# MI Schema Versioning Policy

Status: milestone 5 schema versioning policy.

Active interoperability contract schema version: `0.1`.

Policy version: `0.1`.

## Versioning Rules

`interoperability_contract.schema.json` uses explicit contract versions, currently `contract_version: "0.1"`.

Patch-compatible schema changes may add optional fields, descriptions, examples, or non-required metadata when older readers can ignore the new data without changing gate behavior.

Breaking schema changes require a new contract version, migration notes, updated fixtures, updated validators, and regenerated pilot/dashboard/readiness artifacts before CI can pass.

## Breaking Changes

- Adding a required top-level field requires a new contract version and migration notes.
- Removing, renaming, or changing the meaning of a required field is breaking.
- Narrowing an enum, changing decision semantics, or tightening redaction requirements is breaking.
- Changing AIx, evidence, audit, dashboard, or readiness version compatibility is breaking for CI artifacts.
- Additive optional fields are non-breaking when old readers can ignore them safely.

## Compatibility Matrix

| Contract version | Pilot handoffs | Audit JSONL | Dashboard | Production readiness |
| --- | --- | --- | --- | --- |
| `0.1` | `0.1` | `0.1` | `0.1` | `0.1` |

## Migration Notes

- Initial MI handoff contract for recipient-relative constraint checking.
- Pilot handoffs, redacted MI audit records, dashboard payloads, and production readiness payloads are compatible at version 0.1.
- Future breaking versions must include a migration path for pilot fixtures, audit JSONL readers, dashboard exporters, and readiness gates.

## CI Enforcement

`scripts/validate_mi_contracts.py` checks that the JSON schema, pilot handoffs, audit JSONL, dashboard payload, and production-readiness payload remain compatible with the active interoperability contract version.
