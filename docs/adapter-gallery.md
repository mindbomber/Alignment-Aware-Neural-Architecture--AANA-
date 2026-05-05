# AANA Adapter Gallery

Canonical entry point: [Build Adapter](build-adapter/index.md). The gallery is the adapter catalog used by demo, runtime, and adapter-building paths.

The adapter gallery is the shortest path from "AANA works in one demo" to "I can copy this pattern into my own domain."

Catalog status is not production certification. This repository is demo-ready and pilot-ready for controlled evaluation, but it is not production-certified by itself. Production readiness requires live evidence connectors, domain owner signoff, audit retention, observability, and human review paths.

Open the searchable published gallery:

- [`docs/adapter-gallery/index.html`](adapter-gallery/index.html)

When the gallery is served by the Docker or Python HTTP bridge, each adapter
detail pane includes **Try this adapter**. That opens the web playground with
the adapter preselected, preloads the prompt and bad candidate, and lets a user
run the AANA check from the browser.

It lists each runnable domain adapter with:

- the adapter JSON file,
- risk tier,
- required evidence,
- supported surfaces,
- example inputs and expected outputs,
- AIx tuning,
- a realistic prompt,
- a deliberately bad candidate,
- expected gate behavior,
- caveats for real deployment,
- a copyable command.

Machine-readable gallery:

- [`examples/adapter_gallery.json`](../examples/adapter_gallery.json)
- [`docs/adapter-gallery/data.json`](adapter-gallery/data.json)

Rebuild the published gallery data after adapter changes:

```powershell
python scripts/build_adapter_gallery.py
```

Validate the gallery:

```powershell
python scripts/aana_cli.py validate-gallery --run-examples
```

That command checks that every referenced adapter is valid, runs executable examples, and confirms the expected gate result still holds.

Run an example by id:

```powershell
python scripts/aana_cli.py list
python scripts/aana_cli.py run support_reply
```

Check an agent event:

```powershell
aana agent-check --event examples/agent_event_support_reply.json
```

Use agent-event files only in a trusted local checkout or installed AANA package. Standalone agent skills should prefer a reviewed in-memory tool/API interface and should not infer or execute relative script paths.

## Current Executable Examples

