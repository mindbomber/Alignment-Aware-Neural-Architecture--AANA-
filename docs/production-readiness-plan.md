# AANA Production Readiness Plan

This plan converts the current AANA prototype into a production-capable platform without overstating what the repository can guarantee by itself. AANA remains a verifier-grounded correction architecture; production readiness means the platform has clear contracts, audited evidence flow, observable gates, secure integration boundaries, and repeatable release controls.

Current positioning: this repository can be demo-ready, pilot-ready, or production-candidate for controlled evaluation, but it is not production-certified by local tests alone. Production readiness requires live evidence connectors, domain owner signoff, audit retention, observability, human review path, security review, deployment manifest, incident response plan, and measured pilot results.

`production-certify` is a boundary checker, not a guarantee. It can show that repo-local artifacts are coherent, but deployment readiness requires explicit external evidence: live connector manifests, shadow-mode logs, an audit retention policy, observability, human review path and escalation policy, security review, deployment manifest, incident response plan, measured pilot results, and owner approval.

## Milestone 1: Stable Platform Contract

Status: complete for the local repository baseline.

Goal: make the integration boundary stable enough for apps, agents, and workflow tools.

Completion criteria:

- Versioned Workflow Contract request, batch request, result, and batch result schemas.
- Versioned Agent Event and Agent Check result schemas.
- Python SDK functions for single checks, file checks, and batch checks.
- CLI commands for validation, execution, schema printing, and example discovery.
- HTTP bridge routes for validation, single checks, batch checks, schemas, health, and OpenAPI.

Primary files:

- `aana/__init__.py`
- `eval_pipeline/workflow_contract.py`
- `eval_pipeline/agent_contract.py`
- `eval_pipeline/agent_api.py`
- `eval_pipeline/agent_server.py`
- `scripts/aana_cli.py`

## Milestone 2: Secure Local Integration Boundary

Status: complete for local bridge safeguards; production deployments still need host-level controls.

Goal: keep the bridge from acting like an unauthenticated, unbounded local action service.

Completion criteria:

- POST body limit with `413` rejection for oversized requests.
- Optional bearer token or `X-AANA-Token` requirement for POST routes.
- Environment-token support through `AANA_BRIDGE_TOKEN`.
- Documentation that the bridge should stay on `127.0.0.1` unless a deployment adds authentication, TLS, logging, and network controls.
- Unit tests for authorization and body-size behavior.

Operational defaults:

- Bind host: `127.0.0.1`
- Default max body: `1048576` bytes
- Token env var: `AANA_BRIDGE_TOKEN`

Example:

```powershell
$env:AANA_BRIDGE_TOKEN = "replace-with-a-secret"
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/aana-bridge.jsonl
```

Clients must then send:

```text
Authorization: Bearer replace-with-a-secret
```

or:

```text
X-AANA-Token: replace-with-a-secret
```

## Milestone 3: Adapter Productionization

Status: complete for repo-local adapter productionization. Executable adapters now declare production-readiness metadata, explicit per-adapter AIx beta/layer-weight/threshold tuning, verifier fallbacks, calibration notes, fixture coverage, audit requirements, and human-review escalation. External production approval still requires real domain owners and reviewed evidence integrations.

Goal: turn each domain adapter from a benchmark/demo checker into an owned production gate.

Completion criteria per adapter:

- Named domain owner.
- Explicit hard and soft constraints.
- Evidence source list with provenance requirements.
- Deterministic verifiers where possible.
- Model/verifier fallback rules where deterministic checks are insufficient.
- Calibration notes and known blind spots.
- Explicit `aix.risk_tier`, `aix.beta`, `aix.layer_weights`, and `aix.thresholds`, with stricter tuning for irreversible, regulated, or private-data workflows.
- Redacted fixture tests for pass, block, revise, ask, refuse, retrieve, and defer paths where applicable.
- Human-review escalation rules for high-impact failures.

Current local validator support:

- `aix.risk_tier`
- `aix.beta`
- `aix.layer_weights`
- `aix.thresholds`
- `production_readiness.status`
- `production_readiness.owner`
- `production_readiness.evidence_requirements`
- `production_readiness.verifier_fallbacks`
- `production_readiness.calibration_notes`
- `production_readiness.fixture_coverage`
- `production_readiness.escalation_policy`
- `production_readiness.audit_requirements`
- `production_readiness.human_review_escalation`
- `production_readiness.production_caveats`

Missing production-readiness metadata is a warning for prototype adapters and should be treated as a release blocker before consequential use.

AIx tuning report:

