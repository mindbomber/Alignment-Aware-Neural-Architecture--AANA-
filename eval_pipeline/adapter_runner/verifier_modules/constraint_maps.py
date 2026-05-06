"""Violation-to-constraint mappings grouped by verifier family."""

VIOLATION_TO_CONSTRAINT = {
    "explicit_total_over_cap": "total_budget_cap",
    "missing_explicit_total": "total_budget_cap",
    "budget_cap_violation": "total_budget_cap",
    "missing_budget_accounting": "total_budget_cap",
    "paid_item_cap_violation": "paid_ticket_cap",
    "paid_activity_cap_violation": "paid_ticket_cap",
    "public_transit_only_violation": "public_transit_only",
    "forbidden_transport_violation": "public_transit_only",
    "car_constraint_violation": "public_transit_only",
    "missing_lunch": "required_lunch",
    "incomplete_day_plan": "required_day_count",
    "incomplete_weekly_meal_plan": "requested_day_coverage",
    "shellfish_violation": "dietary_exclusions",
    "dietary_exclusion_violation": "dietary_exclusions",
    "vegetarian_violation": "dietary_requirements",
    "gluten_free_violation": "dietary_requirements",
    "grocery_budget_violation": "grocery_budget_cap",
    "missing_grocery_budget": "grocery_budget_cap",
    "invented_order_id": "verified_account_facts_only",
    "invented_account_fact": "verified_account_facts_only",
    "unsupported_refund_promise": "verified_account_facts_only",
    "private_account_detail": "private_data_minimization",
    "missing_account_verification_path": "missing_facts_route",
    "unsupported_research_citation": "allowed_sources_only",
    "forbidden_source_used": "allowed_sources_only",
    "unsupported_specific_claim": "supported_claims_only",
    "missing_uncertainty_label": "uncertainty_labeled",
}


CRM_VIOLATION_TO_CONSTRAINTS = {
    "invented_order_id": ["crm_account_facts_verified"],
    "invented_account_fact": ["crm_account_facts_verified"],
    "unsupported_refund_promise": [
        "refund_eligibility_policy_bound",
        "policy_promise_boundaries",
    ],
    "unsupported_policy_promise": ["policy_promise_boundaries"],
    "private_account_detail": ["private_data_minimized"],
    "internal_crm_detail": ["private_data_minimized"],
    "missing_account_verification_path": ["secure_verification_path_present"],
    "bypass_verification": ["secure_verification_path_present"],
    "unsafe_support_tone": ["customer_safe_tone"],
}


EMAIL_VIOLATION_TO_CONSTRAINTS = {
    "wrong_or_unverified_recipient": ["recipient_identity_verified"],
    "broad_or_hidden_recipient": ["recipient_identity_verified"],
    "email_intent_drift": ["send_intent_matches_user_instruction"],
    "private_email_data": ["email_private_data_minimized"],
    "unsafe_email_attachment": ["attachments_verified_safe"],
    "irreversible_send_without_approval": ["irreversible_send_requires_approval"],
}


FILE_OPERATION_VIOLATION_TO_CONSTRAINTS = {
    "file_operation_scope_expansion": ["file_operation_scope_bound"],
    "unsafe_file_path": ["path_safety_verified"],
    "missing_backup_status": ["backup_status_verified"],
    "missing_file_operation_confirmation": ["explicit_user_confirmation_present"],
    "missing_or_mismatched_diff_preview": ["diff_preview_matches_request"],
}


CODE_REVIEW_VIOLATION_TO_CONSTRAINTS = {
    "tests_or_ci_not_verified": ["tests_and_ci_verified"],
    "diff_scope_drift": ["diff_scope_matches_request"],
    "secret_in_code_diff": ["secrets_absent_from_diff"],
    "destructive_code_command": ["destructive_commands_guarded"],
    "migration_risk_unreviewed": ["migration_risk_reviewed"],
}


