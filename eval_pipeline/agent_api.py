"""Small Python API for checking AI-agent events with AANA adapters."""

import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_adapter
import validate_adapter_gallery
from eval_pipeline import agent_contract, audit, aix, evidence as evidence_registry, evidence_integrations, workflow_contract


AGENT_EVENT_VERSION = agent_contract.AGENT_EVENT_VERSION
WORKFLOW_CONTRACT_VERSION = workflow_contract.WORKFLOW_CONTRACT_VERSION
DEFAULT_GALLERY = ROOT / "examples" / "adapter_gallery.json"
DEFAULT_AGENT_EVENTS_DIR = ROOT / "examples" / "agent_events"


POLICY_PRESETS = {
    "message_send": {
        "description": "Use before an agent sends an email, chat message, support reply, or public post.",
        "recommended_adapters": ["support_reply", "email_send_guardrail"],
        "call_before": ["send_message", "send_email", "publish_post"],
        "watch_for": ["private data", "unsupported claims", "tone", "missing evidence", "recipient and attachment approval"],
    },
    "file_write": {
        "description": "Use before an agent writes, moves, deletes, or publishes user files.",
        "recommended_adapters": ["file_operation_guardrail"],
        "call_before": ["write_file", "move_file", "delete_file", "publish_file"],
        "watch_for": ["operation scope", "path safety", "backup status", "missing user confirmation", "diff or preview"],
    },
    "code_commit": {
        "description": "Use before an agent commits, pushes, or opens a pull request.",
        "recommended_adapters": ["code_change_review"],
        "call_before": ["git_commit", "git_push", "create_pull_request"],
        "watch_for": ["test failures", "secret leakage", "unreviewed scope", "unsafe automation", "migration risk"],
    },
    "incident_response": {
        "description": "Use before an agent posts, sends, schedules, or syncs incident response updates.",
        "recommended_adapters": ["incident_response_update"],
        "call_before": ["post_status_page_update", "send_incident_update", "sync_incident_status", "notify_customers"],
        "watch_for": ["severity", "customer impact", "mitigation status", "ETA", "communications approval"],
    },
    "security_disclosure": {
        "description": "Use before an agent drafts, posts, sends, schedules, or releases security vulnerability disclosures.",
        "recommended_adapters": ["security_vulnerability_disclosure"],
        "call_before": ["publish_security_advisory", "send_vulnerability_notice", "release_security_notes", "lift_embargo"],
        "watch_for": ["CVE facts", "affected versions", "exploitability", "remediation", "disclosure timing"],
    },
    "access_permission_change": {
        "description": "Use before an agent grants, modifies, escalates, extends, or removes IAM permissions.",
        "recommended_adapters": ["access_permission_change"],
        "call_before": ["grant_access", "modify_role", "escalate_permission", "extend_access", "add_group_member"],
        "watch_for": ["requester authority", "least privilege", "scope", "approval", "expiration"],
    },
    "database_migration": {
        "description": "Use before an agent approves, runs, schedules, merges, or rolls out database migrations.",
        "recommended_adapters": ["database_migration_guardrail"],
        "call_before": ["run_migration", "approve_migration", "schedule_migration", "merge_schema_change"],
        "watch_for": ["data loss", "locks", "rollback", "backfill", "compatibility", "backup"],
    },
    "experiment_launch": {
        "description": "Use before an agent launches, ramps, schedules, or auto-ships experiments and A/B tests.",
        "recommended_adapters": ["experiment_ab_test_launch"],
        "call_before": ["launch_experiment", "ramp_experiment", "schedule_ab_test", "auto_ship_variant"],
        "watch_for": ["hypothesis", "guardrails", "sample size", "user impact", "rollback"],
    },
    "product_requirements": {
        "description": "Use before an agent approves, summarizes, hands off, or converts product requirements into implementation work.",
        "recommended_adapters": ["product_requirements_checker"],
        "call_before": ["approve_prd", "handoff_requirements", "create_epic", "start_implementation"],
        "watch_for": ["acceptance criteria", "scope", "dependencies", "privacy review", "security review"],
    },
    "procurement_vendor_risk": {
        "description": "Use before an agent approves, purchases, onboards, renews, or shares data with a vendor.",
        "recommended_adapters": ["procurement_vendor_risk"],
        "call_before": ["approve_vendor", "purchase_vendor", "onboard_vendor", "share_vendor_data"],
        "watch_for": ["vendor identity", "price", "contract terms", "data sharing", "security review"],
    },
    "hiring_feedback": {
        "description": "Use before an agent writes, saves, sends, or summarizes hiring candidate feedback.",
        "recommended_adapters": ["hiring_candidate_feedback"],
        "call_before": ["save_candidate_feedback", "send_candidate_feedback", "submit_interview_scorecard", "draft_hiring_summary"],
        "watch_for": ["job-relatedness", "protected-class risk", "evidence", "tone", "decision claims"],
    },
    "performance_review": {
        "description": "Use before an agent drafts, saves, shares, summarizes, or routes employee performance review feedback.",
        "recommended_adapters": ["performance_review"],
        "call_before": ["draft_performance_review", "save_performance_review", "share_review_feedback", "submit_review_packet"],
        "watch_for": ["evidence", "bias risk", "private data", "compensation promises", "tone"],
    },
    "learning_tutor_answer_checker": {
        "description": "Use before an agent shows, sends, saves, or grades learner-facing tutor answers.",
        "recommended_adapters": ["learning_tutor_answer_checker"],
        "call_before": ["show_tutor_answer", "send_tutor_hint", "save_tutor_response", "grade_learning_answer"],
        "watch_for": ["curriculum fit", "correctness", "hint-vs-answer", "age safety", "unsupported claims"],
    },
    "api_contract_change": {
        "description": "Use before an agent merges, releases, deploys, publishes, or announces API contract changes.",
        "recommended_adapters": ["api_contract_change"],
        "call_before": ["merge_api_contract", "release_api", "deploy_api", "publish_openapi_spec", "notify_api_consumers"],
        "watch_for": ["breaking changes", "versioning", "docs", "tests", "consumers"],
    },
    "infrastructure_change": {
        "description": "Use before an agent merges, applies, deploys, promotes, or approves infrastructure changes.",
        "recommended_adapters": ["infrastructure_change_guardrail"],
        "call_before": ["merge_iac_change", "apply_infrastructure_plan", "deploy_infrastructure", "approve_change_request"],
        "watch_for": ["blast radius", "secrets", "rollback", "cost", "region and compliance"],
    },
    "data_pipeline_change": {
        "description": "Use before an agent merges, deploys, backfills, schedules, or promotes data pipeline changes.",
        "recommended_adapters": ["data_pipeline_change"],
        "call_before": ["merge_pipeline_change", "deploy_pipeline", "run_backfill", "change_dag_schedule", "promote_dataset"],
        "watch_for": ["schema drift", "freshness", "lineage", "PII", "downstream consumers"],
    },
    "model_evaluation_release": {
        "description": "Use before an agent announces, publishes, promotes, deploys, or scopes a model evaluation release.",
        "recommended_adapters": ["model_evaluation_release"],
        "call_before": ["publish_model_card", "announce_model_benchmark", "promote_model_release", "deploy_model", "expand_model_scope"],
        "watch_for": ["benchmark claims", "regressions", "safety evals", "deployment scope"],
    },
    "feature_flag_rollout": {
        "description": "Use before an agent enables, ramps, schedules, expands, or promotes a production feature flag.",
        "recommended_adapters": ["feature_flag_rollout"],
        "call_before": ["enable_feature_flag", "ramp_feature_flag", "schedule_flag_rollout", "expand_flag_audience", "promote_feature"],
        "watch_for": ["audience", "percentage", "kill switch", "monitoring", "rollback"],
    },
    "sales_proposal_checker": {
        "description": "Use before an agent sends, approves, quotes, or redlines a customer sales proposal.",
        "recommended_adapters": ["sales_proposal_checker"],
        "call_before": ["send_sales_proposal", "approve_quote", "generate_order_form", "redline_contract", "commit_product_terms"],
        "watch_for": ["pricing", "discount authority", "legal terms", "product promises"],
    },
    "customer_success_renewal": {
        "description": "Use before an agent sends, approves, drafts, or updates a customer renewal communication.",
        "recommended_adapters": ["customer_success_renewal"],
        "call_before": ["send_renewal_email", "approve_renewal_offer", "generate_renewal_quote", "update_renewal_opportunity", "commit_renewal_terms"],
        "watch_for": ["account facts", "renewal terms", "discount promises", "private notes"],
    },
    "invoice_billing_reply": {
        "description": "Use before an agent sends, approves, drafts, or updates a customer invoice or billing reply.",
        "recommended_adapters": ["invoice_billing_reply"],
        "call_before": ["send_billing_reply", "approve_invoice_adjustment", "grant_billing_credit", "update_invoice_status", "send_payment_instruction"],
        "watch_for": ["balance facts", "credits", "tax claims", "payment data"],
    },
    "insurance_claim_triage": {
        "description": "Use before an agent sends, approves, drafts, or routes an insurance claim triage reply.",
        "recommended_adapters": ["insurance_claim_triage"],
        "call_before": ["send_claim_reply", "triage_claim", "approve_claim_payment", "close_claim", "route_claim_queue"],
        "watch_for": ["coverage claims", "missing docs", "jurisdiction rules", "escalation"],
    },
    "grant_application_review": {
        "description": "Use before an agent sends, approves, drafts, scores, or routes a grant/application review decision.",
        "recommended_adapters": ["grant_application_review"],
        "call_before": ["send_application_review", "triage_application", "advance_application", "score_application", "notify_applicant"],
        "watch_for": ["eligibility", "deadlines", "required docs", "scoring claims"],
    },
    "deployment_release": {
        "description": "Use before an agent deploys, releases, promotes, or changes production runtime configuration.",
        "recommended_adapters": ["deployment_readiness"],
        "call_before": ["deploy_service", "promote_release", "run_migration", "change_runtime_config"],
        "watch_for": ["config validity", "sensitive values", "rollback", "health checks", "migrations", "observability"],
    },
    "legal_safety": {
        "description": "Use before an agent answers legal-adjacent questions or drafts legal-adjacent content.",
        "recommended_adapters": ["legal_safety_router"],
        "call_before": ["answer_legal_question", "draft_legal_content", "summarize_legal_document"],
        "watch_for": ["jurisdiction", "source law", "policy limits", "personalized advice", "human review"],
    },
    "medical_safety": {
        "description": "Use before an agent answers medical-adjacent questions or drafts health-related content.",
        "recommended_adapters": ["medical_safety_router"],
        "call_before": ["answer_medical_question", "draft_health_content", "summarize_medical_information"],
        "watch_for": ["medical advice boundaries", "emergency routing", "disclaimers", "verified sources", "user-specific claims"],
    },
    "financial_safety": {
        "description": "Use before an agent answers financial-adjacent questions or drafts investment, tax, or regulated financial content.",
        "recommended_adapters": ["financial_advice_router"],
        "call_before": ["answer_financial_question", "draft_financial_content", "summarize_financial_information"],
        "watch_for": ["investment advice boundaries", "tax advice boundaries", "risk disclosure", "source documents", "unsupported predictions", "user intent"],
    },
    "support_reply": {
        "description": "Use before an agent drafts customer-support replies or account-specific messages.",
        "recommended_adapters": ["support_reply"],
        "call_before": ["draft_support_reply", "send_support_reply"],
        "watch_for": ["invented account facts", "private account data", "unsupported promises"],
    },
    "booking_or_purchase": {
        "description": "Use before an agent books, buys, reserves, or recommends paid options.",
        "recommended_adapters": ["travel_planning", "booking_purchase_guardrail"],
        "call_before": ["book_trip", "purchase_item", "reserve_ticket"],
        "watch_for": ["price", "vendor", "refundability", "irreversible payment", "user confirmation", "missing live prices"],
    },
    "calendar_scheduling": {
        "description": "Use before an agent creates, updates, sends, or finalizes calendar invites.",
        "recommended_adapters": ["calendar_scheduling"],
        "call_before": ["create_calendar_invite", "send_calendar_invite", "update_calendar_event"],
        "watch_for": ["availability", "timezone", "attendees", "conflicts", "invite send consent"],
    },
    "data_export": {
        "description": "Use before an agent prepares, downloads, shares, stores, or transmits data exports.",
        "recommended_adapters": ["data_export_guardrail"],
        "call_before": ["export_data", "download_dataset", "share_export", "create_public_link"],
        "watch_for": ["export scope", "private data", "destination", "authorization", "retention policy"],
    },
    "publication_check": {
        "description": "Use before an agent publishes, posts, releases, sends, or schedules public content.",
        "recommended_adapters": ["publication_check"],
        "call_before": ["publish_post", "release_article", "schedule_publication", "send_public_content"],
        "watch_for": ["claims", "citations", "private info", "brand risk", "legal risk", "approval policy"],
    },
    "meeting_summary": {
        "description": "Use before an agent publishes, sends, stores, or shares meeting summaries.",
        "recommended_adapters": ["meeting_summary_checker"],
        "call_before": ["publish_meeting_summary", "send_meeting_recap", "store_meeting_notes", "share_meeting_summary"],
        "watch_for": ["transcript faithfulness", "action items", "attribution", "sensitive content", "distribution scope"],
    },
    "ticket_update": {
        "description": "Use before an agent posts, sends, syncs, or drafts customer-visible ticket updates.",
        "recommended_adapters": ["ticket_update_checker"],
        "call_before": ["post_ticket_update", "send_customer_ticket_update", "sync_ticket_status", "draft_support_update"],
        "watch_for": ["status claims", "commitments", "customer-visible wording", "internal data", "private data", "support policy"],
    },
    "private_data_use": {
        "description": "Use before an agent reads, summarizes, shares, or acts on private user/account data.",
        "recommended_adapters": ["support_reply"],
        "call_before": ["read_private_data", "share_private_data", "summarize_account"],
        "watch_for": ["data minimization", "verified need", "secure routing", "missing consent"],
    },
    "research_summary": {
        "description": "Use before an agent publishes or shares a research summary, brief, synthesis, or cited answer.",
        "recommended_adapters": ["research_summary"],
        "call_before": ["draft_research_summary", "publish_brief", "answer_with_citations"],
        "watch_for": ["invented citations", "unsupported claims", "forbidden sources", "missing uncertainty"],
    },
    "research_answer_grounding": {
        "description": "Use before an agent publishes, shares, or relies on a cited research answer from retrieved documents.",
        "recommended_adapters": ["research_answer_grounding"],
        "call_before": ["answer_with_retrieval", "publish_cited_answer", "share_research_answer", "ground_rag_output"],
        "watch_for": ["citation index", "source boundaries", "unsupported claims", "uncertainty", "source registry"],
    },
}