```powershell
python scripts/aana_cli.py aix-tuning
python scripts/aana_cli.py aix-tuning --json
```

The report lists each gallery adapter's declared risk tier, beta, layer weights, thresholds, and whether the numeric settings meet the tier minimums.

`release-check` enforces the same adapter tuning gate. A release fails when a gallery adapter is missing `aix.risk_tier`, `aix.beta`, `aix.layer_weights`, or `aix.thresholds`, or when the numeric values fall below the declared risk-tier minimums.

Current executable adapters:

- `travel_planning`
- `meal_planning`
- `support_reply`
- `research_summary`

## Milestone 4: Evidence and Retrieval Boundary

Status: complete for repo-local evidence-source authorization. The Workflow Contract accepts structured evidence objects, and the evidence registry validates approved sources, trust tiers, redaction status, freshness, and structured-evidence requirements. Live retrieval and external immutable evidence storage still depend on the deployment environment.

Goal: stop treating evidence as raw caller-provided text once AANA is used for consequential workflows.

Completion criteria:

- Evidence objects have source IDs, timestamps, trust tier, redaction status, and checked text.
- Retrieved evidence is immutable for the duration of a gate decision.
- The result records which evidence supported each accepted claim or action.
- Private data is minimized before entering event files, logs, or external tools.
- Source failures route to `retrieve`, `ask`, or `defer` instead of allowing unsupported acceptance.

Current local evidence object shape:

```json
{
  "source_id": "source-a",
  "retrieved_at": "2026-05-05T00:00:00Z",
  "trust_tier": "verified",
  "redaction_status": "redacted",
  "text": "Source A: AANA makes constraints explicit."
}
```

Simple evidence strings remain supported for demos and backward compatibility. Structured evidence objects are converted into bounded evidence summaries before agent checks.

Local evidence registry validation:

```powershell
python scripts/aana_cli.py validate-evidence-registry --evidence-registry examples/evidence_registry.json
python scripts/aana_cli.py evidence-integrations --evidence-registry examples/evidence_registry.json
python scripts/aana_cli.py evidence-integrations --evidence-registry examples/evidence_registry.json --mock-fixtures examples/evidence_mock_connector_fixtures.json
python scripts/aana_cli.py validate-workflow-evidence --workflow examples/workflow_research_summary_structured.json --evidence-registry examples/evidence_registry.json --require-structured
python scripts/aana_cli.py workflow-check --workflow examples/workflow_research_summary_structured.json --evidence-registry examples/evidence_registry.json --require-structured-evidence
```

Production evidence integration stubs define the connector boundary for CRM/support, ticketing, email, calendar, IAM, CI/GitHub, deployment/release, billing/payment, data export, workspace files, and security systems. These stubs intentionally do not call external systems; they define required source IDs, adapter coverage, authentication scopes, action/auth boundaries, redaction expectations, freshness SLOs, failure modes, and structured evidence templates. Hardened connector contracts now expose typed auth context, fetch request, result, and failure objects so production implementations can fail closed on missing auth, unknown source IDs, stale records, unredacted records, invalid shapes, and upstream outages. Mock connector fixtures cover CRM/support, email, calendar, IAM, CI/GitHub, deployment, billing, data export, and workspace files, proving that connector output can normalize into structured evidence objects accepted by the Workflow Contract validator. A real connector must implement retrieval, redaction, freshness checks, and audit logging before its evidence can be treated as production input.

Production preflight and release checks can include the evidence registry:

```powershell
python scripts/aana_cli.py production-preflight --deployment-manifest examples/production_deployment_template.json --evidence-registry examples/evidence_registry.json
python scripts/aana_cli.py release-check --deployment-manifest examples/production_deployment_template.json --governance-policy examples/human_governance_policy_template.json --evidence-registry examples/evidence_registry.json --audit-log eval_outputs/audit/aana-audit.jsonl
```

## Milestone 5: Gate Observability and Auditability

Status: complete for repo-local observability policy. The repository provides redacted audit-record helpers, audit summaries, audit-to-metrics export, and an observability policy validator for tracked gate, action, violation, latency, and AIx metrics, alert thresholds, drift-review cadence, and latency SLOs. Production log storage, dashboards, and alert execution still depend on the deployment environment.

Goal: make gate behavior inspectable across real traffic without leaking sensitive inputs.

Completion criteria:

- Structured audit records for request ID, adapter ID, gate decision, recommended action, violation codes, and input fingerprints.
- Redaction rules that exclude raw prompts, candidates, private records, evidence, safe responses, and outputs from default audit records.
- Aggregate dashboards for pass/block/fail rates, action distribution, AIx score and decision distribution, latency, and top violations.
- Drift reviews for rising block rates, falling correction success, and repeated unmapped violations.
- Exportable audit record for user-visible or human-review decisions.

Current local audit helpers:

- `eval_pipeline.agent_api.audit_event_check(event, result=None)`
- `eval_pipeline.agent_api.audit_workflow_check(workflow_request, result=None)`
- `eval_pipeline.agent_api.audit_workflow_batch(batch_request, result=None)`
- `aana.audit_event_check(...)`
- `aana.audit_workflow_check(...)`
- `aana.audit_workflow_batch(...)`

These helpers emit SHA-256 fingerprints and text lengths for sensitive fields instead of raw content. A production deployment should write these records to a reviewed audit sink and keep any raw artifacts in a separate access-controlled store only when policy requires it.

Local audit JSONL support:

```powershell
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py audit-validate --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py audit-summary --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/aana-metrics.json
python scripts/aana_cli.py audit-drift --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/aana-aix-drift.json
python scripts/aana_cli.py audit-manifest --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/manifests/aana-audit-integrity.json
python scripts/aana_cli.py audit-verify --manifest eval_outputs/audit/manifests/aana-audit-integrity.json
python scripts/aana_cli.py audit-reviewer-report --audit-log eval_outputs/audit/aana-audit.jsonl --metrics eval_outputs/audit/aana-metrics.json --drift-report eval_outputs/audit/aana-aix-drift.json --manifest eval_outputs/audit/manifests/aana-audit-integrity.json --output eval_outputs/audit/aana-reviewer-report.md
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/aana-bridge.jsonl
```

The CLI can append audit records for direct command-line checks. The HTTP bridge appends redacted audit records itself for successful `/agent-check`, `/workflow-check`, and `/workflow-batch` calls when `--audit-log` is set, so callers do not need to duplicate audit writes. The `audit-validate` command checks audit schema compatibility and rejects raw prompt, candidate, evidence, constraints, safe-response, and output fields. The `audit-metrics` command converts redacted audit JSONL into flat dashboard fields such as `gate_decision_count.pass`, `recommended_action_count.revise`, `violation_code_count.<code>`, `aix_score_average`, and `aix_decision_count.<decision>`. The `audit-drift` command turns those AIx metrics into a release-review drift report for low score, hard blockers, and unexpected AIx decisions. The `audit-manifest` command records the audit JSONL SHA-256, byte size, record count, summary, optional previous-manifest hash, and manifest self-hash; `audit-verify` recomputes those values to catch local tampering. The `audit-reviewer-report` command writes a Markdown handoff summarizing schema/redaction status, gate/action counts, AIx distribution, top violations, drift issues, and manifest hashes. The JSONL file, metrics export, drift report, reviewer report, and manifest are redacted handoff formats, not a complete production audit store. Production deployments still need retention policy, append-only storage, access controls, and review workflows.

The HTTP bridge also serves a local metrics dashboard at `GET /dashboard` and a redacted dashboard feed at `GET /dashboard/metrics`. The dashboard shows gate/action counts, violation trends, AIx average/min/max, hard blockers, adapter breakdowns, and shadow-mode would-block/would-intervene rates from the configured audit log. It is intended for pilot review and uses the same redacted audit records as the CLI metrics exporter.

Local observability policy validation:

```powershell
python scripts/aana_cli.py validate-observability --observability-policy examples/observability_policy.json
python scripts/aana_cli.py validate-observability --observability-policy examples/observability_policy_internal_pilot.json
python scripts/aana_cli.py release-check --deployment-manifest examples/production_deployment_template.json --governance-policy examples/human_governance_policy_template.json --evidence-registry examples/evidence_registry.json --observability-policy examples/observability_policy.json --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py release-check --deployment-manifest examples/production_deployment_internal_pilot.json --governance-policy examples/human_governance_policy_internal_pilot.json --evidence-registry examples/evidence_registry.json --observability-policy examples/observability_policy_internal_pilot.json --audit-log eval_outputs/audit/aana-internal-pilot.jsonl
```