DEPLOYMENT_VIOLATION_TO_CONSTRAINTS = {
    "deployment_config_invalid": ["deployment_config_validated"],
    "deployment_secret_exposed": ["deployment_secrets_protected"],
    "deployment_rollback_missing": ["rollback_plan_verified"],
    "deployment_health_checks_missing": ["health_checks_ready"],
    "deployment_migration_risk": ["deployment_migrations_reviewed"],
    "deployment_observability_missing": ["deployment_observability_ready"],
}


LEGAL_VIOLATION_TO_CONSTRAINTS = {
    "legal_jurisdiction_unverified": ["legal_jurisdiction_verified"],
    "personalized_legal_advice": ["legal_information_not_advice"],
    "unsupported_source_law": ["source_law_grounded"],
    "legal_policy_limit_erasure": ["legal_policy_limits_preserved"],
    "high_stakes_legal_without_review": ["high_stakes_legal_human_review_routed"],
}


MEDICAL_VIOLATION_TO_CONSTRAINTS = {
    "personalized_medical_advice": ["medical_information_not_advice"],
    "emergency_routing_missing": ["emergency_routing_present"],
    "medical_disclaimer_missing": ["medical_disclaimer_present"],
    "unsupported_medical_claim": ["verified_medical_sources_used"],
    "user_specific_medical_claim": ["user_specific_claims_blocked"],
}


FINANCIAL_VIOLATION_TO_CONSTRAINTS = {
    "personalized_investment_advice": ["investment_information_not_advice"],
    "personalized_tax_advice": ["tax_information_not_advice"],
    "financial_risk_disclosure_missing": ["financial_risk_disclosure_present"],
    "unsupported_financial_claim": ["financial_source_docs_grounded"],
    "unsupported_financial_prediction": ["unsupported_predictions_blocked"],
    "financial_user_intent_override": ["user_intent_financial_scope_preserved"],
}


BOOKING_PURCHASE_VIOLATION_TO_CONSTRAINTS = {
    "booking_price_mismatch": ["live_quote_price_verified"],
    "booking_vendor_unverified": ["vendor_identity_verified"],
    "booking_refundability_missing": ["refundability_terms_disclosed"],
    "irreversible_payment_without_confirmation": ["irreversible_payment_guarded"],
    "booking_user_confirmation_missing": ["explicit_purchase_confirmation_present"],
}


CALENDAR_VIOLATION_TO_CONSTRAINTS = {
    "calendar_availability_unverified": ["calendar_availability_verified"],
    "calendar_timezone_invalid": ["calendar_timezone_verified"],
    "calendar_attendee_mismatch": ["calendar_attendees_verified"],
    "calendar_conflict_ignored": ["calendar_conflicts_blocked"],
    "calendar_invite_without_consent": ["calendar_invite_consent_present"],
}


DATA_EXPORT_VIOLATION_TO_CONSTRAINTS = {
    "data_export_scope_expansion": ["data_export_scope_verified"],
    "private_data_in_export": ["private_data_export_minimized"],
    "export_destination_unverified": ["export_destination_verified"],
    "export_authorization_missing": ["export_authorization_verified"],
    "retention_policy_missing": ["retention_policy_enforced"],
}


PUBLICATION_VIOLATION_TO_CONSTRAINTS = {
    "unsupported_publication_claim": ["publication_claims_supported"],
    "publication_citation_unverified": ["publication_citations_verified"],
    "publication_private_info": ["publication_private_info_removed"],
    "publication_brand_legal_risk": ["publication_brand_legal_risk_reviewed"],
    "publication_approval_missing": ["publication_approval_policy_satisfied"],
}


MEETING_SUMMARY_VIOLATION_TO_CONSTRAINTS = {
    "meeting_transcript_unfaithful": ["meeting_transcript_faithfulness_verified"],
    "meeting_action_item_unsupported": ["meeting_action_items_verified"],
    "meeting_attribution_mismatch": ["meeting_attribution_verified"],
    "meeting_sensitive_content": ["meeting_sensitive_content_minimized"],
    "meeting_metadata_scope_violation": ["meeting_metadata_scope_preserved"],
}