| Domain | Adapter | What It Proves |
|---|---|---|
| Budgeted travel planning | [`examples/travel_adapter.json`](../examples/travel_adapter.json) | The gate can block a useful-looking itinerary that breaks budget, transport, ticket, and lunch constraints, then pass a repaired answer. |
| Budgeted allergy-safe meal planning | [`examples/meal_planning_adapter.json`](../examples/meal_planning_adapter.json) | The same correction path transfers to groceries, dietary exclusions, explicit totals, and weekly coverage. |
| Privacy-safe customer support | [`examples/support_reply_adapter.json`](../examples/support_reply_adapter.json) | The gate can block invented order details, unsupported refund promises, and private payment details, then pass a reply that asks/routes through secure verification. |
| CRM support replies | [`examples/crm_support_reply_adapter.json`](../examples/crm_support_reply_adapter.json) | The gate can block invented CRM/order facts, refund overpromises, private payment/internal CRM details, verification bypasses, and policy-promise violations, then pass a secure verification reply. |
| Email send guardrail | [`examples/email_send_guardrail_adapter.json`](../examples/email_send_guardrail_adapter.json) | The gate can block wrong recipients, intent drift, private data, unsafe attachments, and missing explicit send approval, then pass a held draft that asks for approval. |
| File operation guardrail | [`examples/file_operation_guardrail_adapter.json`](../examples/file_operation_guardrail_adapter.json) | The gate can block out-of-scope deletes/moves/writes, unsafe paths, missing backup status, missing confirmation, and missing diff/preview, then pass a preview-only plan. |
| Code change review | [`examples/code_change_review_adapter.json`](../examples/code_change_review_adapter.json) | The gate can block missing or failing tests, diff scope drift, secret exposure, destructive commands, and unreviewed migrations, then pass a hold-for-review recommendation. |
| Incident response update | [`examples/incident_response_update_adapter.json`](../examples/incident_response_update_adapter.json) | The gate can block unverified severity, exaggerated customer impact, unsupported mitigation status, ETA promises, and missing communications approval, then pass an incident-update hold. |
| Security vulnerability disclosure | [`examples/security_vulnerability_disclosure_adapter.json`](../examples/security_vulnerability_disclosure_adapter.json) | The gate can block unverified CVE facts, affected-version expansion, exploitability claims, unsupported remediation, and disclosure-timing violations, then pass a disclosure hold. |
| Access permission change | [`examples/access_permission_change_adapter.json`](../examples/access_permission_change_adapter.json) | The gate can block unverified requester authority, least-privilege violations, scope expansion, missing approval, and unsafe expiration, then pass an access-change hold. |
| Database migration guardrail | [`examples/database_migration_guardrail_adapter.json`](../examples/database_migration_guardrail_adapter.json) | The gate can block data loss, lock risk, missing rollback, missing backfill, compatibility breaks, and backup gaps, then pass a phased migration hold. |
| Experiment/A-B test launch | [`examples/experiment_ab_test_launch_adapter.json`](../examples/experiment_ab_test_launch_adapter.json) | The gate can block missing hypotheses, missing guardrails, unsupported sample size, unreviewed user impact, and missing rollback, then pass an experiment-launch hold. |
| Feature flag rollout | [`examples/feature_flag_rollout_adapter.json`](../examples/feature_flag_rollout_adapter.json) | The gate can block audience mismatch, percentage overexpansion, missing kill switch, missing monitoring, and missing rollback, then pass a feature-flag rollout hold. |
| Sales proposal checker | [`examples/sales_proposal_checker_adapter.json`](../examples/sales_proposal_checker_adapter.json) | The gate can block pricing mismatch, excessive discounts, unapproved legal terms, and unsupported product promises, then pass a sales-proposal hold. |
| Customer success renewal | [`examples/customer_success_renewal_adapter.json`](../examples/customer_success_renewal_adapter.json) | The gate can block unsupported account facts, misrepresented renewal terms, unauthorized discount promises, and private account-note exposure, then pass a renewal hold. |
| Invoice/billing reply | [`examples/invoice_billing_reply_adapter.json`](../examples/invoice_billing_reply_adapter.json) | The gate can block wrong balance facts, unauthorized credits or waivers, unsupported tax claims, and exposed payment metadata, then pass a billing reply hold. |
| Insurance claim triage | [`examples/insurance_claim_triage_adapter.json`](../examples/insurance_claim_triage_adapter.json) | The gate can block unsupported coverage claims, missing required documents, unverified state rules, and missing escalation, then pass a claim-triage hold. |
| Grant/application review | [`examples/grant_application_review_adapter.json`](../examples/grant_application_review_adapter.json) | The gate can block unsupported eligibility claims, deadline misstatements, missing required documents, and unsupported rubric or award claims, then pass an application-review hold. |
| Product requirements checker | [`examples/product_requirements_checker_adapter.json`](../examples/product_requirements_checker_adapter.json) | The gate can block vague acceptance criteria, scope expansion, unresolved dependencies, and missing privacy/security review, then pass a PRD approval hold. |
| Procurement/vendor risk | [`examples/procurement_vendor_risk_adapter.json`](../examples/procurement_vendor_risk_adapter.json) | The gate can block unverified vendor identity, unsupported pricing, unreviewed contract terms, unapproved data sharing, and missing security review, then pass a procurement hold. |
| Hiring candidate feedback | [`examples/hiring_candidate_feedback_adapter.json`](../examples/hiring_candidate_feedback_adapter.json) | The gate can block non-job-related feedback, protected-class risk, unsupported claims, unsafe tone, and unauthorized decision claims, then pass a rubric-grounded hold. |
| Performance review | [`examples/performance_review_adapter.json`](../examples/performance_review_adapter.json) | The gate can block unevidenced review claims, bias risk, private employee data, unauthorized compensation promises, and unsafe tone, then pass an evidence-grounded HR hold. |
| Learning/tutor answer checker | [`examples/learning_tutor_answer_checker_adapter.json`](../examples/learning_tutor_answer_checker_adapter.json) | The gate can block off-curriculum tutoring, wrong answers, direct-answer leakage, learner age-safety risk, and ungrounded learning claims, then pass a hint-first tutor hold. |
| API contract change | [`examples/api_contract_change_adapter.json`](../examples/api_contract_change_adapter.json) | The gate can block unreviewed breaking changes, missing versioning, stale docs, failed tests, and unhandled consumer impact, then pass an API-contract release hold. |
| Infrastructure change guardrail | [`examples/infrastructure_change_guardrail_adapter.json`](../examples/infrastructure_change_guardrail_adapter.json) | The gate can block broad blast radius, secret/security exposure, missing rollback, unreviewed cost, and region/compliance violations, then pass an infrastructure apply hold. |
| Data pipeline change | [`examples/data_pipeline_change_adapter.json`](../examples/data_pipeline_change_adapter.json) | The gate can block schema drift, freshness degradation, broken lineage, PII policy violations, and unhandled downstream consumers, then pass a data-pipeline deployment hold. |
| Model evaluation release | [`examples/model_evaluation_release_adapter.json`](../examples/model_evaluation_release_adapter.json) | The gate can block unsupported benchmark claims, unreviewed regressions, missing safety evals, and deployment-scope expansion, then pass a model-release hold. |
| Deployment readiness | [`examples/deployment_readiness_adapter.json`](../examples/deployment_readiness_adapter.json) | The gate can block invalid config, exposed sensitive values, missing rollback, missing health checks, risky migrations, and missing observability, then pass a hold-release recommendation. |
| Legal safety router | [`examples/legal_safety_router_adapter.json`](../examples/legal_safety_router_adapter.json) | The gate can block personalized legal advice, unsupported jurisdiction/source-law claims, policy-limit erasure, and missing high-stakes review, then pass a general-information route. |
| Medical safety router | [`examples/medical_safety_router_adapter.json`](../examples/medical_safety_router_adapter.json) | The gate can block diagnosis, dosing, missing emergency routing, missing disclaimers, unsupported medical claims, and user-specific claims, then pass a safe medical route. |
| Financial advice router | [`examples/financial_advice_router_adapter.json`](../examples/financial_advice_router_adapter.json) | The gate can block individualized investment/tax advice, missing risk disclosure, unsupported source claims, unsupported predictions, and user-intent override, then pass a general-education route. |
| Booking/purchase guardrail | [`examples/booking_purchase_guardrail_adapter.json`](../examples/booking_purchase_guardrail_adapter.json) | The gate can block price mismatch, unverified vendor, hidden refundability, irreversible payment, and missing exact confirmation, then pass a checkout hold. |
| Calendar scheduling | [`examples/calendar_scheduling_adapter.json`](../examples/calendar_scheduling_adapter.json) | The gate can block unavailable times, timezone ambiguity, attendee drift, ignored conflicts, and missing invite-send consent, then pass a scheduling hold. |
| Data export guardrail | [`examples/data_export_guardrail_adapter.json`](../examples/data_export_guardrail_adapter.json) | The gate can block export scope expansion, private-data leakage, unapproved destinations, missing authorization, and retention-policy violations, then pass an export hold. |
| Publication check | [`examples/publication_check_adapter.json`](../examples/publication_check_adapter.json) | The gate can block unsupported claims, bad citations, private information, unreviewed brand/legal risk, and missing approval-policy clearance, then pass a publication hold. |
| Meeting summary checker | [`examples/meeting_summary_checker_adapter.json`](../examples/meeting_summary_checker_adapter.json) | The gate can block transcript-unfaithful claims, unsupported action items, attribution mismatches, sensitive content, and distribution-scope violations, then pass a summary hold. |
| Ticket update checker | [`examples/ticket_update_checker_adapter.json`](../examples/ticket_update_checker_adapter.json) | The gate can block unverified status claims, unsupported commitments, unsafe customer-visible wording, internal/private data exposure, and support-policy bypass, then pass a ticket-update hold. |
| Research answer grounding | [`examples/research_answer_grounding_adapter.json`](../examples/research_answer_grounding_adapter.json) | The gate can block invalid citations, source-boundary violations, unsupported claims, uncertainty erasure, and source-registry policy bypass, then pass an evidence-bounded answer hold. |
| Grounded research summaries | [`examples/research_summary_adapter.json`](../examples/research_summary_adapter.json) | The gate can block invented citations, forbidden sources, unsupported numbers, and missing uncertainty labels, then pass a source-bounded brief. |

## Add A Domain To The Gallery

1. Create or scaffold an adapter.
2. Add one realistic prompt.
3. Add one bad candidate that sounds useful but breaks a named constraint.
4. Run the adapter and record expected `candidate_gate`, `gate_decision`, `recommended_action`, `aix_decision`, and `candidate_aix_decision`.
5. Add the entry to `examples/adapter_gallery.json`.
6. Run `python scripts/aana_cli.py validate-gallery --run-examples`.

Keep the claim narrow: a gallery entry proves that this adapter contract, this verifier path, and this example gate behavior work. It does not prove broad safety for the domain.