The observability policies declare required metrics, including `aix_score_average`, `aix_decision_count`, `aix_hard_blocker_count`, `refusal_defer_rate`, `connector_failure_count`, and `evidence_freshness_failure_count`, plus alert thresholds, drift-review reports, ownership, and latency SLOs. The internal-pilot policy at `examples/observability_policy_internal_pilot.json` is the dashboard/alert/on-call source of truth: it declares concrete dashboard panels, alert coverage for high refusal/defer rate, connector failures, stale evidence, latency spikes, AIx drift, and hard-blocker spikes, plus primary and secondary on-call ownership. `release-check` always enforces adapter AIx tuning against declared risk tiers. When `release-check` receives `--audit-log`, it also exports audit metrics and fails release on low final AIx score, AIx hard blockers, or disallowed final AIx decisions such as `defer` or `refuse`. The internal pilot profile gives the single-node deployment concrete alert routes and drift reports; a real deployment must connect those declarations to the selected monitoring stack.

## Milestone 6: Evaluation and Release Gates

Status: complete for repo-local release gates. A production launch still requires reviewed deployment and governance manifests.

Goal: require evidence before widening platform use.

Completion criteria:

- `python scripts/dev.py check` passes before release.
- `python scripts/dev.py contract-freeze` validates frozen public contracts and compatibility fixtures before release.
- `python scripts/dev.py production-profiles` validates internal pilot production profiles, AIx tuning, evidence integration source coverage, and audit metrics export before release.
- Adapter gallery validation passes with runnable examples.
- Agent event examples pass expected gate behavior.
- Schema compatibility tests protect contract changes.
- Release notes include known caveats and benchmark limitations.
- Production rollout requires a reviewed evidence package, not only a passing unit test suite.
- Incident response plan validation passes for severity levels, rollback triggers, notification paths, audit review, and customer-impact review.

Local release gate:

```powershell
docker compose up --build
python scripts/dev.py contract-freeze
python scripts/dev.py pilot-certify
python scripts/dev.py production-profiles
python scripts/validation/validate_incident_response_plan.py
python scripts/dev.py production-profiles --audit-log eval_outputs/audit/ci/aana-ci-audit.jsonl --metrics-output eval_outputs/audit/ci/aana-ci-metrics.json --drift-output eval_outputs/audit/ci/aana-ci-aix-drift.json --reviewer-report-output eval_outputs/audit/ci/aana-ci-reviewer-report.md --manifest-output eval_outputs/audit/ci/manifests/aana-ci-audit-integrity.json
python scripts/aana_cli.py release-check
python scripts/aana_cli.py release-check --deployment-manifest path/to/your-production-deployment.json --governance-policy path/to/your-governance-policy.json --audit-log path/to/redacted-audit.jsonl
```

The CI workflow uses the stable `eval_outputs/audit/ci/` paths and uploads the redacted audit JSONL, metrics JSON, AIx drift JSON, integrity manifest, and Markdown reviewer report as the `aana-production-profile-audit-artifacts` artifact, so reviewers can inspect gate/action counts, adapter counts, AIx score distribution, AIx decisions, hard-blocker totals, drift status, and hashes without scraping logs.

Dockerized local runtime:

```powershell
docker compose up --build
Invoke-RestMethod http://localhost:8765/ready
```

The Docker bridge packages the HTTP server, adapter gallery, internal pilot profiles, web playground, local action demos, and a mounted redacted audit log path. See `docs/docker-http-bridge.md` for POST examples for `/agent-check`, `/workflow-check`, and `/workflow-batch`.

Copyable integration recipes are published in `docs/integration-recipes.md`. They cover GitHub Actions, local agents, CRM support drafts, deployment reviews, and shadow-mode pilots, each pointing to checked-in payloads and commands that produce a working result.

Web playground:

```powershell
python scripts/demos/run_playground.py
```

Open `http://localhost:8765/playground` to pick an adapter, edit the proposed answer or action, and inspect violations, AIx, safe response, and redacted audit preview.

Local desktop/browser demos:

```powershell
python scripts/demos/run_local_demos.py
```

Open `http://localhost:8765/demos` to test AANA around email send, file operation, calendar scheduling, purchase/booking, and research-grounding checks using synthetic evidence.

Shadow mode:

```powershell
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl --shadow-mode
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl --output eval_outputs/audit/shadow/aana-shadow-metrics.json
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl --shadow-mode
```

Shadow mode keeps production behavior unchanged while writing redacted telemetry for would-pass, would-revise, would-defer, and would-refuse decisions. Use it for early user evaluation before enforcing any adapter route.

Adapter Integration SDK:

```powershell
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --auth-token aana-local-dev-token --audit-log eval_outputs/audit/sdk/aana-sdk.jsonl --shadow-mode
$env:AANA_BRIDGE_TOKEN = "aana-local-dev-token"
python examples/sdk/python_client_example.py
```

