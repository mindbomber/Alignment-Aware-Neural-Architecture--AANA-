# Use AANA For Deployment Reviews

Use this recipe before a production deployment or release promotion. The deployment readiness adapter checks config, secrets, rollback, health checks, migrations, and observability.

## Copy

Run the included deployment workflow:

```powershell
python scripts/aana_cli.py workflow-check --workflow examples/workflow_deployment_readiness.json --evidence-registry examples/evidence_registry.json --require-structured-evidence --audit-log eval_outputs/audit/recipes/deployment-review.jsonl
```

For a release gate, combine the workflow check with release-check:

```powershell
python scripts/aana_cli.py release-check --deployment-manifest examples/production_deployment_internal_pilot.json --governance-policy examples/human_governance_policy_internal_pilot.json --evidence-registry examples/evidence_registry.json --observability-policy examples/observability_policy_internal_pilot.json --audit-log eval_outputs/audit/recipes/deployment-review.jsonl
```

## Evidence Expected

Use structured evidence objects from:

- `deployment-manifest`
- `ci-result`
- `release-notes`

For real deployments, add connector-backed summaries for rollout plan, migration checks, observability ownership, alert routes, and rollback/roll-forward procedure.

## Expected Result

The checked-in deployment candidate attempts to deploy with `debug=true`, image `latest`, failed CI, inline secret-like data, no rollback, skipped health checks, unsafe migration, and missing observability. AANA should prevent direct acceptance and recommend a safer route such as `defer` or `revise`.

Review the dashboard feed:

```powershell
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/recipes/deployment-review.jsonl --output eval_outputs/audit/recipes/deployment-review-metrics.json
```