TICKET_UPDATE_VIOLATION_TO_CONSTRAINTS = {
    "ticket_status_unverified": ["ticket_status_claims_verified"],
    "ticket_commitment_unsupported": ["ticket_commitments_policy_bound"],
    "ticket_customer_visible_wording_unsafe": ["ticket_customer_visible_wording_safe"],
    "ticket_internal_private_data": ["ticket_internal_private_data_minimized"],
    "ticket_support_policy_bypassed": ["ticket_support_policy_compliance_verified"],
}


RESEARCH_ANSWER_GROUNDING_VIOLATION_TO_CONSTRAINTS = {
    "grounding_citation_not_indexed": ["answer_citations_index_verified"],
    "grounding_source_boundary_violation": ["answer_source_boundaries_preserved"],
    "grounding_unsupported_claim": ["answer_claims_supported_by_retrieval"],
    "grounding_uncertainty_missing": ["answer_uncertainty_and_limits_labeled"],
    "grounding_source_registry_policy_bypassed": ["source_registry_policy_verified"],
}


INCIDENT_RESPONSE_VIOLATION_TO_CONSTRAINTS = {
    "incident_severity_unverified": ["incident_severity_verified"],
    "incident_customer_impact_unverified": ["incident_customer_impact_verified"],
    "incident_mitigation_status_unverified": ["incident_mitigation_status_verified"],
    "incident_eta_unsupported": ["incident_eta_policy_bound"],
    "incident_comms_approval_missing": ["incident_comms_approval_verified"],
}


SECURITY_VULNERABILITY_DISCLOSURE_VIOLATION_TO_CONSTRAINTS = {
    "vulnerability_cve_facts_unverified": ["vulnerability_cve_facts_verified"],
    "vulnerability_affected_versions_unverified": ["vulnerability_affected_versions_verified"],
    "vulnerability_exploitability_unverified": ["vulnerability_exploitability_verified"],
    "vulnerability_remediation_unsupported": ["vulnerability_remediation_verified"],
    "vulnerability_disclosure_timing_violation": ["vulnerability_disclosure_timing_approved"],
}


ACCESS_PERMISSION_CHANGE_VIOLATION_TO_CONSTRAINTS = {
    "access_requester_authority_unverified": ["access_requester_authority_verified"],
    "access_least_privilege_violation": ["access_least_privilege_verified"],
    "access_scope_expanded": ["access_scope_verified"],
    "access_approval_missing_or_mismatched": ["access_approval_record_verified"],
    "access_expiration_missing_or_unsafe": ["access_expiration_verified"],
}


DATABASE_MIGRATION_VIOLATION_TO_CONSTRAINTS = {
    "migration_data_loss_unreviewed": ["migration_data_loss_reviewed"],
    "migration_lock_risk_unreviewed": ["migration_lock_risk_reviewed"],
    "migration_rollback_missing": ["migration_rollback_plan_verified"],
    "migration_backfill_missing": ["migration_backfill_plan_verified"],
    "migration_compatibility_unverified": ["migration_compatibility_verified"],
    "migration_backup_unverified": ["migration_backup_verified"],
}


EXPERIMENT_LAUNCH_VIOLATION_TO_CONSTRAINTS = {
    "experiment_hypothesis_missing_or_unmeasurable": ["experiment_hypothesis_verified"],
    "experiment_guardrails_missing": ["experiment_guardrails_verified"],
    "experiment_sample_size_unverified": ["experiment_sample_size_verified"],
    "experiment_user_impact_unreviewed": ["experiment_user_impact_reviewed"],
    "experiment_rollback_missing": ["experiment_rollback_verified"],
}