The SDK adds `aana.AANAClient`, evidence normalization, Agent Event builders, Workflow Contract builders, and a mirrored TypeScript package under `sdk/typescript`. Use it when app teams need to call AANA from production or shadow-mode integrations without hand-building JSON.

Pilot surface certification:

```powershell
python scripts/aana_cli.py pilot-certify
python scripts/aana_cli.py pilot-certify --json
python scripts/dev.py pilot-certify
```

The certification command prints a public readiness score and fails if any repo-local pilot surface is missing its required gates for CLI, Python API, HTTP bridge, adapters, Agent Event Contract, Workflow Contract, skills/plugins, evidence, audit/metrics, docs, or contract freeze.

Production certification:

```powershell
python scripts/aana_cli.py production-certify --certification-policy examples/production_certification_template.json --deployment-manifest path/to/deployment.json --governance-policy path/to/governance.json --evidence-registry path/to/evidence_registry.json --observability-policy path/to/observability.json --audit-log path/to/redacted-shadow-audit.jsonl --external-evidence path/to/external-production-evidence.json
python scripts/aana_cli.py production-certify --json --certification-policy examples/production_certification_template.json --deployment-manifest path/to/deployment.json --governance-policy path/to/governance.json --evidence-registry path/to/evidence_registry.json --observability-policy path/to/observability.json --audit-log path/to/redacted-shadow-audit.jsonl --external-evidence path/to/external-production-evidence.json
```

Production boundary checking is intentionally stricter than pilot certification. It draws the line between repo-local readiness and deployment readiness by requiring at least 14 days of shadow mode, at least 100 redacted shadow audit records, required gate/action/violation/AIx/shadow/human-review metrics, human-review routing for high-impact, low-confidence, and irreversible decisions, connector evidence contracts, at least 365 days of immutable redacted audit retention, plus explicit external evidence for connector manifests, shadow-mode logs, audit retention policy, escalation policy, and owner approval. See `docs/production-certification.md`.

For quick command validation without recursively running the full test suite:

```powershell
python scripts/aana_cli.py release-check --skip-local-check
```

## Milestone 7: Deployment Hardening

Status: complete for repo-local deployment packaging and validation. External production still requires the selected cluster, ingress, certificate, secret manager, immutable audit sink, connector services, and owner approval.

Goal: run AANA in a controlled service environment.

Completion criteria:

- TLS termination, HTTPS-only ingress, and authenticated clients.
- Per-client edge rate limits, runtime rate limits, and request-size limits.
- Secret management outside source files and command history.
- `/health` liveness and `/ready` readiness checks.
- CPU and memory requests/limits.
- Non-root container runtime.
- Deployment rollback plan and last-known-good artifact.
- Dependency and container/image scanning if packaged as a service.
- Least-privilege access to evidence sources and downstream agent actions.

Local preflight command:

```powershell
python scripts/aana_cli.py production-preflight
python scripts/aana_cli.py production-preflight --json
python scripts/aana_cli.py production-preflight --deployment-manifest examples/production_deployment_template.json
```

The command checks repo-local readiness, then reports remaining external gates such as TLS, rate limits, immutable audit storage, evidence-source authorization, dashboards, domain-owner signoff, and human-review operations.

Deployment manifest validation:

```powershell
python scripts/aana_cli.py validate-deployment --deployment-manifest examples/production_deployment_template.json
python scripts/aana_cli.py validate-deployment --deployment-manifest examples/production_deployment_internal_pilot.json
python scripts/aana_cli.py validate-deployment --deployment-manifest path/to/your-production-deployment.json --json
```

The checked-in template is a concrete controlled deployment profile backed by `deploy/kubernetes/aana-bridge-production-template.yaml`. The Kubernetes template includes Secret, ConfigMap, PVC, Deployment, Service, HTTPS-only Ingress, `/health` and `/ready` probes, resource requests/limits, non-root runtime context, edge rate-limit annotations, and rollback command metadata. The `production_deployment_internal_pilot.json` profile is a more complete internal pilot environment for running the current gallery behind an internal TLS terminator with token auth, append-only redacted audit logs, rate limits, evidence-source authorization, observability, domain-owner signoff, human-review queues, and incident rollback path. Before external production use, replace internal queue names and example URLs with the real infrastructure, owners, and review routes for that environment. A launch manifest must declare:

- bridge authentication, TLS termination, request-size limit, and rate limits,
- container image, command, health/readiness probes, and resource limits,
- Kubernetes manifest, namespace, service, ingress, and rollback command,
- immutable audit sink, retention, redaction, and raw-artifact storage policy,
- authorized evidence sources with owners, freshness SLOs, and trust tiers,
- observability dashboard, alerts, and tracked gate/action/violation/AIx metrics,
- adapter domain owners and review status,
- human-review queue, triggers, and SLA,
- incident owner, channel, rollback trigger, rollback path, rollback steps, and last-known-good artifact.

Internal pilot smoke test:

```powershell
$env:AANA_BRIDGE_TOKEN = "replace-with-a-secret"
python scripts/dev.py pilot-bundle
python scripts/dev.py pilot-eval
python scripts/dev.py starter-kits
python scripts/pilots/run_e2e_pilot_bundle.py
python scripts/pilots/run_pilot_evaluation_kit.py
python scripts/pilots/run_starter_pilot_kit.py --kit all
python scripts/integrations/run_github_action_guardrails.py --force --fail-on never
python scripts/pilots/run_pilot_evaluation_kit.py --pack enterprise --report-output eval_outputs/pilot_eval/enterprise-report.md
python scripts/pilots/run_e2e_pilot_bundle.py --event support_reply --event research_summary --skip-production-profiles
python scripts/pilots/run_internal_pilot.py --audit-log eval_outputs/audit/aana-internal-pilot.jsonl
python scripts/pilots/run_internal_pilot.py --audit-log eval_outputs/audit/aana-internal-pilot.jsonl --metrics-output eval_outputs/audit/aana-internal-pilot-metrics.json
python scripts/pilots/pilot_smoke_test.py --audit-log eval_outputs/audit/aana-pilot-smoke.jsonl
python scripts/pilots/pilot_smoke_test.py --base-url http://127.0.0.1:8765 --audit-log eval_outputs/audit/aana-pilot-smoke.jsonl
```

The e2e pilot bundle is the broadest one-command local pilot path. It checks multiple agent events across adapters, writes redacted audit JSONL, exports audit metrics, writes an audit integrity manifest, runs `release-check` with internal pilot deployment/governance/evidence/observability profiles, and then runs `python scripts/dev.py production-profiles`. Use `--event` to narrow the bundle while debugging and `--skip-production-profiles` only when avoiding recursive validation inside focused tests.

The Pilot Evaluation Kit is the broader pre-real-data evaluation path. It runs named synthetic and public-data-rehearsal packs for enterprise, personal, civic/government, and public-data pilot planning; writes a redacted audit JSONL file, flat metrics JSON, JSON report, and Markdown report; and records operator workflow notes for each scenario. Use it before real-world testing to decide which adapters deserve shadow-mode pilots and which evidence connectors must be built first.

The Starter Pilot Kits are the fastest realistic no-private-data handoff path. They provide self-contained enterprise, personal productivity, and civic/government kit folders with synthetic records, adapter configuration, workflow examples, expected outcomes, and a one-command runner. The runner materializes Workflow Contract batch requests, appends redacted audit logs, exports metrics JSON, and writes pilot reports under `eval_outputs/starter_pilot_kits/`. Use these kits when a reviewer needs to understand AANA behavior from concrete workflow artifacts before a real evidence connector or shadow-mode deployment exists.

The Design Partner Pilots are the first field-evaluation package. They define four controlled pilots across enterprise support operations, developer tooling/release, personal productivity irreversible actions, and civic/government-style workflows. The runner writes redacted audit logs, metrics, dashboard payloads, AIx drift reports, audit manifests, reviewer reports, field-note templates, and structured feedback templates under `eval_outputs/design_partner_pilots/`. Use `python scripts/pilots/run_design_partner_pilots.py --pilot all` before scheduling partner sessions, then attach redacted `<pilot_id>.json` feedback files with `--feedback-dir` to collect real failure modes, friction points, and adoption blockers.

The Hosted Demo is the public no-clone option at `/demo/` on the project site. It is a static GitHub Pages surface backed by `docs/demo/scenarios.json`, uses only precomputed synthetic examples, accepts no secrets, and cannot send email, delete files, deploy releases, run migrations, submit payments, book purchases, or export private data. Use it for first-contact evaluation before asking someone to clone the repo, run Docker, or connect a local bridge.

The GitHub Action is the first team-facing CI integration. It packages the code review, deployment readiness, API contract change, infrastructure change, and database migration adapters behind a composite action at `.github/actions/aana-guardrails`. Teams can add one workflow step to PR/release jobs, feed in test output, deployment manifests, OpenAPI diffs, IaC plans, and migration evidence, and receive redacted audit logs, metrics JSON, a report JSON, and a Markdown job summary. Use `fail-on: candidate-block` for PR blocking mode or `fail-on: never` for advisory shadow mode.