def load_json_file(path):
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def load_gallery(path=DEFAULT_GALLERY):
    return validate_adapter_gallery.load_gallery(path)


def gallery_entries(gallery):
    return gallery.get("adapters", []) if isinstance(gallery.get("adapters"), list) else []


def find_entry(gallery, adapter_id):
    for entry in gallery_entries(gallery):
        if entry.get("id") == adapter_id:
            return entry
    available = ", ".join(entry.get("id", "") for entry in gallery_entries(gallery))
    raise ValueError(f"Unknown adapter id: {adapter_id}. Available adapters: {available}.")


def evidence_item_to_text(item):
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)
    parts = []
    if item.get("source_id"):
        parts.append(f"source_id={item['source_id']}")
    if item.get("trust_tier"):
        parts.append(f"trust_tier={item['trust_tier']}")
    if item.get("redaction_status"):
        parts.append(f"redaction_status={item['redaction_status']}")
    prefix = " ".join(parts)
    if prefix:
        return f"[{prefix}] {item.get('text', '')}"
    return item.get("text", "")


def prompt_from_event(event):
    user_request = event.get("user_request") or event.get("prompt")
    if not isinstance(user_request, str) or not user_request.strip():
        raise ValueError("Agent event must include a non-empty user_request.")

    evidence = event.get("available_evidence", [])
    if isinstance(evidence, list) and evidence:
        evidence_lines = "\n".join(f"- {evidence_item_to_text(item)}" for item in evidence)
        return f"{user_request}\n\nAvailable verified evidence:\n{evidence_lines}"
    return user_request


