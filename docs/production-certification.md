# AANA Production Certification

Production certification is the line between trying AANA and letting AANA enforce decisions in front of real user or business actions. The `production-certify` command is a boundary checker, not a guarantee: it separates repo-local readiness from deployment readiness and reports whether required evidence exists for a production-readiness review.

This repository is demo-ready and pilot-ready for controlled evaluation, but it is not production-certified by itself. Production readiness requires live evidence connectors, domain owner signoff, audit retention, observability, and human review paths.

Run the certification command with real operating artifacts:

```powershell
python scripts/aana_cli.py production-certify `
  --certification-policy examples/production_certification_template.json `
  --deployment-manifest path/to/deployment.json `
  --governance-policy path/to/governance.json `
  --evidence-registry path/to/evidence_registry.json `
  --observability-policy path/to/observability.json `
  --audit-log path/to/redacted-shadow-audit.jsonl `
  --external-evidence path/to/external-production-evidence.json
```

Use `--json` for automation:

```powershell
python scripts/aana_cli.py production-certify --json `
  --certification-policy examples/production_certification_template.json `
  --deployment-manifest path/to/deployment.json `
  --governance-policy path/to/governance.json `
  --evidence-registry path/to/evidence_registry.json `
  --observability-policy path/to/observability.json `
  --audit-log path/to/redacted-shadow-audit.jsonl `
  --external-evidence path/to/external-production-evidence.json
```

The command reports two boundaries:

- `repo_local_ready`: local contracts, manifests, registry coverage, governance policy, observability policy, and redacted shadow-mode audit shape pass.
- `deployment_ready`: repo-local readiness passes and an explicit external evidence manifest is supplied.

The command still sets `production_certified` to `false`; final certification remains an external domain owner, security, and governance decision. Passing local examples, `release-check`, or a synthetic shadow audit does not certify production.

The command fails deployment readiness unless it receives explicit external evidence for production claims:

- connector manifests
- shadow-mode logs
- audit retention policy
- escalation policy
- owner approval

Use [`examples/external_production_evidence_template.json`](../examples/external_production_evidence_template.json) only as a shape template. It intentionally uses `evidence_scope: template`; a real deployment manifest must use `evidence_scope: external_deployment` and point to environment-owned artifacts.

## Readiness Levels

| Level | Data | Side effects | Certification line |
|---|---|---|---|
| Demo | Synthetic-only examples | None | Public understanding only. No live connectors, secrets, or irreversible actions. |
| Pilot | Synthetic, public, or tightly scoped redacted data | Shadow or advisory mode preferred | Measures value and friction without broad production enforcement. |
| Production | Authorized production evidence | Enforcement may block or route live workflows | Requires shadow evidence, metrics, human review, connector evidence, and audit retention. |

Demo-ready and pilot-ready do not imply production certification. Production boundary checks are intentionally stricter than `pilot-certify`, `release-check`, or local tests, because those checks cannot prove live connector freshness, domain owner approval, retained audit evidence, deployed observability, or human review operations.

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
- `production-certify` requires all repo-local artifacts plus explicit external evidence and draws the repo-local/deployment boundary; it does not guarantee production safety by itself.