The pilot runner sets up the runtime audit directory, starts the real bridge process with `--audit-log`, runs the smoke test against that live bridge, verifies that the bridge appended a redacted audit record, writes an audit integrity manifest under the runtime `manifests` directory, exports flat audit metrics beside the audit log by default, summarizes the audit log, and shuts the bridge down. Use `--metrics-output` when the metrics handoff file should live somewhere else. The smoke-test commands are lower-level checks: one starts an ephemeral local bridge using the same HTTP handler and audit path, and the other targets an already-running bridge. All verify unauthenticated POST rejection, authenticated event validation, authenticated agent checking, server-side redacted audit append, and audit summary generation. Use `--client-audit` only when intentionally testing a non-auditing bridge target.

## Milestone 8: Human Governance

Status: complete for repo-local policy validation. A real production program still needs accountable people, review queues, and incident operations.

Goal: make high-impact refusals, deferrals, and repeated corrections accountable.

Completion criteria:

- Escalation policy for medical, legal, financial, safety, private-data, and irreversible-action workflows.
- Review queue for decisions where verifier confidence is weak or evidence is missing.
- Periodic review of false accepts, false blocks, over-refusals, and user harm reports.
- Clear user-facing explanation patterns for `ask`, `defer`, and `refuse`.

Governance policy validation:

```powershell
python scripts/aana_cli.py validate-governance --governance-policy examples/human_governance_policy_template.json
python scripts/aana_cli.py validate-governance --governance-policy examples/human_governance_policy_internal_pilot.json
python scripts/aana_cli.py validate-governance --governance-policy path/to/your-governance-policy.json --json
```

The checked-in template is a concrete local governance profile. The `human_governance_policy_internal_pilot.json` profile adds pilot escalation classes for regulated decisions, irreversible actions, evidence failures, and gate-quality incidents. Before external production use, replace its role owners and review routes with the real accountable people, queues, and incident channels for that environment. A launch policy must declare:

- accountable governance owner and review cadence,
- escalation classes, triggers, routes, and allowed actions,
- user-facing explanation templates for `ask`, `defer`, and `refuse`,
- review metrics such as false accepts, false blocks, over-refusals, turnaround time, and repeated violations,
- incident owner, severity levels, rollback trigger, and notification path.

## Local Completion Summary

Completed in this repository:

