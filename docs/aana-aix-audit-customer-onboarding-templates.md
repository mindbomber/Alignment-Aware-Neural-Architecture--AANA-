# AANA AIx Audit Customer Onboarding Templates

Use these templates during enterprise-ops pilot onboarding. They are designed to gather enough customer context to run `AANA AIx Audit` in synthetic mode first, then shadow mode with approved live connectors.

These templates support pilot readiness only. They do not create production certification without customer governance approval, live evidence, security review, observability, human-review operations, incident response, and measured shadow-mode results.

For concrete connector setup requirements, use [`enterprise-connector-readiness.md`](enterprise-connector-readiness.md) together with these templates.

## 1. Use-Case Intake

Customer:

Pilot owner:

Domain owner:

Security/compliance contact:

Target pilot dates:

AI system name:

AI system owner:

Primary user groups:

End users or affected parties:

Pilot surface:

- [ ] Support/customer communications
- [ ] Data/access controls
- [ ] DevOps/release controls
- [ ] Other:

Proposed AI actions:

- [ ] Draft customer response
- [ ] Send email
- [ ] Update ticket
- [ ] Export data
- [ ] Change access
- [ ] Review code
- [ ] Approve deployment
- [ ] Publish incident update
- [ ] Other:

Decision influence:

- What can the AI system decide, recommend, or trigger?
- What human steps currently exist before action?
- What systems or records can the AI see?
- What systems or tools can the AI affect?

Failure impact:

- What happens if the AI output is wrong?
- What happens if the AI leaks private data?
- What happens if the AI takes or recommends an unauthorized action?
- What happens if the AI refuses or defers too often?

Pilot objective:

- [ ] Evaluate readiness before deployment
- [ ] Run shadow-mode monitoring
- [ ] Compare adapters or policies
- [ ] Prepare limited enforcement decision
- [ ] Produce audit evidence for internal review

Success definition:

Constraints and exclusions:

Open questions:

## 2. System Inventory

AI application:

Model/provider:

Model version or deployment ID:

Prompt or agent framework:

Runtime environment:

Deployment owner:

Data handled:

- [ ] Public
- [ ] Internal
- [ ] Confidential
- [ ] Personal data/PII
- [ ] Financial data
- [ ] Health data
- [ ] Legal or regulated data
- [ ] Source code/secrets

Connected systems:

| System | Purpose | Data type | Read/write | Owner | Pilot access approved |
| --- | --- | --- | --- | --- | --- |
| CRM/support | | | | | |
| Ticketing | | | | | |
| Email | | | | | |
| IAM/access | | | | | |
| CI/code review | | | | | |
| Deployment/release | | | | | |
| Data warehouse/export | | | | | |

Current controls:

- Authentication:
- Authorization:
- Logging:
- Human review:
- Monitoring:
- Incident response:
- Data retention:

Known system limitations:

## 3. Connector Checklist

Connector readiness status:

| Connector | Required for pilot | Access mode | Redaction available | Freshness SLA | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- |
| CRM/support | Yes/No | Read/Write/None | Yes/No | | | |
| Ticketing | Yes/No | Read/Write/None | Yes/No | | | |
| Email send | Yes/No | Read/Write/None | Yes/No | | | |
| IAM/access | Yes/No | Read/Write/None | Yes/No | | | |
| CI/code review | Yes/No | Read/Write/None | Yes/No | | | |
| Deployment/release | Yes/No | Read/Write/None | Yes/No | | | |
| Data export | Yes/No | Read/Write/None | Yes/No | | | |

For each connector, confirm:

- [ ] Source system owner approved pilot use.
- [ ] Read scope is least-privilege.
- [ ] Write scope is disabled during shadow mode.
- [ ] Secrets are stored outside logs and reports.
- [ ] Evidence objects include source ID and retrieval timestamp.
- [ ] Evidence objects include trust tier.
- [ ] Evidence objects include redaction status.
- [ ] Connector failure mode is defined.
- [ ] Freshness failure mode is defined.
- [ ] Private/raw records are not written to AANA audit logs.

Connector blockers:

Fallback plan if connector is unavailable:

## 4. Risk-Tier Questionnaire

Recommended tier:

- [ ] `standard`: low-risk internal assistant
- [ ] `elevated`: customer-facing recommendations or operational workflow support
- [ ] `high`: material business, security, access, employment, finance, insurance, legal, or customer-impacting decision support
- [ ] `strict`: irreversible, rights-impacting, safety-critical, highly regulated, or external action-capable workflows

Risk questions:

| Question | Yes/No | Notes |
| --- | --- | --- |
| Can the AI action affect a customer, employee, citizen, or vendor? | | |
| Can the AI expose private, confidential, or regulated data? | | |
| Can the AI send, publish, export, delete, merge, deploy, buy, book, or change permissions? | | |
| Can the action be difficult or impossible to undo? | | |
| Does the workflow involve legal, healthcare, finance, employment, insurance, security, or public-sector obligations? | | |
| Does the workflow require policy, contract, law, source, or approval evidence? | | |
| Would an incorrect output require customer notification, incident response, or regulatory review? | | |