def candidate_from_event(event):
    candidate = event.get("candidate_action")
    if candidate is None:
        candidate = event.get("candidate_answer")
    if candidate is None:
        candidate = event.get("draft_response")
    return candidate


def check_event(event, gallery_path=DEFAULT_GALLERY, adapter_id=None):
    if isinstance(event, dict) and adapter_id and event.get("adapter_id") and adapter_id != event.get("adapter_id"):
        raise ValueError(f"Route mismatch: adapter_id override {adapter_id!r} does not match event adapter_id {event.get('adapter_id')!r}.")
    contract_report = agent_contract.validate_agent_event(event, policy_presets=POLICY_PRESETS)
    if not contract_report["valid"]:
        messages = "; ".join(issue["message"] for issue in contract_report["issues"] if issue["level"] == "error")
        raise ValueError(messages)

    gallery = load_gallery(gallery_path)
    resolved_adapter_id = adapter_id or event.get("adapter_id") or event.get("workflow")
    if not resolved_adapter_id:
        raise ValueError("Agent event must include adapter_id or workflow, or pass adapter_id.")

    entry = find_entry(gallery, resolved_adapter_id)
    adapter = run_adapter.load_adapter(ROOT / entry["adapter_path"])
    result = run_adapter.run_adapter(adapter, prompt_from_event(event), candidate_from_event(event))
    return {
        "agent_check_version": AGENT_EVENT_VERSION,
        "agent": event.get("agent", "unknown"),
        "adapter_id": resolved_adapter_id,
        "workflow": entry.get("title"),
        "event_id": event.get("event_id"),
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "aix": result.get("aix"),
        "candidate_aix": result.get("candidate_aix"),
        "violations": result.get("candidate_tool_report", result.get("tool_report", {})).get("violations", []),
        "safe_response": result.get("final_answer"),
        "adapter_result": result,
    }


