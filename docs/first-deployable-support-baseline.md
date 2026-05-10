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

## Environment Baselines

Environment-specific artifacts use the same schema and attach deployment evidence:

- `examples/first_deployable_support_baseline.internal_pilot.json`
- `examples/external_production_evidence_internal_pilot.json`
- `examples/production_deployment_internal_pilot.json`
- `examples/support_domain_owner_signoff_internal_pilot.json`
- `examples/internal_pilot_measured_results_support.json`

The internal-pilot artifact can pass `--require-reached` because it declares live-approved internal-pilot connector manifests, an approved support owner signoff artifact, the internal-pilot deployment manifest, and measured pilot metrics. It remains scoped to `environment: internal-pilot` and is not production certification for external customer traffic.

## Validation

```powershell
python scripts/validation/validate_first_deployable_baseline.py
```

Use `--require-reached` only with an environment-specific artifact that attaches approved support domain signoff and measured pilot results:

```powershell
python scripts/validation/validate_first_deployable_baseline.py --baseline path/to/baseline.json --require-reached
```

For the checked-in internal-pilot baseline:

```powershell
python scripts/validation/validate_first_deployable_baseline.py --baseline examples/first_deployable_support_baseline.internal_pilot.json --require-reached
```