AIx tuning expectation:

- Risk tier:
- Beta:
- Layer weights:
- Accept threshold:
- Revise threshold:
- Defer/refuse threshold:

Required hard blockers:

Human review required when:

## 5. Domain-Owner Signoff

Domain:

Domain owner:

Review date:

Pilot scope approved:

- [ ] Yes
- [ ] No
- [ ] Approved with conditions

Approved pilot surfaces:

- [ ] Support/customer communications
- [ ] Data/access controls
- [ ] DevOps/release controls

Approved data sources:

Approved actions in shadow mode:

Actions excluded from pilot:

Required human-review conditions:

Required evidence sources:

Known policy constraints:

Success criteria:

Required remediation before enforcement:

Signoff:

```text
I approve the above scope for AANA AIx Audit pilot evaluation. This approval does not certify production enforcement.

Name:
Role:
Date:
Conditions:
```

## 6. Human-Review Routing

Review queues:

| Route | Queue owner | SLA | Required for | Escalation path |
| --- | --- | --- | --- | --- |
| `ask` | | | missing information or user confirmation | |
| `defer` | | | domain-owner or stronger-evidence review | |
| `refuse` | | | unsafe or prohibited action review | |
| security review | | | access, secrets, deployment, incident, data risk | |
| compliance review | | | regulated or policy-sensitive workflows | |

Routing rules:

- `accept`: action may proceed only within checked scope.
- `revise`: revise output/action and recheck before execution.
- `retrieve`: fetch missing evidence and recheck before execution.
- `ask`: ask for missing information, authorization, or confirmation.
- `defer`: route to human/domain-owner review.
- `refuse`: stop unsafe action.

Human-review packet requirements:

- [ ] Workflow ID
- [ ] Adapter ID
- [ ] Recommended action
- [ ] AIx score and decision
- [ ] Hard blockers
- [ ] Violation codes
- [ ] Evidence source IDs
- [ ] Input fingerprints
- [ ] No raw private content

Override policy:

Appeal or dispute path:

Reviewer training needed:

## 7. Shadow-Mode Success Criteria

Shadow-mode period:

Minimum records:

Minimum days:

Included workflows:

Excluded workflows:

Success thresholds:

| Metric | Target | Actual | Pass/Fail |
| --- | --- | --- | --- |
| Redacted audit record validity | 100% | | |
| Raw payload leakage | 0 | | |
| Connector failure rate | | | |
| Evidence freshness failure rate | | | |
| AIx average score | | | |
| AIx minimum score | | | |
| Hard blocker count | 0 for direct accept | | |
| Would-revise rate | | | |
| Would-defer rate | | | |
| Would-refuse rate | | | |
| Human-review SLA met | | | |
| False accept rate after review | | | |
| False block/over-refusal rate after review | | | |

Sampling plan:

Review cadence:

Go/no-go criteria:

- [ ] Continue shadow mode
- [ ] Expand pilot scope
- [ ] Enable limited enforcement
- [ ] Remediate before enforcement
- [ ] Stop or redesign workflow

## 8. Incident Response Plan

Incident owner:

Security owner:

Domain owner:

Communications owner:

Severity levels:

| Severity | Definition | Response time | Owner |
| --- | --- | --- | --- |
| SEV-1 | Unsafe action executed, private data leak, unauthorized access/export/deployment, or customer/regulatory impact | | |
| SEV-2 | Unsafe recommendation caught before execution, repeated hard blockers, major connector failure, or high false-accept risk | | |
| SEV-3 | Increased defer/refuse rate, evidence freshness degradation, dashboard alert, or review backlog | | |
| SEV-4 | Documentation, fixture, or non-user-impacting pilot issue | | |

Trigger conditions:

- [ ] Raw prompt, candidate, evidence text, private record, secret, or output appears in audit/report artifact.
- [ ] AANA recommends `accept` despite a hard blocker.
- [ ] Runtime executes action when route is not `accept`.
- [ ] Connector returns unauthorized or stale evidence.
- [ ] AIx score distribution drifts below agreed threshold.
- [ ] Human-review queue exceeds SLA.
- [ ] Buyer reports unsafe output or action.

Immediate actions:

1. Pause affected enforcement route.
2. Preserve redacted audit records and integrity manifest.
3. Disable or restrict affected connector.
4. Notify incident owner, domain owner, security, and compliance.
5. Review affected workflow IDs, adapter IDs, violation codes, and fingerprints.
6. Decide whether customer/user notification is required.
7. Document remediation and recheck before resuming.

Rollback plan:

Evidence to collect:

- Audit log path:
- Integrity manifest:
- Dashboard snapshot:
- AIx drift report:
- Connector status:
- Human-review queue state:
- Deployment/config version:

Post-incident review:

- Root cause:
- Missed control:
- Corrective action:
- Preventive action:
- Owner:
- Due date:

Resume criteria:

- [ ] Root cause understood.
- [ ] Remediation implemented.
- [ ] Tests or fixtures added.
- [ ] Domain owner approves resume.
- [ ] Security/compliance approves resume when required.
- [ ] Shadow-mode verification passes.
