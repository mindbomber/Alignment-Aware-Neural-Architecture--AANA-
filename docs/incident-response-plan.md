# AANA Support Incident Response Plan

The executable incident-response source of truth is `examples/incident_response_plan_internal_pilot.json`. Validate it with:

```powershell
python scripts/validation/validate_incident_response_plan.py
```

The plan is for the internal-pilot support runtime. It keeps the production boundary conservative: this repo can be pilot-ready or production-candidate, but production readiness still depends on the real deployment environment, live connectors, owner approval, audit retention, observability, human review staffing, and measured pilot evidence.

## Severity Levels

- `sev0`: confirmed unsafe accept, private-data exposure, unauthorized irreversible action, auth bypass, or audit leakage. Rollback, audit review, and customer-impact review are required.
- `sev1`: likely unsafe accept, repeated high-risk false accepts, email-send fail-open behavior, connector permission incident, or hard-blocker spike with user-impact risk. Rollback is expected unless the incident commander documents why containment is stronger.
- `sev2`: elevated false blocks, over-refusal, stale evidence, connector failures, high latency, or human-review backlog. Audit and customer-impact review are required.
- `sev3`: documentation, dashboard, or isolated advisory-mode issue without unsafe acceptance.

## Rollback Triggers

Rollback or enforcement downgrade is required for:

- critical false accept,
- audit or log leakage of raw support data,
- auth bypass or connector permission incident,
- bridge unavailability that could affect irreversible actions,
- sustained quality regression after a runtime, adapter, route-map, connector, or AIx tuning change.

The default rollback command is:

```powershell
kubectl rollout undo deployment/aana-bridge -n aana-runtime
```

For support incidents, first switch affected adapters to shadow or advisory mode, then roll back the bridge or adapter version, verify `/health` and `/ready`, and rerun release gates before restoring enforcement.

## Notification Paths

The plan requires notification coverage for `sev0`, `sev1`, and `sev2` across:

- AANA Platform On-Call,
- Support Operations Domain Owner,
- Security Operations Reviewer and Privacy Review Owner,
- AANA Audit Reviewers.

## Audit Review

Audit review starts from metadata-only artifacts: redacted audit JSONL, integrity manifest, metrics, AIx drift report, affected workflow IDs, adapter IDs, violation codes, hard blockers, recommended actions, human review routes, connector source IDs, and freshness metadata.

The incident record must not copy raw customer messages, raw candidates, full CRM records, payment data, internal notes, attachment bodies, secrets, or tokens.

## Customer Impact

Customer-impact review is required for `sev0`, `sev1`, and `sev2`. It determines whether any customer-visible reply or irreversible support action included invented facts, private data, unsupported refund/billing statements, internal CRM notes, verification bypass, or unsafe email/ticket behavior. Remediation can include correction, retraction, human-reviewed follow-up, privacy/security escalation, adapter enforcement freeze, and verifier or connector updates.
