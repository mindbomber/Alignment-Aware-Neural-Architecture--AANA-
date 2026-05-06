"""Adapter routing predicates and task construction."""

def is_travel_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return "travel" in haystack or "itinerary" in haystack or "outing" in haystack

def is_meal_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return "meal" in haystack or "grocery" in haystack or "allergy" in haystack

def is_support_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "support_reply" in haystack
        or "customer support" in haystack
        or "customer-support" in haystack
        or "crm" in haystack
        or "refund" in haystack
    )

def is_ticket_update_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "ticket_update_checker" in haystack
        or "ticket update checker" in haystack
        or "ticket update" in haystack
        or "ticket history" in haystack
        or "sprint status" in haystack
        or "customer-visible ticket" in haystack
    )

def is_email_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "email_send" in haystack
        or "email send" in haystack
        or "send_guardrail" in haystack
        or "recipient metadata" in haystack
        or "attachment" in haystack
    )

def is_file_operation_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "file_operation" in haystack
        or "file operation" in haystack
        or "delete, move" in haystack
        or "backup status" in haystack
        or "path safety" in haystack
        or "diff or preview" in haystack
    )

def is_code_review_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "code_change_review" in haystack
        or "code change review" in haystack
        or "git diff" in haystack
        or "ci status" in haystack
        or "migration risk" in haystack
    )

def is_deployment_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "deployment_readiness" in haystack
        or "deployment readiness" in haystack
        or "deployment manifest" in haystack
        or "release notes" in haystack
        or "rollback" in haystack
        or "observability" in haystack
    )

def is_incident_response_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "incident_response_update" in haystack
        or "incident response update" in haystack
        or "incident timeline" in haystack
        or "status-page policy" in haystack
        or "on-call notes" in haystack
        or "incident communications" in haystack
    )

def is_security_vulnerability_disclosure_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "security_vulnerability_disclosure" in haystack
        or "security vulnerability disclosure" in haystack
        or "security advisory" in haystack
        or "scanner output" in haystack
        or "affected versions" in haystack
        or "disclosure timing" in haystack
    )

def is_access_permission_change_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "access_permission_change" in haystack
        or "access permission change" in haystack
        or "iam request" in haystack
        or "role catalog" in haystack
        or "approval record" in haystack
        or "least privilege" in haystack
    )

def is_database_migration_guardrail_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "database_migration_guardrail" in haystack
        or "database migration guardrail" in haystack
        or "migration diff" in haystack
        or "schema state" in haystack
        or "backup status" in haystack
        or "rollout plan" in haystack
    )

def is_experiment_launch_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "experiment_ab_test_launch" in haystack
        or "experiment launch" in haystack
        or "a/b test" in haystack
        or "experiment config" in haystack
        or "metric registry" in haystack
        or "risk policy" in haystack
    )

def is_product_requirements_checker_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "product_requirements_checker" in haystack
        or "product requirements checker" in haystack
        or "prd" in haystack
        or "roadmap" in haystack
        or "design spec" in haystack
        or "policy checklist" in haystack
    )

def is_procurement_vendor_risk_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "procurement_vendor_risk" in haystack
        or "procurement vendor risk" in haystack
        or "vendor-risk" in haystack
        or "dpa/security docs" in haystack
        or "third-party risk" in haystack
    )

def is_hiring_candidate_feedback_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "hiring_candidate_feedback" in haystack
        or "hiring candidate feedback" in haystack
        or "interview notes" in haystack
        or "hiring policy" in haystack
        or "protected-class" in haystack
        or "candidate feedback" in haystack
    )

def is_performance_review_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "performance_review" in haystack
        or "performance review" in haystack
        or "review packet" in haystack
        or "hr policy" in haystack
        or "compensation promises" in haystack
    )

def is_learning_tutor_answer_checker_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "learning_tutor_answer_checker" in haystack
        or "learning tutor answer" in haystack
        or "tutor answer" in haystack
        or "lesson plan" in haystack
        or "solution key" in haystack
        or "learner profile" in haystack
    )

def is_api_contract_change_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "api_contract_change" in haystack
        or "api contract change" in haystack
        or "openapi diff" in haystack
        or "consumer list" in haystack
        or "contract tests" in haystack
    )

def is_infrastructure_change_guardrail_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "infrastructure_change_guardrail" in haystack
        or "infrastructure change guardrail" in haystack
        or "iac diff" in haystack
        or "plan output" in haystack
        or "region/compliance" in haystack
    )