def check_workflow(
    adapter,
    request,
    candidate=None,
    evidence=None,
    constraints=None,
    allowed_actions=None,
    metadata=None,
    workflow_id=None,
    gallery_path=DEFAULT_GALLERY,
):
    workflow_request = workflow_contract.normalize_workflow_request(
        adapter=adapter,
        request=request,
        candidate=candidate,
        evidence=evidence,
        constraints=constraints,
        allowed_actions=allowed_actions,
        metadata=metadata,
        workflow_id=workflow_id,
    )
    return check_workflow_request(workflow_request, gallery_path=gallery_path)


def check_workflow_request(workflow_request, gallery_path=DEFAULT_GALLERY):
    contract_report = workflow_contract.validate_workflow_request(workflow_request)
    if not contract_report["valid"]:
        messages = "; ".join(issue["message"] for issue in contract_report["issues"] if issue["level"] == "error")
        raise ValueError(messages)

    event = workflow_contract.workflow_request_to_agent_event(workflow_request)
    result = check_event(event, gallery_path=gallery_path)
    recommended_action, action_violation = workflow_contract.action_within_allowed(
        result.get("recommended_action"),
        workflow_request.get("allowed_actions"),
    )
    violations = list(result.get("violations", []))
    if action_violation:
        violations.append(action_violation)
    workflow_aix = result.get("aix")
    if action_violation and isinstance(workflow_aix, dict):
        workflow_aix = dict(workflow_aix)
        hard_blockers = list(workflow_aix.get("hard_blockers", []))
        hard_blockers.append(action_violation["code"])
        workflow_aix["hard_blockers"] = sorted(set(hard_blockers))
        thresholds = {
            **aix.DEFAULT_THRESHOLDS,
            **(workflow_aix.get("thresholds", {}) if isinstance(workflow_aix.get("thresholds"), dict) else {}),
        }
        score = min(float(workflow_aix.get("score", 0.0)), float(thresholds.get("accept", 0.85)) - 0.01)
        workflow_aix["score"] = round(max(0.0, score), 4)
        workflow_aix["decision"] = aix.decision_from_score(
            workflow_aix["score"],
            hard_blockers=workflow_aix["hard_blockers"],
            thresholds=thresholds,
        )
        notes = list(workflow_aix.get("notes", []))
        notes.append("Workflow allowed_actions changed the recommended action; direct accept is blocked.")
        workflow_aix["notes"] = notes
    return {
        "contract_version": WORKFLOW_CONTRACT_VERSION,
        "workflow_id": workflow_request.get("workflow_id"),
        "adapter": result.get("adapter_id"),
        "workflow": result.get("workflow"),
        "gate_decision": result.get("gate_decision"),
        "recommended_action": recommended_action,
        "candidate_gate": result.get("candidate_gate"),
        "aix": workflow_aix,
        "candidate_aix": result.get("candidate_aix"),
        "violations": violations,
        "output": result.get("safe_response"),
        "raw_result": result,
    }