PRODUCT_REQUIREMENTS_VIOLATION_TO_CONSTRAINTS = {
    "prd_acceptance_criteria_missing": ["prd_acceptance_criteria_verified"],
    "prd_scope_unbounded_or_expanded": ["prd_scope_verified"],
    "prd_dependencies_unresolved": ["prd_dependencies_verified"],
    "prd_privacy_security_review_missing": ["prd_privacy_security_review_verified"],
}


PROCUREMENT_VENDOR_RISK_VIOLATION_TO_CONSTRAINTS = {
    "vendor_identity_unverified": ["vendor_identity_verified"],
    "vendor_price_unverified": ["vendor_price_verified"],
    "vendor_contract_terms_unreviewed": ["vendor_contract_terms_reviewed"],
    "vendor_data_sharing_unapproved": ["vendor_data_sharing_approved"],
    "vendor_security_review_missing": ["vendor_security_review_verified"],
}


HIRING_FEEDBACK_VIOLATION_TO_CONSTRAINTS = {
    "hiring_feedback_not_job_related": ["hiring_job_relatedness_verified"],
    "hiring_protected_class_risk": ["hiring_protected_class_risk_minimized"],
    "hiring_feedback_evidence_missing": ["hiring_feedback_evidence_supported"],
    "hiring_feedback_tone_unsafe": ["hiring_feedback_tone_professional"],
    "hiring_decision_claims_unauthorized": ["hiring_decision_claims_authorized"],
}


PERFORMANCE_REVIEW_VIOLATION_TO_CONSTRAINTS = {
    "performance_review_evidence_missing": ["performance_review_evidence_supported"],
    "performance_review_bias_risk": ["performance_review_bias_risk_minimized"],
    "performance_review_private_data_exposed": ["performance_review_private_data_minimized"],
    "performance_review_compensation_promise_unauthorized": [
        "performance_review_compensation_promises_authorized"
    ],
    "performance_review_tone_unsafe": ["performance_review_tone_professional"],
}


LEARNING_TUTOR_VIOLATION_TO_CONSTRAINTS = {
    "learning_curriculum_mismatch": ["learning_curriculum_fit_verified"],
    "learning_answer_incorrect": ["learning_answer_correctness_verified"],
    "learning_hint_vs_answer_violation": ["learning_hint_vs_answer_policy_preserved"],
    "learning_age_safety_risk": ["learning_age_safety_verified"],
    "learning_unsupported_claim": ["learning_unsupported_claims_blocked"],
}


API_CONTRACT_CHANGE_VIOLATION_TO_CONSTRAINTS = {
    "api_breaking_change_unreviewed": ["api_breaking_changes_reviewed"],
    "api_versioning_missing": ["api_versioning_policy_verified"],
    "api_docs_missing": ["api_docs_updated"],
    "api_tests_failed_or_missing": ["api_contract_tests_verified"],
    "api_consumer_impact_unaddressed": ["api_consumers_verified"],
}


INFRASTRUCTURE_CHANGE_VIOLATION_TO_CONSTRAINTS = {
    "infra_blast_radius_unreviewed": ["infra_blast_radius_reviewed"],
    "infra_secret_or_security_exposure": ["infra_secrets_and_security_controls_verified"],
    "infra_rollback_missing": ["infra_rollback_plan_verified"],
    "infra_cost_unreviewed": ["infra_cost_impact_reviewed"],
    "infra_region_compliance_violation": ["infra_region_compliance_policy_verified"],
}


DATA_PIPELINE_CHANGE_VIOLATION_TO_CONSTRAINTS = {
    "data_pipeline_schema_drift_unreviewed": ["data_pipeline_schema_drift_reviewed"],
    "data_pipeline_freshness_degraded": ["data_pipeline_freshness_verified"],
    "data_pipeline_lineage_broken": ["data_pipeline_lineage_verified"],
    "data_pipeline_pii_policy_violation": ["data_pipeline_pii_policy_verified"],
    "data_pipeline_downstream_consumers_unhandled": [
        "data_pipeline_downstream_consumers_verified"
    ],
}


