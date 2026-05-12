# AANA AIx Audit Enterprise Ops Pilot

## One-Page Overview

`AANA AIx Audit Enterprise Ops Pilot` is a controlled pilot package for evaluating AI systems before they are allowed to send customer communications, update tickets, export data, change access, approve code, deploy software, or publish incident updates.

The pilot uses AANA Runtime governance and AIx scoring to answer:

```text
Is this AI system ready for a controlled enterprise-operations pilot under the declared constraints?
```

The pilot is designed for enterprise operations teams, compliance leaders, security teams, engineering leaders, and domain owners who need evidence that AI actions are being checked before deployment or enforcement.

This is pilot-readiness evidence. It is not production certification.

## What The Pilot Evaluates

The V1 enterprise-ops pilot evaluates three operational surfaces:

- Support/customer communications: CRM support replies, email send guardrails, and ticket updates.
- Data/access controls: data export review and access permission changes.
- DevOps/release controls: code change review, deployment readiness, and incident response updates.

Each workflow is checked for:

- factual grounding and unsupported claims
- customer/privacy risk
- policy and permission constraints
- evidence quality and verifier integrity
- hard blockers
- recommended route: `accept`, `revise`, `retrieve`, `ask`, `defer`, or `refuse`
- AIx score and component scores across `P`, `B`, `C`, and `F`

## What The Buyer Receives

The pilot produces a complete local evidence packet:

- `enterprise-workflow-batch.json`: materialized Workflow Contract batch.
- `audit.jsonl`: redacted per-workflow audit records.
- `metrics.json`: dashboard-ready aggregate metrics.
- `enterprise-dashboard.json`: enterprise pilot dashboard payload.
- `aix-drift.json`: AIx drift and hard-blocker review.
- `audit-integrity.json`: SHA-256 integrity manifest.
- `reviewer-report.md`: operational audit reviewer handoff.
- `aix-report.json`: structured buyer-facing governance artifact.
- `aix-report.md`: human-readable AIx Report.

The audit artifacts do not store raw prompts, candidate outputs, private records, safe responses, secrets, or raw evidence text.

Customer onboarding templates are available in [`aana-aix-audit-customer-onboarding-templates.md`](aana-aix-audit-customer-onboarding-templates.md).

Connector setup requirements are available in [`enterprise-connector-readiness.md`](enterprise-connector-readiness.md).

The polished buyer demo for the first wedge is available in [`enterprise-support-demo-flow.md`](enterprise-support-demo-flow.md).

## What Pilot-Ready Means

`pilot_ready` or `pilot_ready_with_controls` means AANA has enough synthetic or shadow-mode evidence to support a controlled pilot under the stated scope.

For the current sample run:

```text
Recommendation: pilot_ready_with_controls
Workflow count: 8
Audit records: 8
Average AIx: 1.0
Minimum AIx: 1.0
Maximum AIx: 1.0
Hard blockers: 0
Shadow would-intervene: 8
```

`pilot_ready_with_controls` means the system should continue with human review, stronger evidence, or remediation before enforcement is expanded.

## What It Does Not Certify

The pilot does not certify production use.

Production approval still requires:

- live customer connectors
- domain-owner signoff
- immutable audit retention
- production observability
- human-review operations
- security review
- incident response process
- measured shadow-mode results on real traffic
- customer production go/no-go approval

## Sample AIx Report

Current sample output:

```text
AANA AIx Report: Enterprise Ops Pilot
Recommendation: pilot_ready_with_controls
Average AIx: 1.0
AIx decisions: accept = 8
Hard blockers: 0
Tested workflows: 8
```

Included use-case scope:

```text
Product bundle: enterprise_ops_pilot
Deployment context: enterprise_operations_pilot
Data basis: synthetic
Pilot surfaces:
- support_customer_communications
- data_access_controls
- devops_release_controls
```

The report includes:

- executive summary
- deployment recommendation
- overall AIx and component scores
- use-case scope
- tested workflows
- evidence quality
- verifier coverage
- calibration confidence
- failure modes
- remediation plan
- redacted evidence appendix
- human-review requirements
- monitoring plan
- limitations
- audit metadata

## Sample Dashboard JSON/Metrics

Excerpt from `enterprise-dashboard.json`:

```json
{
  "cards": {
    "pass": 8,
    "block_or_fail": 8,
    "fail": 0,
    "aix_average": 1.0,
    "aix_min": 1.0,
    "aix_max": 1.0,
    "hard_blockers": 0,
    "shadow_would_block": 0,
    "shadow_would_intervene": 8
  },
  "recommended_actions": {
    "revise": 8
  }
}
```

Surface breakdown:

```text
support_customer_communications: 3 workflows
data_access_controls: 2 workflows
devops_release_controls: 3 workflows
```

The dashboard data is generated from redacted audit metrics and can be connected to a customer monitoring stack during a shadow pilot.

## 30/60/90 Day Rollout Plan

### Days 1-30: Synthetic Pilot And Scope Lock

Goals:

- confirm buyer use case and risk boundary
- select enterprise-ops workflows
- run synthetic AIx audit
- review AIx Report and dashboard metrics
- identify required live connectors
- define human-review routes
- agree on shadow-mode success criteria

Outputs:

- scoped pilot plan
- synthetic AIx Report
- connector readiness checklist
- initial remediation plan
- human-review routing map

### Days 31-60: Shadow Mode With Customer Evidence

Goals:

- connect approved evidence sources
- run AANA in shadow mode
- sample real AI actions without blocking users
- measure would-revise, would-defer, and would-refuse rates
- review evidence gaps and recurring violation codes
- validate audit redaction and integrity controls

Outputs:

- shadow-mode AIx Report
- redacted audit logs
- dashboard metrics
- AIx drift report
- evidence quality review
- updated remediation plan

### Days 61-90: Controlled Enforcement Decision

Goals:

- resolve high-priority evidence gaps
- validate human-review operations
- confirm security and governance signoff
- choose limited enforcement surfaces
- define rollback and incident response path
- prepare customer go/no-go decision

Outputs:

- final pilot report
- enforcement readiness recommendation
- domain-owner signoff packet
- incident response checklist
- monitoring plan
- production certification gap list

## Buyer Decision

At the end of the pilot, the buyer should be able to decide one of four outcomes:

- expand shadow mode
- enforce limited low-risk surfaces
- remediate before enforcement
- stop or redesign the deployment

The AIx Report supports that decision with redacted evidence, score summaries, failure modes, and governance recommendations.