def is_data_pipeline_change_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "data_pipeline_change" in haystack
        or "data pipeline change" in haystack
        or "dag metadata" in haystack
        or "schema registry" in haystack
        or "lineage graph" in haystack
    )

def is_model_evaluation_release_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "model_evaluation_release" in haystack
        or "model evaluation release" in haystack
        or "eval results" in haystack
        or "model card" in haystack
        or "release policy" in haystack
    )

def is_feature_flag_rollout_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "feature_flag_rollout" in haystack
        or "feature flag rollout" in haystack
        or "flag config" in haystack
        or "kill switch" in haystack
    )

def is_sales_proposal_checker_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "sales_proposal_checker" in haystack
        or "sales proposal" in haystack
        or "crm opportunity" in haystack
        or "price book" in haystack
        or "contract policy" in haystack
    )

def is_customer_success_renewal_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "customer_success_renewal" in haystack
        or "customer success renewal" in haystack
        or "account health" in haystack
        or "renewal communications" in haystack
    )

def is_invoice_billing_reply_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "invoice_billing_reply" in haystack
        or "invoice billing reply" in haystack
        or "invoice and billing" in haystack
        or "billing replies" in haystack
    )

def is_insurance_claim_triage_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "insurance_claim_triage" in haystack
        or "insurance claim triage" in haystack
        or "claim triage" in haystack
        or "policy docs" in haystack
    )

def is_grant_application_review_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "grant_application_review" in haystack
        or "grant application review" in haystack
        or "application review" in haystack
        or "program rules" in haystack
    )

def is_legal_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "legal_safety" in haystack
        or "legal safety" in haystack
        or "legal-adjacent" in haystack
        or "source law" in haystack
        or "jurisdiction" in haystack
    )

def is_medical_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "medical_safety" in haystack
        or "medical safety" in haystack
        or "medical-adjacent" in haystack
        or "severity signals" in haystack
        or "verified medical" in haystack
    )

def is_financial_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "financial_advice" in haystack
        or "financial advice" in haystack
        or "financial-adjacent" in haystack
        or "investment" in haystack
        or "tax advice" in haystack
        or "source documents" in haystack
    )

def is_booking_purchase_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "booking_purchase" in haystack
        or "booking purchase" in haystack
        or "purchase_guardrail" in haystack
        or "checkout" in haystack
        or "live quote" in haystack
        or "payment policy" in haystack
    )

def is_calendar_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "calendar_scheduling" in haystack
        or "calendar scheduling" in haystack
        or "calendar free/busy" in haystack
        or "free/busy" in haystack
        or "attendee list" in haystack
        or "send invites" in haystack
    )

def is_data_export_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "data_export" in haystack
        or "data export" in haystack
        or "export guardrail" in haystack
        or "data classification" in haystack
        or "access grants" in haystack
        or "retention policy" in haystack
    )

def is_publication_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "publication_check" in haystack
        or "publication check" in haystack
        or "publishing" in haystack
        or "source list" in haystack
        or "approval policy" in haystack
        or "brand/legal" in haystack
    )

def is_meeting_summary_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "meeting_summary_checker" in haystack
        or "meeting summary checker" in haystack
        or "meeting summary" in haystack
        or "transcript" in haystack
        or "attendee-list" in haystack
        or "meeting metadata" in haystack
    )

def is_research_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "research_summary" in haystack
        or "grounded_research" in haystack
        or "research" in haystack
        or "citation" in haystack
    )

def is_research_answer_grounding_adapter(adapter):
    haystack = " ".join(
        [
            str(adapter.get("adapter_name", "")),
            str(adapter.get("domain", {}).get("name", "")),
            str(adapter.get("domain", {}).get("user_workflow", "")),
        ]
    ).lower()
    return (
        "research_answer_grounding" in haystack
        or "research answer grounding" in haystack
        or "retrieved documents" in haystack
        or "citation index" in haystack
        or "source registry" in haystack
        or "answer-grounding" in haystack
    )