def workflow_batch_summary(results):
    gate_decisions = {}
    recommended_actions = {}
    for result in results:
        gate_decision = result.get("gate_decision")
        recommended_action = result.get("recommended_action")
        gate_decisions[gate_decision] = gate_decisions.get(gate_decision, 0) + 1
        recommended_actions[recommended_action] = recommended_actions.get(recommended_action, 0) + 1
    failed = sum(1 for result in results if result.get("gate_decision") != "pass")
    return {
        "total": len(results),
        "passed": len(results) - failed,
        "failed": failed,
        "gate_decisions": gate_decisions,
        "recommended_actions": recommended_actions,
    }


def workflow_item_failure_result(workflow_request, error, index=None, batch_id=None):
    item = workflow_request if isinstance(workflow_request, dict) else {}
    workflow_id = item.get("workflow_id")
    if not workflow_id and index is not None:
        workflow_id = f"{batch_id or 'workflow-batch'}-{index + 1}"
    recommended_action, action_violation = workflow_contract.safe_failure_action(item.get("allowed_actions"))
    violation = {
        "code": "workflow_item_error",
        "severity": "high",
        "message": str(error),
    }
    violations = [violation]
    hard_blockers = [violation["code"]]
    if action_violation:
        violations.append(action_violation)
        hard_blockers.append(action_violation["code"])
    return {
        "contract_version": WORKFLOW_CONTRACT_VERSION,
        "workflow_id": workflow_id,
        "adapter": item.get("adapter"),
        "workflow": None,
        "gate_decision": "fail",
        "recommended_action": recommended_action,
        "candidate_gate": "block",
        "aix": {
            "aix_version": aix.AIX_VERSION,
            "score": 0.0,
            "components": {},
            "base_score": 0.0,
            "penalty": 1.0,
            "beta": 1.0,
            "thresholds": dict(aix.DEFAULT_THRESHOLDS),
            "decision": "refuse",
            "hard_blockers": sorted(set(hard_blockers)),
            "notes": ["Workflow batch item failed before adapter completion; direct accept is blocked."],
        },
        "candidate_aix": None,
        "violations": violations,
        "output": None,
        "raw_result": {
            "error": {
                "type": error.__class__.__name__,
                "message": str(error),
            }
        },
    }


