# Versioning and Migration

AANA versions the public and release-sensitive surfaces that affect runtime behavior:

- adapter version
- Workflow Contract version
- Agent Event Contract version
- verifier module version
- route map version
- AIx tuning version
- evidence connector manifest version
- audit schema version
- runtime version

The source of truth for the current inventory is `examples/version_migration_policy.json`.

## Breaking Changes

Breaking changes require:

- a version bump for the changed surface
- migration notes
- compatibility tests or golden-output tests

Examples of breaking changes include removing required result fields, changing route-map behavior for an existing violation code, changing AIx thresholds in a way that alters accept/revise/defer/refuse outcomes, changing audit redaction schema, or changing evidence connector requirements.

## Validation

Run:

```powershell
python scripts/validation/validate_versioning_migration.py
```

The release gate runs this validator before production-profile checks. It fails when a versioned surface is missing, when code constants drift from the policy manifest, or when a breaking migration note lacks compatibility tests.