def make_task(adapter, prompt):
    if is_travel_adapter(adapter):
        task_type = "budgeted_travel_planner"
        block = "application_demo"
    elif is_meal_adapter(adapter):
        task_type = "allergy_safe_meal_planner"
        block = "application_demo"
    elif is_research_answer_grounding_adapter(adapter):
        task_type = "research_answer_grounding"
        block = "application_demo"
    elif is_research_adapter(adapter):
        task_type = "grounded_research_summary"
        block = "application_demo"
    elif is_email_adapter(adapter):
        task_type = "email_send_guardrail"
        block = "application_demo"
    elif is_file_operation_adapter(adapter):
        task_type = "file_operation_guardrail"
        block = "application_demo"
    elif is_code_review_adapter(adapter):
        task_type = "code_change_review"
        block = "application_demo"
    elif is_incident_response_adapter(adapter):
        task_type = "incident_response_update"
        block = "application_demo"
    elif is_security_vulnerability_disclosure_adapter(adapter):
        task_type = "security_vulnerability_disclosure"
        block = "application_demo"
    elif is_access_permission_change_adapter(adapter):
        task_type = "access_permission_change"
        block = "application_demo"
    elif is_feature_flag_rollout_adapter(adapter):
        task_type = "feature_flag_rollout"
        block = "application_demo"
    elif is_sales_proposal_checker_adapter(adapter):
        task_type = "sales_proposal_checker"
        block = "application_demo"
    elif is_customer_success_renewal_adapter(adapter):
        task_type = "customer_success_renewal"
        block = "application_demo"
    elif is_invoice_billing_reply_adapter(adapter):
        task_type = "invoice_billing_reply"
        block = "application_demo"
    elif is_insurance_claim_triage_adapter(adapter):
        task_type = "insurance_claim_triage"
        block = "application_demo"
    elif is_grant_application_review_adapter(adapter):
        task_type = "grant_application_review"
        block = "application_demo"
    elif is_database_migration_guardrail_adapter(adapter):
        task_type = "database_migration_guardrail"
        block = "application_demo"
    elif is_experiment_launch_adapter(adapter):
        task_type = "experiment_ab_test_launch"
        block = "application_demo"
    elif is_product_requirements_checker_adapter(adapter):
        task_type = "product_requirements_checker"
        block = "application_demo"
    elif is_procurement_vendor_risk_adapter(adapter):
        task_type = "procurement_vendor_risk"
        block = "application_demo"
    elif is_hiring_candidate_feedback_adapter(adapter):
        task_type = "hiring_candidate_feedback"
        block = "application_demo"
    elif is_performance_review_adapter(adapter):
        task_type = "performance_review"
        block = "application_demo"
    elif is_learning_tutor_answer_checker_adapter(adapter):
        task_type = "learning_tutor_answer_checker"
        block = "application_demo"
    elif is_api_contract_change_adapter(adapter):
        task_type = "api_contract_change"
        block = "application_demo"
    elif is_infrastructure_change_guardrail_adapter(adapter):
        task_type = "infrastructure_change_guardrail"
        block = "application_demo"
    elif is_data_pipeline_change_adapter(adapter):
        task_type = "data_pipeline_change"
        block = "application_demo"
    elif is_model_evaluation_release_adapter(adapter):
        task_type = "model_evaluation_release"
        block = "application_demo"
    elif is_deployment_adapter(adapter):
        task_type = "deployment_readiness"
        block = "application_demo"
    elif is_legal_adapter(adapter):
        task_type = "legal_safety_router"
        block = "application_demo"
    elif is_medical_adapter(adapter):
        task_type = "medical_safety_router"
        block = "application_demo"
    elif is_financial_adapter(adapter):
        task_type = "financial_advice_router"
        block = "application_demo"
    elif is_booking_purchase_adapter(adapter):
        task_type = "booking_purchase_guardrail"
        block = "application_demo"
    elif is_calendar_adapter(adapter):
        task_type = "calendar_scheduling"
        block = "application_demo"
    elif is_data_export_adapter(adapter):
        task_type = "data_export_guardrail"
        block = "application_demo"
    elif is_meeting_summary_adapter(adapter):
        task_type = "meeting_summary_checker"
        block = "application_demo"
    elif is_ticket_update_adapter(adapter):
        task_type = "ticket_update_checker"
        block = "application_demo"
    elif is_publication_adapter(adapter):
        task_type = "publication_check"
        block = "application_demo"
    elif is_support_adapter(adapter):
        task_type = "privacy_safe_support_reply"
        block = "application_demo"
    else:
        task_type = "domain_adapter"
        block = "adapter"

    return {
        "id": "adapter_prompt",
        "block": block,
        "task_type": task_type,
        "capability_prompt": "Answer usefully while preserving every hard adapter constraint.",
        "low_pressure_prompt": prompt,
        "high_pressure_prompt": prompt,
        "reference_notes": "Adapter constraints: "
        + "; ".join(c.get("id", "") for c in adapter.get("constraints", [])),
    }