def check_workflow_batch(batch_request, gallery_path=DEFAULT_GALLERY):
    contract_report = workflow_contract.validate_workflow_batch_request(batch_request)
    if not contract_report["valid"]:
        messages = "; ".join(issue["message"] for issue in contract_report["issues"] if issue["level"] == "error")
        raise ValueError(messages)

    results = []
    for index, workflow_request in enumerate(batch_request["requests"]):
        item = dict(workflow_request)
        if not item.get("workflow_id"):
            item["workflow_id"] = f"{batch_request.get('batch_id') or 'workflow-batch'}-{index + 1}"
        try:
            results.append(check_workflow_request(item, gallery_path=gallery_path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            results.append(
                workflow_item_failure_result(
                    item,
                    exc,
                    index=index,
                    batch_id=batch_request.get("batch_id"),
                )
            )

    return {
        "contract_version": WORKFLOW_CONTRACT_VERSION,
        "batch_id": batch_request.get("batch_id"),
        "summary": workflow_batch_summary(results),
        "results": results,
    }


def audit_event_check(event, result=None, created_at=None):
    if result is None:
        result = check_event(event)
    return audit.agent_audit_record(event, result, created_at=created_at)


def audit_workflow_check(workflow_request, result=None, created_at=None):
    if result is None:
        result = check_workflow_request(workflow_request)
    return audit.workflow_audit_record(workflow_request, result, created_at=created_at)


def audit_workflow_batch(batch_request, result=None, created_at=None):
    if result is None:
        result = check_workflow_batch(batch_request)
    requests = batch_request.get("requests", []) if isinstance(batch_request, dict) else []
    records = []
    for workflow_request, workflow_result in zip(requests, result.get("results", []), strict=False):
        records.append(audit_workflow_check(workflow_request, workflow_result, created_at=created_at))
    timestamp = created_at or (records[0]["created_at"] if records else None)
    return {
        "audit_record_version": audit.AUDIT_RECORD_VERSION,
        "created_at": timestamp,
        "record_type": "workflow_batch_check",
        "batch_id": result.get("batch_id") if isinstance(result, dict) else None,
        "summary": result.get("summary", {}) if isinstance(result, dict) else {},
        "records": records,
    }


def append_audit_record(path, record):
    return audit.append_jsonl(path, record)


def load_audit_records(path):
    return audit.load_jsonl(path)


def summarize_audit_records(records):
    return audit.summarize_records(records)


def summarize_audit_file(path):
    return audit.summarize_jsonl(path)


def export_audit_metrics(records, audit_log_path=None, created_at=None):
    return audit.export_metrics(records, audit_log_path=audit_log_path, created_at=created_at)


def export_audit_metrics_file(audit_log_path, output_path=None, created_at=None):
    return audit.export_metrics_jsonl(audit_log_path, output_path=output_path, created_at=created_at)


def create_audit_integrity_manifest(audit_log_path, manifest_path=None, previous_manifest_path=None, created_at=None):
    return audit.create_integrity_manifest(
        audit_log_path,
        manifest_path=manifest_path,
        previous_manifest_path=previous_manifest_path,
        created_at=created_at,
    )


def verify_audit_integrity_manifest(manifest_path):
    return audit.verify_integrity_manifest(manifest_path)


def list_policy_presets():
    return POLICY_PRESETS


def validate_event(event, evidence_registry=None, require_structured_evidence=False, now=None):
    return agent_contract.validate_agent_event(
        event,
        policy_presets=POLICY_PRESETS,
        source_registry=evidence_registry,
        require_structured_evidence=require_structured_evidence,
        now=now,
    )


def validate_workflow_request(workflow_request):
    return workflow_contract.validate_workflow_request(workflow_request)


def validate_workflow_batch_request(batch_request):
    return workflow_contract.validate_workflow_batch_request(batch_request)


def load_evidence_registry(path):
    return evidence_registry.load_registry(path)


def validate_evidence_registry(registry):
    return evidence_registry.validate_registry(registry)


def evidence_integration_stubs():
    return [stub.to_dict() for stub in evidence_integrations.all_integration_stubs()]


def evidence_integration_coverage(registry=None):
    return evidence_integrations.integration_coverage_report(registry=registry)


def validate_workflow_evidence(workflow_request, registry, require_structured=False, now=None):
    return evidence_registry.validate_workflow_evidence(
        workflow_request,
        registry,
        require_structured=require_structured,
        now=now,
    )


def validate_workflow_batch_evidence(batch_request, registry, require_structured=False, now=None):
    return evidence_registry.validate_workflow_batch_evidence(
        batch_request,
        registry,
        require_structured=require_structured,
        now=now,
    )


def schema_catalog():
    return {
        **agent_contract.schema_catalog(),
        **workflow_contract.schema_catalog(),
    }


def discover_agent_events(events_dir=DEFAULT_AGENT_EVENTS_DIR):
    path = pathlib.Path(events_dir)
    if not path.exists():
        raise ValueError(f"Agent events directory does not exist: {path}")
    return sorted(item for item in path.glob("*.json") if item.is_file())


def run_agent_event_examples(events_dir=DEFAULT_AGENT_EVENTS_DIR, gallery_path=DEFAULT_GALLERY):
    rows = []
    for path in discover_agent_events(events_dir):
        event = load_json_file(path)
        validation = validate_event(event)
        if not validation["valid"]:
            rows.append(
                {
                    "event_file": str(path),
                    "event_id": event.get("event_id"),
                    "adapter_id": event.get("adapter_id"),
                    "valid": False,
                    "gate_decision": None,
                    "recommended_action": None,
                    "candidate_gate": None,
                    "aix_decision": None,
                    "candidate_aix_decision": None,
                    "passed_expectations": False,
                    "validation": validation,
                }
            )
            continue

        result = check_event(event, gallery_path=gallery_path)
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        expected_candidate_gate = metadata.get("expected_candidate_gate")
        expected_gate_decision = metadata.get("expected_gate_decision")
        expected_recommended_action = metadata.get("expected_recommended_action")
        expected_aix_decision = metadata.get("expected_aix_decision")
        expected_candidate_aix_decision = metadata.get("expected_candidate_aix_decision")
        expectation_checks = [
            expected_candidate_gate is None or result.get("candidate_gate") == expected_candidate_gate,
            expected_gate_decision is None or result.get("gate_decision") == expected_gate_decision,
            expected_recommended_action is None or result.get("recommended_action") == expected_recommended_action,
            expected_aix_decision is None or result.get("aix", {}).get("decision") == expected_aix_decision,
            expected_candidate_aix_decision is None
            or result.get("candidate_aix", {}).get("decision") == expected_candidate_aix_decision,
        ]
        rows.append(
            {
                "event_file": str(path),
                "event_id": event.get("event_id"),
                "adapter_id": result.get("adapter_id"),
                "valid": True,
                "gate_decision": result.get("gate_decision"),
                "recommended_action": result.get("recommended_action"),
                "candidate_gate": result.get("candidate_gate"),
                "aix_decision": result.get("aix", {}).get("decision"),
                "candidate_aix_decision": result.get("candidate_aix", {}).get("decision"),
                "passed_expectations": all(expectation_checks),
                "validation": validation,
            }
        )

    return {
        "valid": all(row["valid"] and row["passed_expectations"] for row in rows),
        "events_dir": str(pathlib.Path(events_dir)),
        "count": len(rows),
        "checked_examples": rows,
    }


def build_agent_event_from_gallery(adapter_id, gallery_path=DEFAULT_GALLERY, agent="openclaw"):
    gallery = load_gallery(gallery_path)
    entry = find_entry(gallery, adapter_id)
    expected = entry.get("expected", {}) if isinstance(entry.get("expected"), dict) else {}
    event_id = f"draft-{adapter_id}-001"
    evidence = [
        f"Workflow: {entry.get('workflow', 'replace with verified workflow notes')}",
        "Replace this list with verified facts, records, constraints, or retrieved evidence.",
    ]
    for constraint_id in expected.get("failing_constraints", []):
        evidence.append(f"Constraint to preserve: {constraint_id}")

    return {
        "event_version": AGENT_EVENT_VERSION,
        "event_id": event_id,
        "agent": agent,
        "adapter_id": adapter_id,
        "user_request": entry.get("prompt", "Replace with the user request to check."),
        "candidate_action": entry.get("bad_candidate", "Replace with the agent's planned answer or action."),
        "available_evidence": evidence,
        "allowed_actions": ["accept", "revise", "ask", "defer", "refuse"],
        "metadata": {
            "scenario": adapter_id,
            "policy_preset": suggested_policy_preset(adapter_id),
            "expected_candidate_gate": expected.get("candidate_gate"),
            "expected_gate_decision": expected.get("gate_decision"),
            "expected_recommended_action": expected.get("recommended_action"),
            "expected_aix_decision": expected.get("aix_decision"),
            "expected_candidate_aix_decision": expected.get("candidate_aix_decision"),
            "notes": "Replace starter values with a real planned agent action before production use.",
        },
    }


def suggested_policy_preset(adapter_id):
    for preset_name, preset in POLICY_PRESETS.items():
        if adapter_id in preset.get("recommended_adapters", []):
            return preset_name
    return "custom"


def scaffold_agent_event(adapter_id, output_dir=DEFAULT_AGENT_EVENTS_DIR, gallery_path=DEFAULT_GALLERY, agent="openclaw", force=False):
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{adapter_id}.json"
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists. Use --force to overwrite.")

    event = build_agent_event_from_gallery(adapter_id, gallery_path=gallery_path, agent=agent)
    path.write_text(json.dumps(event, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "event": str(path),
        "next_steps": [
            f"python scripts/aana_cli.py validate-event --event {path}",
            f"python scripts/aana_cli.py agent-check --event {path}",
            "Replace the starter candidate_action and available_evidence with a real agent workflow case.",
        ],
    }
