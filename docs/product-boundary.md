# Product Boundary

Canonical entry point: [Integrate Runtime](integrate-runtime/index.md)

AANA is a runtime guardrail layer for agentic workflows. It sits between an agent and consequential outputs or actions. It receives a Workflow Contract request or Agent Event, checks the candidate output or action against adapter-specific constraints, applies verifier-grounded correction policy, returns one of `accept`, `revise`, `retrieve`, `ask`, `defer`, or `refuse`, and emits audit-safe metadata.

AANA is not the base agent, the CRM, the ticketing system, the email sender, or the system of record. It is the decision and correction boundary that decides whether the agent's proposed output/action can proceed, must be revised, needs more evidence, needs clarification, must be escalated, or must be blocked.

## Primary Runtime Boundary

Public integrations should use one of two contracts:

- **Workflow Contract**: app and workflow checks that pass an adapter, request, candidate, evidence, and constraints.
- **Agent Event Contract**: agent action checks before an agent sends, publishes, exports, deletes, deploys, books, buys, changes permissions, or exposes private data.

The runtime returns:

- `gate_decision`
- `recommended_action`
- `violations`
- `constraint_results`
- `aix`
- `candidate_aix`
- `audit_summary`
- safe output or safe response text when a correction is available

Lower-level adapter runner modules, verifier modules, repair functions, route maps, and result assembly helpers are implementation details.

## First Deployable Support Boundary

The first deployable product vertical is support workflows. The support boundary is intentionally narrow: AANA checks drafts and planned support communications before they become customer-visible or irreversible.

Initial support adapters:

- **Draft support reply guardrail**: checks customer-facing support drafts for invented account facts, unsupported policy promises, private data, unsafe tone, and missing verification routes.
- **CRM support reply guardrail**: checks drafts that reference CRM context, with stricter handling for internal notes, fraud/risk flags, agent-only details, and private account data.
- **Refund/account fact boundary checker**: checks whether refund eligibility, order IDs, account state, payment timing, and customer-specific promises are grounded in verified account evidence.
- **Email-send guardrail for support communications**: checks recipients, broad/BCC delivery, attachments, sensitive data, irreversible send approval, and content drift before send or schedule-send.
- **Ticket/customer-visible update checker**: checks public ticket updates for verified status, unsupported commitments, unsafe wording, internal/private data, and support-policy bypasses.
- **Invoice/billing reply checker**: adjacent later adapter for billing balances, credits, tax claims, payment data, and invoice-specific escalation.

## Support Actions

Support adapters should route to the standard AANA actions:

- `accept`: the candidate is safe to use within the approved scope.
- `revise`: the candidate can be corrected into a safe draft.
- `retrieve`: required account, ticket, policy, or evidence data is missing and may be available.
- `ask`: the user or agent must provide missing verification, recipient, request scope, or approval.
- `defer`: a stronger support, billing, privacy, legal, or human-review path is required.
- `refuse`: the proposed output/action asks AANA to expose private data, bypass verification, send to an unsafe recipient, or make an unsupported irreversible claim.

## Explicit Non-Goals

The support product boundary does not certify final business correctness by itself. It does not replace:

- CRM authorization and access control
- Refund or billing systems of record
- Identity verification
- Human support review
- Legal/privacy review
- Email delivery controls
- Audit retention infrastructure
- Observability and incident response

Production readiness for support workflows requires live or approved evidence connectors, domain owner signoff, audit retention, observability, human review path, security review, deployment manifest, incident response plan, and measured pilot results.
