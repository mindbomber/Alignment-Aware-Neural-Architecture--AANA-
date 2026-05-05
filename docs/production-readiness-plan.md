# AANA Production Readiness Plan

This plan converts the current AANA prototype into a production-capable platform without overstating what the repository can guarantee by itself. AANA remains a verifier-grounded correction architecture; production readiness means the platform has clear contracts, audited evidence flow, observable gates, secure integration boundaries, and repeatable release controls.

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
python scripts/aana_server.py --host 127.0.0.1 --port 8765
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

Status: complete for repo-local adapter productionization. Executable adapters now declare production-readiness metadata, verifier fallbacks, calibration notes, fixture coverage, audit requirements, and human-review escalation. External production approval still requires real domain owners and reviewed evidence integrations.

Goal: turn each domain adapter from a benchmark/demo checker into an owned production gate.

Completion criteria per adapter:

- Named domain owner.
- Explicit hard and soft constraints.
- Evidence source list with provenance requirements.
- Deterministic verifiers where possible.
- Model/verifier fallback rules where deterministic checks are insufficient.
- Calibration notes and known blind spots.
- Redacted fixture tests for pass, block, revise, ask, refuse, retrieve, and defer paths where applicable.
- Human-review escalation rules for high-impact failures.

Current local validator support:

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
python scripts/aana_cli.py validate-workflow-evidence --workflow examples/workflow_research_summary_structured.json --evidence-registry examples/evidence_registry.json --require-structured
python scripts/aana_cli.py workflow-check --workflow examples/workflow_research_summary_structured.json --evidence-registry examples/evidence_registry.json --require-structured-evidence
```

Production preflight and release checks can include the evidence registry:

```powershell
python scripts/aana_cli.py production-preflight --deployment-manifest examples/production_deployment_template.json --evidence-registry examples/evidence_registry.json
python scripts/aana_cli.py release-check --deployment-manifest examples/production_deployment_template.json --governance-policy examples/human_governance_policy_template.json --evidence-registry examples/evidence_registry.json
```

## Milestone 5: Gate Observability and Auditability

Status: complete for repo-local observability policy. The repository provides redacted audit-record helpers, audit summaries, and an observability policy validator for tracked metrics, alert thresholds, drift-review cadence, and latency SLOs. Production log storage, dashboards, and alert execution still depend on the deployment environment.

Goal: make gate behavior inspectable across real traffic without leaking sensitive inputs.

Completion criteria:

- Structured audit records for request ID, adapter ID, gate decision, recommended action, violation codes, and input fingerprints.
- Redaction rules that exclude raw prompts, candidates, private records, evidence, safe responses, and outputs from default audit records.
- Aggregate dashboards for pass/block/fail rates, action distribution, latency, and top violations.
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
python scripts/aana_cli.py audit-summary --audit-log eval_outputs/audit/aana-audit.jsonl
```

The JSONL file is a redacted handoff format, not a complete production audit store. Production deployments still need retention policy, write integrity, access controls, and review workflows.

Local observability policy validation:

```powershell
python scripts/aana_cli.py validate-observability --observability-policy examples/observability_policy.json
python scripts/aana_cli.py release-check --deployment-manifest examples/production_deployment_template.json --governance-policy examples/human_governance_policy_template.json --evidence-registry examples/evidence_registry.json --observability-policy examples/observability_policy.json
```

The observability policy declares required metrics, alert thresholds, drift-review reports, ownership, and latency SLOs. A real deployment must connect those declarations to the selected monitoring stack.

## Milestone 6: Evaluation and Release Gates

Status: complete for repo-local release gates. A production launch still requires reviewed deployment and governance manifests.

Goal: require evidence before widening platform use.

Completion criteria:

- `python scripts/dev.py check` passes before release.
- Adapter gallery validation passes with runnable examples.
- Agent event examples pass expected gate behavior.
- Schema compatibility tests protect contract changes.
- Release notes include known caveats and benchmark limitations.
- Production rollout requires a reviewed evidence package, not only a passing unit test suite.

Local release gate:

```powershell
python scripts/aana_cli.py release-check
python scripts/aana_cli.py release-check --deployment-manifest path/to/your-production-deployment.json --governance-policy path/to/your-governance-policy.json
```

For quick command validation without recursively running the full test suite:

```powershell
python scripts/aana_cli.py release-check --skip-local-check
```

## Milestone 7: Deployment Hardening

Status: outside this repo until a target deployment is chosen. The local `production-preflight` command lists these gates so they are not lost during release preparation.

Goal: run AANA in a controlled service environment.

Completion criteria:

- TLS termination and authenticated clients.
- Per-client rate limits and request-size limits.
- Secret management outside source files and command history.
- Health checks and graceful shutdown.
- Deployment rollback plan.
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
python scripts/aana_cli.py validate-deployment --deployment-manifest path/to/your-production-deployment.json --json
```

The checked-in example is a concrete local controlled deployment profile. Before external production use, replace its local fixtures with the real infrastructure, owners, and review queues for that environment. A launch manifest must declare:

- bridge authentication, TLS termination, request-size limit, and rate limits,
- immutable audit sink, retention, redaction, and raw-artifact storage policy,
- authorized evidence sources with owners, freshness SLOs, and trust tiers,
- observability dashboard, alerts, and tracked metrics,
- adapter domain owners and review status,
- human-review queue, triggers, and SLA.

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
python scripts/aana_cli.py validate-governance --governance-policy path/to/your-governance-policy.json --json
```

The checked-in example is a concrete local governance profile. Before external production use, replace its local ownership and review routes with the real accountable people, queues, and incident channels for that environment. A launch policy must declare:

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
- Structured Workflow Contract evidence objects with validation and agent-event conversion.
- Evidence registry template, validator, CLI checks, and workflow-check enforcement for structured evidence.
- Adapter validator checks for production-readiness metadata and fails malformed production-readiness blocks.
- Redacted audit JSONL append/load/summary helpers and CLI support.
- Observability policy template and validator for tracked metrics, alert thresholds, drift review, and latency SLOs.
- Production preflight command that separates local readiness from external deployment gates.
- Production deployment manifest template and validator for infrastructure, evidence, audit, observability, ownership, and human-review gates.
- Human-governance policy template and validator for escalation, explanation, review metrics, and incident response.
- Release-check command that combines local checks, doctor, production preflight, governance validation, and release documentation presence.

Remaining production work depends on replacing templates with real deployment values, evidence sources, domain owners, review queues, incident channels, and monitoring stack.
