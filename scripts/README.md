# Development Helpers

Top-level commands stay intentionally small: `aana`, `aana-fastapi`, and `aana-validate-platform`.
The repo-owned compatibility scripts in this folder are only for local development. Experiment,
benchmark, Hugging Face, publication, validation, pilot, demo, adapter, and integration helpers
live in grouped subfolders so the runtime surface does not blur into research tooling.

`dev.py` provides short, cross-platform commands for common local checks.

Run from the repository root:

```powershell
python scripts/dev.py test
python scripts/dev.py sample
python scripts/dev.py dry-run
python scripts/dev.py check
python scripts/dev.py production-profiles
python scripts/dev.py production-profiles --audit-log eval_outputs/audit/ci/aana-ci-audit.jsonl --metrics-output eval_outputs/audit/ci/aana-ci-metrics.json
python scripts/dev.py contract-freeze
python scripts/dev.py pilot-bundle
python scripts/dev.py pilot-eval
python scripts/dev.py starter-kits
python scripts/dev.py github-guardrails
python scripts/aana_cli.py cli-contract
python scripts/aana_cli.py cli-contract --json
python scripts/aana_cli.py aix-tuning
python scripts/aana_cli.py contract-freeze
python scripts/aana_cli.py evidence-integrations --evidence-registry examples/evidence_registry.json --mock-fixtures examples/evidence_mock_connector_fixtures.json
python scripts/aana_cli.py audit-validate --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py audit-drift --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/aana-aix-drift.json
python scripts/aana_cli.py audit-reviewer-report --audit-log eval_outputs/audit/aana-audit.jsonl --metrics eval_outputs/audit/aana-metrics.json --drift-report eval_outputs/audit/aana-aix-drift.json --output eval_outputs/audit/aana-reviewer-report.md
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl --shadow-mode
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl
python scripts/aana_cli.py pilot-certify
python scripts/aana_cli.py certify-bundle enterprise
python scripts/aana_cli.py certify-bundle personal_productivity
python scripts/aana_cli.py certify-bundle government_civic
python scripts/aana_cli.py production-certify --certification-policy examples/production_certification_template.json --deployment-manifest path/to/deployment.json --governance-policy path/to/governance.json --evidence-registry path/to/evidence_registry.json --observability-policy path/to/observability.json --audit-log path/to/redacted-shadow-audit.jsonl
docker compose up --build
Get-Content docs/integration-recipes.md
python scripts/demos/run_playground.py
python scripts/pilots/run_design_partner_pilots.py --pilot all
python scripts/demos/run_local_demos.py
start http://127.0.0.1:8765/dashboard
python scripts/pilots/run_e2e_pilot_bundle.py
python scripts/pilots/run_pilot_evaluation_kit.py
python scripts/pilots/run_pilot_evaluation_kit.py --pack enterprise --report-output eval_outputs/pilot_eval/enterprise-report.md
python scripts/pilots/run_starter_pilot_kit.py --kit all
python scripts/pilots/run_starter_pilot_kit.py --kit enterprise
python scripts/pilots/run_starter_pilot_kit.py --kit personal_productivity
python scripts/pilots/run_starter_pilot_kit.py --kit government_civic
python scripts/integrations/run_github_action_guardrails.py --changed-files "src/app.py,migrations/001.sql" --migration-diff eval_outputs/migration-diff.sql
python scripts/benchmarks/community_issue_scout.py --output examples/community_issue_candidates.json
python scripts/benchmarks/community_issue_solver.py --repository adhit-r/fairmind --limit 1
python scripts/pilots/pilot_smoke_test.py --audit-log eval_outputs/audit/aana-pilot-smoke.jsonl
python scripts/pilots/run_internal_pilot.py --audit-log eval_outputs/audit/aana-internal-pilot.jsonl
python scripts/pilots/run_internal_pilot.py --audit-log eval_outputs/audit/aana-internal-pilot.jsonl --metrics-output eval_outputs/audit/aana-internal-pilot-metrics.json
python scripts/aana_cli.py release-check --skip-local-check --audit-log eval_outputs/audit/aana-internal-pilot.jsonl
python scripts/aana_cli.py audit-verify --manifest eval_outputs/audit/manifests/aana-internal-pilot-integrity.json
```

Commands:

- `compile` - Compile Python files in `eval_pipeline/`, `tests/`, and `scripts/`.
- `test` - Run the unit tests.
- `sample` - Score the checked-in sample outputs.
- `dry-run` - Generate held-out tasks, run a tiny no-API evaluation, and score it.
- `check` - Run compile, tests, and sample scoring.
- `contract-freeze` - Validate frozen public AANA contracts, schemas, compatibility fixtures, and contract documentation.
- `production-profiles` - CI guard for adapter gallery examples, AIx tuning, internal pilot deployment/governance/observability profiles, evidence registry, evidence integration stubs, audit metrics export, and release-check with a generated redacted audit log. Use `--audit-log` and `--metrics-output` when CI or a handoff process needs stable artifact paths.
- `pilot-bundle` - Run the end-to-end pilot bundle across agent events, audit logging, metrics export, release-check, and production-profile validation.
- `pilot-eval` - Run the AANA Pilot Evaluation Kit and write a redacted audit log, audit metrics JSON, JSON report, and Markdown report.
- `starter-kits` - Run the starter pilot kits for enterprise, personal productivity, and civic/government packs using only synthetic workflow data.
- `github-guardrails` - Run the GitHub Action guardrail engine locally in advisory mode across the packaged PR/release adapters.
- `aana_cli.py cli-contract` - Print the stable CLI command matrix, exit-code meanings, JSON error contract, and major command examples for operator use.
- `aana_cli.py aix-tuning` - Report each gallery adapter's AIx risk tier, beta, layer weights, thresholds, and whether the values meet the declared tier.
- `aana_cli.py contract-freeze` - Report frozen contract inventory and validate schemas plus compatibility fixtures for adapters, agent events, workflows, AIx, evidence, audit records, and metrics.
- `aana_cli.py evidence-integrations` - List production evidence connector contracts, verify that the evidence registry covers required source IDs, and optionally validate mock connector fixtures for auth, source scope, freshness, redaction, failure routing, and normalized evidence objects.
- `aana_cli.py audit-validate` - Validate redacted audit JSONL records and reject raw sensitive fields.
- `aana_cli.py audit-drift` - Generate an AIx drift report from redacted audit JSONL.
- `aana_cli.py audit-reviewer-report` - Write a Markdown reviewer report from audit, metrics, drift, and manifest artifacts.
- `aana_cli.py pilot-certify` - Print the public pilot readiness score plus surface matrix, and fail on missing CLI, API, bridge, adapter, evidence, audit/metrics, docs, contract, or skill/plugin gates.
- `aana_cli.py certify-bundle <enterprise|personal_productivity|government_civic>` - Certify one product bundle's manifest declarations, required evidence connectors, human-review requirements, minimum validation coverage, adapter layout, and existing family certification surfaces.
- `aana_cli.py production-certify` - Certify the stricter production boundary: shadow-mode duration and volume, required metrics, human-review routing, connector evidence, audit retention, and production signoff.
- `docker compose up --build` - Run the Dockerized local HTTP bridge on `http://localhost:8765` with the bundled adapter gallery, local token auth, mounted redacted audit logs, and internal pilot profiles. See `docs/docker-http-bridge.md` for `/ready`, `/agent-check`, `/workflow-check`, and `/workflow-batch` examples.
- `docs/integration-recipes.md` - Copyable recipes for GitHub Actions, local agents, CRM support drafts, deployment reviews, and shadow-mode pilots.
- `run_playground.py` - Run the local HTTP bridge with the web playground at `http://localhost:8765/playground`, the local action demos at `http://localhost:8765/demos`, and redacted playground audit logging enabled.
- `run_design_partner_pilots.py` - Run the controlled enterprise, developer/tooling, personal productivity, and civic/government-style pilot bundles and write redacted audit, metrics, reviewer, field-notes, and feedback-template artifacts.
- `run_local_demos.py` - Run the local HTTP bridge with the desktop/browser demos for email send, file operation, calendar scheduling, purchase/booking, and research grounding checks at `http://localhost:8765/demos`.
- `http://localhost:8765/dashboard` - Review redacted audit metrics for gate/action counts, violation trends, AIx score range, hard blockers, adapter breakdowns, and shadow-mode would-block rates.
- `run_e2e_pilot_bundle.py` - Run multiple checked-in agent events, append redacted audit records, export audit metrics, write an audit integrity manifest, run release-check, and run production profile validation.
- `run_pilot_evaluation_kit.py` - Run named synthetic and public-data-rehearsal pilot packs for enterprise, personal, civic/government, and public-data evaluation planning.
- `run_starter_pilot_kit.py` - Materialize starter pilot kit workflows from synthetic records, run adapter checks, write redacted audit JSONL, export metrics JSON, and produce JSON/Markdown reports under `eval_outputs/starter_pilot_kits/`.
- `run_github_action_guardrails.py` - Run the GitHub Action guardrail engine locally against changed files, diffs, and optional release evidence for code review, deployment readiness, API contract, infrastructure, and database migration adapters.
- `community_issue_scout.py` - Search public GitHub issues and write a heuristic AANA intake candidate list with issue family, suggested adapter, evidence needs, first action, and publication boundary. Convert one candidate at a time into a Workflow Contract before acting.
- `community_issue_solver.py` - Create AANA-gated workpacks for selected public GitHub issues, including a public response draft, Workflow Contract, gate result, and local publish boundary. The script stops before posting, opening PRs, or pushing branches.
- `pilot_smoke_test.py` - Start or target the AANA HTTP bridge, verify POST auth, run an agent check, verify server-side redacted audit append, and summarize the audit log.
- `aana_server.py` - Run the local HTTP bridge with POST auth, optional token-file rotation, request-size limits, process-local rate limits, read timeouts, `/health`, `/ready`, OpenAPI, and server-side audit append.
- `run_internal_pilot.py` - Set up the internal pilot runtime directories, start the real bridge with `AANA_BRIDGE_TOKEN` and `--audit-log`, run the smoke test against that live bridge, write an audit integrity manifest and metrics export, and shut it down.
- `aana_cli.py audit-metrics` - Export flat dashboard metrics from redacted audit JSONL, including gate decisions, recommended actions, violation codes, adapter counts, record types, and AIx score/decision/hard-blocker fields.
- `aana_cli.py agent-check --shadow-mode` / `workflow-check --shadow-mode` / `workflow-batch --shadow-mode` - Observe proposed actions without returning a blocking exit code, append redacted shadow audit records, and feed would-pass/revise/defer/refuse dashboard metrics.
- `aana.AANAClient` and `sdk/typescript` - Application SDK helpers for building evidence objects, Agent Events, Workflow Contract requests, and bridge calls without hand-building JSON. See `docs/adapter-integration-sdk.md`.
- `aana_cli.py release-check` - Enforce release gates, including adapter AIx tuning against declared risk tiers.
- `aana_cli.py release-check --audit-log` - Also enforce release AIx thresholds against redacted audit logs, failing on low AIx scores, AIx hard blockers, or disallowed final AIx decisions.
- `aana_cli.py audit-manifest` / `audit-verify` - Create and verify local SHA-256 manifests for redacted audit JSONL files.
