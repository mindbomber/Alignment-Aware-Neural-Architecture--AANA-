# First Deployable Support Baseline

The first deployable AANA support runtime baseline is a boundary artifact, not a local-test claim. The source of truth is `examples/first_deployable_support_baseline.json`.

The baseline is reached only when all of these are true:

- support adapters run through Workflow Contract and Agent Event Contract paths
- runtime routing is registry-driven
- live or approved support evidence connectors exist
- audit-safe records are emitted
- human review paths are wired
- golden outputs pass
- gallery validation passes
- release gate passes
- security/privacy review is complete
- support domain owner signs off
- internal pilot shows acceptable over-acceptance, over-refusal, latency, and correction metrics

The checked-in baseline artifact is intentionally `not_reached_external_evidence_required`. Repo-local gates can validate contracts, registry routing, fixture-backed evidence boundaries, audit redaction, gallery metadata, golden outputs, and release wiring. They cannot prove support owner approval or measured pilot performance on live traffic.

## Validation

```powershell
python scripts/validate_first_deployable_baseline.py
```

Use `--require-reached` only with an environment-specific artifact that attaches approved support domain signoff and measured pilot results:

```powershell
python scripts/validate_first_deployable_baseline.py --baseline path/to/baseline.json --require-reached
```