- Production milestone list and release gates.
- Optional POST authorization for the local HTTP bridge.
- POST body-size limit for the local HTTP bridge.
- Tests for local bridge auth and request-size safeguards.
- Redacted audit-record helpers for agent, workflow, and workflow-batch checks.
- Tests proving audit records preserve decision metadata without storing raw checked text.
- HTTP bridge server-side audit append for successful agent, workflow, and workflow-batch gate checks.
- SHA-256 audit integrity manifests, verification, tamper-detection tests, and pilot-runner manifest and metrics generation.
- End-to-end pilot bundle that runs multiple agent events, redacted audit logging, metrics export, audit integrity manifest generation, release-check, and production-profile validation in one command.
- Pilot Evaluation Kit with enterprise, personal, civic/government, and public-data-rehearsal packs plus redacted audit logs, audit metrics, JSON reports, and Markdown reviewer reports.
- Contract Freeze gate for adapter JSON, Agent Event, Workflow, AIx, structured evidence, evidence registry, redacted audit record, audit metrics, and audit manifest schemas plus compatibility fixtures.
- CLI hardening for stable exit-code meanings, `cli-contract` command matrix output, structured JSON error responses, preflight input path validation, scaffold dry-run modes, command examples, and golden-output tests.
- Python runtime API hardening with typed public `eval_pipeline` exports, versioned `RuntimeResult` and `ValidationReport` dataclasses, predictable `AANAError` exception subclasses, typed `aana.*_typed` compatibility helpers, runtime API smoke tests, and public API reference docs.
- Agent Event Contract hardening for candidate field validation, structured evidence objects, source/freshness validation, allowed-action validation, route mismatch warnings, policy preset compatibility, schema route examples, and valid/invalid contract fixtures.
- Workflow Contract hardening for strict structured evidence mode, batch behavior guarantees, per-item runtime failure isolation, safe non-accept fallback on failed items, source-registry validation, and canonical adapter-family workflow examples.
- HTTP Bridge hardening with token-file rotation support, structured error payloads, `/ready` dependency checks, process-local POST rate limits, request body read timeouts, locked server-side audit appends, concurrent request tests, and deployment runbook guidance.
- Skills/plugins hardening with OpenClaw/Codex result-handling guidance, conformance tests for AIx and action-routing rules, runtime connector readiness and batch tools, high-risk workflow examples, and plugin install/use docs.
- Evidence Integration Stub hardening with machine-checkable auth scopes, freshness SLOs, redaction expectations, failure modes, normalized evidence helpers, public SDK helpers, CLI fixture checks, contract-freeze fixture validation, and mock connector fixtures/tests for CRM/support, email, calendar, IAM, CI, deployment, billing, and data export.
- Observability and Audit hardening with audit record schema validation, redaction checks, audit metrics compatibility validation, AIx drift reports, Markdown reviewer reports, contract-freeze drift fixture validation, and CI artifact generation for redacted audit JSONL, metrics, drift, manifest, and reviewer handoff files.
- Pilot Surface Certification with a one-command public readiness score and matrix for CLI, Python API, HTTP bridge, adapters, Agent Event Contract, Workflow Contract, skills/plugins, evidence, audit/metrics, docs, and contract freeze.
- Production Certification with an explicit demo/pilot/production boundary, shadow-mode duration and record-count requirements, required metrics, human-review routing, connector evidence, and audit-retention gates.
- Dockerized HTTP Bridge packaging with `docker compose up --build`, local token auth, mounted redacted audit logs, bundled internal pilot profiles, and endpoint examples for `/ready`, `/agent-check`, `/workflow-check`, and `/workflow-batch`.
- Web Playground for local adapter gallery demos with editable request/candidate fields, allowed-action fallback presets, verifier violations, AIx details, safe response, and redacted audit preview.
- Local Desktop/Browser Demos for email send, file operations, calendar scheduling, purchase/booking, and research grounding, backed by synthetic evidence templates, `GET /demos/scenarios`, and the same Workflow Contract/audit path as `/playground/check`.
- Starter Pilot Kits for enterprise, personal productivity, and civic/government packs with synthetic data, adapter config, workflow examples, expected outcomes, redacted audit logs, metrics reports, and Markdown pilot reports.
- Design Partner Pilots for 3 to 5 controlled field runs across enterprise, developer/tooling, personal productivity, and civic/government-style workflows, including redacted audit/metrics artifacts plus field-note and feedback templates for failure modes, friction points, and adoption blockers.
- Hosted Demo Option for public synthetic-only AANA examples on GitHub Pages with no secrets, no live backend, and no real sends/deletes/deploys/payments/exports.
- GitHub Action packaging for code review, deployment readiness, API contract change, infrastructure change, and database migration guardrails with one-step YAML integration and redacted CI artifacts.
- Structured Workflow Contract evidence objects with validation and agent-event conversion.
- Evidence registry template, validator, CLI checks, and workflow-check enforcement for structured evidence.
- Production evidence integration stubs for CRM/support, ticketing, email, calendar, IAM, CI/code review, deployment/release, billing/payment, data export, workspace files, and security evidence.
- Adapter validator checks for production-readiness metadata and fails malformed production-readiness blocks.
- Explicit per-adapter AIx risk tiers and tuning across the gallery, with stricter beta, layer weights, and action thresholds for high-risk adapters plus a CLI tuning report.
- Redacted audit JSONL append/load/summary helpers and CLI support.
- Audit-to-metrics exporter for flat gate, action, violation, adapter, record-type, and AIx dashboard fields.
- AIx calibration fixtures and tests covering clean high scores, hard-blocker accept caps, beta-scaled high-risk penalties, candidate repair improvement, and allowed-action fallback blocks.
- Observability policy template and validator for tracked gate/action/violation/AIx metrics, alert thresholds, drift review, and latency SLOs.
- Production preflight command that separates local readiness from external deployment gates.
- Production deployment manifest template and validator for infrastructure, evidence, audit, observability, ownership, and human-review gates.
- Human-governance policy template and validator for escalation, explanation, review metrics, and incident response.
- Release-check command that combines local checks, doctor, adapter AIx tuning enforcement, production preflight, governance validation, AIx audit enforcement, and release documentation presence.
- CI production-profile guard for adapter gallery examples, AIx tuning, internal pilot deployment/governance/observability profiles, evidence registry, evidence integration stubs, audit metrics artifact export, and release-check with a generated redacted audit log.
- Incident response plan artifact and validator for severity levels, rollback triggers, owner notification paths, audit review procedure, and customer-impact review.

Remaining production work depends on replacing templates with real deployment values, evidence sources, domain owners, review queues, incident channels, and monitoring stack.
