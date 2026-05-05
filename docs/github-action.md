# AANA GitHub Action

The AANA GitHub Action lets teams add verifier-grounded PR and release checks with one workflow step. It runs the production adapter gallery through the Workflow Contract and writes redacted audit, metrics, JSON report, and Markdown summary artifacts.

## Guardrails

The action packages these adapters:

- `code_change_review`
- `deployment_readiness`
- `api_contract_change`
- `infrastructure_change_guardrail`
- `database_migration_guardrail`

Each adapter receives GitHub evidence such as changed files, git diff, CI status, test output, deployment manifest, release notes, OpenAPI diff, IaC plan, migration diff, schema state, backup status, and rollout plan. Evidence is converted into structured Workflow Contract objects and redacted audit records.

## One YAML Snippet

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

      - name: Run AANA guardrails
        uses: mindbomber/Alignment-Aware-Neural-Architecture--AANA-/.github/actions/aana-guardrails@main
        with:
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

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: aana-github-guardrails
          path: eval_outputs/github_action/aana-guardrails/
```

For a checked-in starter workflow, copy [examples/github-actions/aana-guardrails.yml](../examples/github-actions/aana-guardrails.yml).

## Failure Modes

`fail-on` controls how strict the action is:

- `candidate-block` - fail if the proposed PR/release candidate is blocked or the final gate fails. This is the recommended PR default.
- `recommended-action` - fail unless AANA recommends `accept`.
- `gate-fail` - fail only when the final AANA gate fails.
- `never` - advisory mode; write artifacts and summary but do not fail the job.

The action skips adapters when no relevant files or evidence are detected unless `force: "true"` is set.

## Outputs

The default artifact directory is `eval_outputs/github_action/aana-guardrails/`:

- `audit.jsonl` - redacted audit records.
- `metrics.json` - flat audit metrics.
- `report.json` - machine-readable guardrail report.
- `summary.md` - Markdown summary also appended to the GitHub step summary.

The audit log stores adapter IDs, gate decisions, recommended actions, AIx summaries, violation codes, fingerprints, and lengths. It does not store raw prompts, candidates, evidence, outputs, or safe responses.