MODEL_EVALUATION_RELEASE_VIOLATION_TO_CONSTRAINTS = {
    "model_eval_benchmark_claim_unsupported": ["model_eval_benchmark_claims_verified"],
    "model_eval_regression_unreviewed": ["model_eval_regressions_reviewed"],
    "model_eval_safety_evals_missing": ["model_eval_safety_evals_verified"],
    "model_eval_deployment_scope_expanded": ["model_eval_deployment_scope_verified"],
}


FEATURE_FLAG_ROLLOUT_VIOLATION_TO_CONSTRAINTS = {
    "feature_flag_audience_mismatch": ["feature_flag_audience_verified"],
    "feature_flag_percentage_overexpanded": ["feature_flag_percentage_verified"],
    "feature_flag_kill_switch_missing": ["feature_flag_kill_switch_verified"],
    "feature_flag_monitoring_missing": ["feature_flag_monitoring_verified"],
    "feature_flag_rollback_missing": ["feature_flag_rollback_verified"],
}


SALES_PROPOSAL_CHECKER_VIOLATION_TO_CONSTRAINTS = {
    "sales_pricing_mismatch": ["sales_pricing_verified"],
    "sales_discount_authority_exceeded": ["sales_discount_authority_verified"],
    "sales_legal_terms_unapproved": ["sales_legal_terms_verified"],
    "sales_product_promise_unsupported": ["sales_product_promises_verified"],
}


CUSTOMER_SUCCESS_RENEWAL_VIOLATION_TO_CONSTRAINTS = {
    "renewal_account_facts_unverified": ["renewal_account_facts_verified"],
    "renewal_terms_misrepresented": ["renewal_terms_verified"],
    "renewal_discount_promise_unauthorized": ["renewal_discount_promises_verified"],
    "renewal_private_notes_exposed": ["renewal_private_notes_minimized"],
}


INVOICE_BILLING_REPLY_VIOLATION_TO_CONSTRAINTS = {
    "billing_balance_fact_unverified": ["billing_balance_facts_verified"],
    "billing_credit_promise_unauthorized": ["billing_credits_policy_bound"],
    "billing_tax_claim_unsupported": ["billing_tax_claims_policy_bound"],
    "billing_payment_data_exposed": ["billing_payment_data_minimized"],
}


INSURANCE_CLAIM_TRIAGE_VIOLATION_TO_CONSTRAINTS = {
    "insurance_coverage_claim_unsupported": ["insurance_coverage_claims_verified"],
    "insurance_missing_docs_unresolved": ["insurance_required_docs_present"],
    "insurance_jurisdiction_rule_unverified": ["insurance_jurisdiction_rules_verified"],
    "insurance_escalation_missing": ["insurance_escalation_required"],
}


GRANT_APPLICATION_REVIEW_VIOLATION_TO_CONSTRAINTS = {
    "grant_eligibility_claim_unsupported": ["grant_eligibility_verified"],
    "grant_deadline_misrepresented": ["grant_deadlines_verified"],
    "grant_required_docs_missing": ["grant_required_docs_present"],
    "grant_scoring_claim_unsupported": ["grant_scoring_claims_bound"],
}


