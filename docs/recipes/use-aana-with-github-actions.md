# Use AANA With GitHub Actions

Use this recipe to add AANA guardrails to pull requests and release workflows. It checks code review, deployment readiness, API contract changes, infrastructure changes, and database migrations.

## Copy

Copy this workflow into `.github/workflows/aana-guardrails.yml`:

```yaml
name: AANA Guardrails

on:
  pull_request:
  workflow_dispatch:

jobs:
  aana:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Run AANA PR and release guardrails
        uses: mindbomber/Alignment-Aware-Neural-Architecture--AANA-/.github/actions/aana-guardrails@main
        with:
          adapters: code_change_review,deployment_readiness,api_contract_change,infrastructure_change_guardrail,database_migration_guardrail
          fail-on: candidate-block
          test-output: eval_outputs/test-output.txt
          deployment-manifest: deploy/production.json
          release-notes: RELEASE_NOTES.md
          openapi-diff: eval_outputs/openapi-diff.txt
          consumer-list: docs/api-consumers.md
          iac-plan: eval_outputs/tfplan.txt
          migration-diff: eval_outputs/migration-diff.sql
          schema-state: eval_outputs/schema-state.txt
          backup-status: eval_outputs/backup-status.txt
          rollout-plan: docs/migration-rollout.md

      - name: Upload AANA guardrail artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: aana-github-guardrails
          path: eval_outputs/github_action/aana-guardrails/
          if-no-files-found: warn
```

The same snippet is checked in at `examples/github-actions/aana-guardrails.yml`.

## Test Locally

Run the packaged guardrail engine without GitHub:

```powershell
python scripts/run_github_action_guardrails.py --fail-on never --changed-files "src/app.py,migrations/001.sql" --migration-diff eval_outputs/migration-diff.sql
```

## Expected Result

The action writes these artifacts under `eval_outputs/github_action/aana-guardrails/`:

- `audit.jsonl`
- `metrics.json`
- `report.json`
- `summary.md`

The local smoke command uses `--fail-on never`, so it exits successfully while still writing findings and artifacts. With `fail-on: candidate-block`, CI fails when AANA blocks the proposed candidate or the final gate fails.
