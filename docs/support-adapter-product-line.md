# Support Adapter Product Line

AANA support adapters are a product line, not example-only fixtures. They are the first deployable support guardrails for checking customer-visible replies and actions before an agent sends, posts, promises, updates, or routes work.

Production positioning stays conservative: these adapters are demo-ready or pilot-ready in this repository. Real production use still requires live CRM, ticketing, mailbox, billing, policy, approval, audit, observability, and human-review integrations with domain owner signoff.

## Runtime Surfaces

Every support product adapter must support:

- CLI
- Python SDK
- HTTP bridge
- Workflow Contract
- Agent Event Contract

Public callers should use the Workflow Contract or Agent Event Contract. Adapter files, verifier modules, runner internals, and repair helpers are implementation details.

## Product Adapters

| Adapter ID | Product Boundary | Production Status |
| --- | --- | --- |
| `support_reply` | Draft support reply guardrail for verified facts, private-data minimization, and secure routing. | Demo adapter |
| `crm_support_reply` | CRM-backed support reply guardrail for account facts, refund eligibility, policy promises, tone, and privacy. | Pilot-ready |
| `email_send_guardrail` | Email-send guardrail for recipients, intent, attachments, private data, and explicit send approval. | Pilot-ready |
| `ticket_update_checker` | Customer-visible ticket update checker for status claims, commitments, wording, private data, and policy. | Pilot-ready |
| `invoice_billing_reply` | Adjacent billing/invoice reply checker for invoice facts, credits, tax claims, payment data, and secure routing. | Production candidate, pending external evidence |

## Required Metadata

Each support adapter gallery entry declares:

- clear `id` and `title`
- `product_line: "support"`
- supported surfaces
- `risk_tier` and `aix_tuning`
- evidence requirements
- verifier behavior
- correction policy summary
- human review path
- caveats
- production status

Catalog validation fails if these fields are missing for a support adapter.

## Evidence Boundary

Support guardrails are only production-useful when they can check live or approved evidence. Production claims are blocked until every required support connector exists as either a live production connector manifest or an approved production fixture:

- `crm_customer_account`: CRM/customer account record
- `order_history`: order history
- `refund_policy`: refund policy
- `internal_notes_classifier`: agent-only/internal notes classifier
- `support_ticket_history`: support ticket history
- `email_recipient_verification`: email recipient verification
- `attachment_metadata`: attachment metadata
- `account_verification_status`: account verification status
- `billing_payment_redaction`: billing/payment redaction metadata
- `support_policy_registry`: support policy registry

The checked-in mock connector fixtures are synthetic contract fixtures. They prove evidence shape, auth-scope, freshness, redaction, and failure-routing behavior, but they do not make the support product line production-ready.

## AIx Calibration

Support AIx calibration is tracked in `examples/support_aix_calibration_cases.json`.
The fixture covers clean candidates, unsafe candidates, borderline verification
cases, missing evidence, high-risk privacy, internal CRM note leakage, and
irreversible email-send cases across standard, high, and strict risk tiers.

Run the support calibration gate:

```powershell
python scripts/aana_cli.py support-aix-calibration
python scripts/aana_cli.py support-aix-calibration --json
```

The report tracks:

- over-acceptance
- over-refusal
- correction success
- human-review precision and recall
- false blocker rate
- evidence-missing behavior

The checked-in thresholds require zero over-acceptance, zero over-refusal, zero
false blockers on clean support cases, full correction success on unsafe cases,
and correct missing-evidence routing. These are fixture-calibration gates, not
proof of production calibration on live traffic.

## Later Adapters

The support roadmap tracks later adapters separately from the first deployable set:

- refunds
- account closure
- chargeback
- cancellation
- escalation
- retention/deletion request

These should not be presented as supported product adapters until they have gallery entries, executable fixtures, AIx tuning, evidence requirements, correction policy, and human-review routing.