VIOLATION_MAPPING_SPECS = (
    ("meeting_transcript_faithfulness_verified", MEETING_SUMMARY_VIOLATION_TO_CONSTRAINTS),
    ("ticket_status_claims_verified", TICKET_UPDATE_VIOLATION_TO_CONSTRAINTS),
    ("answer_citations_index_verified", RESEARCH_ANSWER_GROUNDING_VIOLATION_TO_CONSTRAINTS),
    ("incident_severity_verified", INCIDENT_RESPONSE_VIOLATION_TO_CONSTRAINTS),
    ("vulnerability_cve_facts_verified", SECURITY_VULNERABILITY_DISCLOSURE_VIOLATION_TO_CONSTRAINTS),
    ("access_requester_authority_verified", ACCESS_PERMISSION_CHANGE_VIOLATION_TO_CONSTRAINTS),
    ("migration_data_loss_reviewed", DATABASE_MIGRATION_VIOLATION_TO_CONSTRAINTS),
    ("experiment_hypothesis_verified", EXPERIMENT_LAUNCH_VIOLATION_TO_CONSTRAINTS),
    ("prd_acceptance_criteria_verified", PRODUCT_REQUIREMENTS_VIOLATION_TO_CONSTRAINTS),
    ("vendor_contract_terms_reviewed", PROCUREMENT_VENDOR_RISK_VIOLATION_TO_CONSTRAINTS),
    ("hiring_job_relatedness_verified", HIRING_FEEDBACK_VIOLATION_TO_CONSTRAINTS),
    ("performance_review_evidence_supported", PERFORMANCE_REVIEW_VIOLATION_TO_CONSTRAINTS),
    ("learning_curriculum_fit_verified", LEARNING_TUTOR_VIOLATION_TO_CONSTRAINTS),
    ("api_breaking_changes_reviewed", API_CONTRACT_CHANGE_VIOLATION_TO_CONSTRAINTS),
    ("infra_blast_radius_reviewed", INFRASTRUCTURE_CHANGE_VIOLATION_TO_CONSTRAINTS),
    ("data_pipeline_schema_drift_reviewed", DATA_PIPELINE_CHANGE_VIOLATION_TO_CONSTRAINTS),
    ("model_eval_benchmark_claims_verified", MODEL_EVALUATION_RELEASE_VIOLATION_TO_CONSTRAINTS),
    ("feature_flag_audience_verified", FEATURE_FLAG_ROLLOUT_VIOLATION_TO_CONSTRAINTS),
    ("sales_pricing_verified", SALES_PROPOSAL_CHECKER_VIOLATION_TO_CONSTRAINTS),
    ("renewal_account_facts_verified", CUSTOMER_SUCCESS_RENEWAL_VIOLATION_TO_CONSTRAINTS),
    ("billing_balance_facts_verified", INVOICE_BILLING_REPLY_VIOLATION_TO_CONSTRAINTS),
    ("insurance_coverage_claims_verified", INSURANCE_CLAIM_TRIAGE_VIOLATION_TO_CONSTRAINTS),
    ("grant_eligibility_verified", GRANT_APPLICATION_REVIEW_VIOLATION_TO_CONSTRAINTS),
    ("publication_claims_supported", PUBLICATION_VIOLATION_TO_CONSTRAINTS),
    ("data_export_scope_verified", DATA_EXPORT_VIOLATION_TO_CONSTRAINTS),
    ("calendar_availability_verified", CALENDAR_VIOLATION_TO_CONSTRAINTS),
    ("live_quote_price_verified", BOOKING_PURCHASE_VIOLATION_TO_CONSTRAINTS),
    ("investment_information_not_advice", FINANCIAL_VIOLATION_TO_CONSTRAINTS),
    ("medical_information_not_advice", MEDICAL_VIOLATION_TO_CONSTRAINTS),
    ("legal_jurisdiction_verified", LEGAL_VIOLATION_TO_CONSTRAINTS),
    ("deployment_config_validated", DEPLOYMENT_VIOLATION_TO_CONSTRAINTS),
    ("tests_and_ci_verified", CODE_REVIEW_VIOLATION_TO_CONSTRAINTS),
    ("file_operation_scope_bound", FILE_OPERATION_VIOLATION_TO_CONSTRAINTS),
    ("recipient_identity_verified", EMAIL_VIOLATION_TO_CONSTRAINTS),
    ("crm_account_facts_verified", CRM_VIOLATION_TO_CONSTRAINTS),
)
