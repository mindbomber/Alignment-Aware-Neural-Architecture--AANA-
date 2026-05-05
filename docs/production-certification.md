# AANA Production Certification

Production certification is the line between trying AANA and letting AANA enforce decisions in front of real user or business actions.

Run the certification command with real operating artifacts:

```powershell
python scripts/aana_cli.py production-certify `
  --certification-policy examples/production_certification_template.json `
  --deployment-manifest path/to/deployment.json `
  --governance-policy path/to/governance.json `
  --evidence-registry path/to/evidence_registry.json `
  --observability-policy path/to/observability.json `
  --audit-log path/to/redacted-shadow-audit.jsonl
```

Use `--json` for automation:

```powershell
python scripts/aana_cli.py production-certify --json `
  --certification-policy examples/production_certification_template.json `
  --deployment-manifest path/to/deployment.json `
  --governance-policy path/to/governance.json `
  --evidence-registry path/to/evidence_registry.json `
  --observability-policy path/to/observability.json `
  --audit-log path/to/redacted-shadow-audit.jsonl
```

The command fails unless the deployment has a valid certification policy, production deployment manifest, governance policy, observability policy, evidence registry, and redacted shadow-mode audit log.

## Readiness Levels

| Level | Data | Side effects | Certification line |
|---|---|---|---|
| Demo | Synthetic-only examples | None | Public understanding only. No live connectors, secrets, or irreversible actions. |
| Pilot | Synthetic, public, or tightly scoped redacted data | Shadow or advisory mode preferred | Measures value and friction without broad production enforcement. |
| Production | Authorized production evidence | Enforcement may block or route live workflows | Requires shadow evidence, metrics, human review, connector evidence, and audit retention. |

Demo-ready and pilot-ready do not imply production-ready. Production certification is intentionally stricter than `pilot-certify` or `release-check`.

## Required Gates

Production certification requires:

- Shadow mode for at least 14 days.
- At least 100 redacted shadow-mode audit records.
- Required metrics in the observability policy:
  `gate_decision_count`, `recommended_action_count`, `violation_code_count`, `adapter_error_count`, `latency`, `aix_score_average`, `aix_decision_count`, `aix_hard_blocker_count`, `false_accept_rate`, `false_block_rate`, `over_refusal_rate`, `human_review_turnaround_time`, `shadow_records_total`, and `shadow_would_action_count`.
- Human-review routing for high-impact, low-confidence, and irreversible decisions.
- Connector evidence contracts for auth boundary, freshness SLO, redaction, and failure modes.
- Audit retention for at least 365 days, with immutable or append-only storage and redaction required.
- Domain owner, security, and governance signoff.

## Shadow Mode Evidence

The audit log must be redacted JSONL generated from shadow-mode checks. Shadow mode means AANA observes proposed actions and records what it would have done, while production behavior remains unchanged.

Required audit properties:

- `execution_mode` is `shadow`.
- `shadow_observation.enforcement` is `observe_only`.
- Raw prompts, candidates, evidence, safe responses, and outputs are absent.
- AIx score, decision, hard blockers, gate decision, recommended action, adapter, and violation codes are present where available.

The shadow audit must span the required duration. A single burst of test records does not certify production behavior.

## Production Inputs

Use the checked-in templates only as shape examples:

- `examples/production_certification_template.json`
- `examples/production_deployment_template.json`
- `examples/human_governance_policy_template.json`
- `examples/observability_policy.json`
- `examples/evidence_registry.json`

Before production, replace owners, routes, evidence sources, audit sink, dashboard, and incident paths with real environment values.

## Relationship To Other Commands

- `pilot-certify` checks whether a local evaluator can try AANA through public surfaces.
- `release-check` checks repo-local release readiness and optional AIx audit enforcement.
- `production-preflight` lists deployment gates and validates selected manifests.
- `production-certify` requires all production artifacts plus shadow-mode evidence and draws the final demo/pilot/production boundary.
