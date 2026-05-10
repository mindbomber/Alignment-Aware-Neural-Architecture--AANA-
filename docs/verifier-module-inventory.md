# Verifier Module Inventory

The adapter runner keeps public behavior behind the Workflow Contract and Agent Event Contract. These verifier modules are internal platform-core implementation details.

## Family Modules

### Customer Comms

Module: `eval_pipeline/adapter_runner/verifier_modules/customer_comms.py`

- `support_tool_report`
- `email_tool_report`
- Safe responses: `support_safe_response`, `email_safe_response`

### Local Actions

Module: `eval_pipeline/adapter_runner/verifier_modules/local_actions.py`

- `file_operation_tool_report`
- `booking_purchase_tool_report`
- `calendar_tool_report`
- `data_export_tool_report`
- Safe responses: `file_operation_repair`, `booking_purchase_repair`, `calendar_repair`, `data_export_repair`

### Engineering / Release

Module: `eval_pipeline/adapter_runner/verifier_modules/engineering_release.py`

- `code_review_tool_report`
- `deployment_tool_report`
- `incident_response_tool_report`
- `security_vulnerability_disclosure_tool_report`
- `access_permission_change_tool_report`
- `database_migration_tool_report`
- `experiment_launch_tool_report`
- `api_contract_change_tool_report`
- `infrastructure_change_guardrail_tool_report`
- `data_pipeline_change_tool_report`
- `model_evaluation_release_tool_report`
- `feature_flag_rollout_tool_report`
- Safe responses live beside the matching verifier as `*_repair` functions.

### Regulated Advice

Module: `eval_pipeline/adapter_runner/verifier_modules/regulated_advice.py`

- `insurance_claim_triage_tool_report`
- `legal_tool_report`
- `medical_tool_report`
- `financial_tool_report`
- Safe responses live beside the matching verifier as `*_repair` functions.

### Business Ops

Module: `eval_pipeline/adapter_runner/verifier_modules/business_ops.py`

- `product_requirements_tool_report`
- `procurement_vendor_risk_tool_report`
- `hiring_candidate_feedback_tool_report`
- `performance_review_tool_report`
- `learning_tutor_answer_checker_tool_report`
- `sales_proposal_checker_tool_report`
- `customer_success_renewal_tool_report`
- `invoice_billing_reply_tool_report`
- Safe responses live beside the matching verifier as `*_repair` functions.

### Research / Citation / Civic

Module: `eval_pipeline/adapter_runner/verifier_modules/research_civic.py`

- `grant_application_review_tool_report`
- `publication_tool_report`
- `meeting_summary_tool_report`
- `ticket_update_tool_report`
- `research_answer_grounding_tool_report`
- `research_tool_report`
- Safe responses live beside the matching verifier as `*_repair` functions.

## Constraint Maps

Violation-to-constraint maps are centralized in `eval_pipeline/adapter_runner/verifier_modules/constraint_maps.py` and exported through `VIOLATION_MAPPING_SPECS`.

## Registry Metadata

`VERIFIER_REGISTRY` is assembled in `eval_pipeline/adapter_runner/verifier_catalog.py`. Entries now declare:

- verifier name
- family
- supported adapter ids
- report function
- safe-response function
- correction routes where available
- fallback action

## Adapter Routing

Adapter family predicates and task construction live in `eval_pipeline/adapter_runner/routing.py`. The legacy runner imports these names for compatibility, but does not own the routing rules.

## Runtime Orchestration

The compatibility execution path lives in `eval_pipeline/adapter_runner/runtime.py`. `scripts/adapters/run_adapter.py` and `eval_pipeline/adapter_runner/legacy_runner.py` remain thin compatibility wrappers for older CLI and import paths.

## Stability Gate

After moving verifier families, run:

```powershell
python -m unittest tests.test_adapter_runner_golden_outputs
python scripts/adapters/compare_adapter_runner_baseline.py --ref HEAD
python scripts/dev.py test
```
