"""Minimal Python SDK surface for AANA workflow checks."""

import json
import pathlib

from eval_pipeline.agent_api import (
    WORKFLOW_CONTRACT_VERSION,
    append_audit_record,
    apply_shadow_mode,
    audit_aix_drift_report,
    audit_aix_drift_report_file,
    audit_dashboard,
    audit_dashboard_file,
    audit_event_check,
    audit_redaction_report,
    audit_workflow_batch,
    audit_workflow_check,
    check_workflow,
    check_workflow_batch,
    check_workflow_request,
    evidence_connector_marketplace,
    evidence_connector_contracts,
    evidence_integration_coverage,
    evidence_integration_stubs,
    evidence_mock_connector_matrix,
    export_audit_metrics,
    export_audit_metrics_file,
    load_audit_records,
    load_evidence_mock_fixtures,
    load_evidence_registry,
    normalize_evidence_object,
    run_evidence_mock_connector,
    schema_catalog,
    support_evidence_boundary,
    summarize_audit_file,
    summarize_audit_records,
    validate_audit_file,
    validate_audit_metrics_export,
    validate_audit_records,
    validate_workflow_batch_evidence,
    validate_workflow_batch_request,
    validate_evidence_registry,
    validate_workflow_evidence,
    validate_workflow_request,
    write_audit_reviewer_report,
)
from eval_pipeline.aix import calculate_aix, decision_from_score
from eval_pipeline.evidence_integrations import (
    CIVIC_CONNECTOR_CONTRACT_IDS,
    CORE_CONNECTOR_CONTRACT_IDS,
    EvidenceAuthContext,
    EvidenceConnectorFailure,
    EvidenceConnectorResult,
    EvidenceFetchRequest,
    LiveEvidenceConnectorManifest,
    LiveHTTPJSONEvidenceConnector,
    SUPPORT_CONNECTOR_CONTRACT_IDS,
    build_live_support_connectors,
    live_support_connector_manifests,
    run_live_support_connector,
)
from eval_pipeline.runtime import (
    RUNTIME_API_VERSION,
    AANACheckError,
    AANAError,
    AANAInputError,
    AANAValidationError,
    RuntimeResult,
    ValidationReport,
    check as check_typed,
    check_batch as check_batch_typed,
    check_batch_file as check_batch_file_typed,
    check_file as check_file_typed,
    check_request as check_request_typed,
    load_json_object,
    schemas as runtime_schemas,
    validate_batch as validate_batch_typed,
    validate_request as validate_request_typed,
)
from eval_pipeline.workflow_contract import WorkflowBatchRequest, WorkflowBatchResult, WorkflowRequest, WorkflowResult
from aana.sdk import (
    AANAClient,
    AANAClientError,
    CivicAANAClient,
    EnterpriseAANAClient,
    FamilyAANAClient,
    PersonalAANAClient,
    SupportAANAClient,
    build_agent_event,
    build_family_workflow_request,
    build_workflow_request,
    client,
    evidence_object,
    normalize_evidence,
)


__version__ = "0.1.0"


def check(
    adapter,
    request,
    candidate=None,
    evidence=None,
    constraints=None,
    allowed_actions=None,
    metadata=None,
    workflow_id=None,
    gallery_path=None,
):
    """Check a proposed AI output or action against an AANA workflow adapter.

    Returns a dictionary with gate_decision, recommended_action, violations,
    output, and the raw underlying adapter result.
    """

    kwargs = {
        "adapter": adapter,
        "request": request,
        "candidate": candidate,
        "evidence": evidence,
        "constraints": constraints,
        "allowed_actions": allowed_actions,
        "metadata": metadata,
        "workflow_id": workflow_id,
    }
    if gallery_path is not None:
        kwargs["gallery_path"] = gallery_path
    return check_workflow(**kwargs)


def check_request(workflow_request, gallery_path=None):
    """Check a Workflow Contract request dictionary or WorkflowRequest object."""

    if isinstance(workflow_request, WorkflowRequest):
        workflow_request = workflow_request.to_dict()
    if gallery_path is not None:
        return check_workflow_request(workflow_request, gallery_path=gallery_path)
    return check_workflow_request(workflow_request)


def check_batch(batch_request, gallery_path=None):
    """Check a Workflow Batch Contract dictionary or WorkflowBatchRequest object."""

    if isinstance(batch_request, WorkflowBatchRequest):
        batch_request = batch_request.to_dict()
    if gallery_path is not None:
        return check_workflow_batch(batch_request, gallery_path=gallery_path)
    return check_workflow_batch(batch_request)


def check_file(path, gallery_path=None):
    """Load a Workflow Contract JSON file and run the AANA gate."""

    with pathlib.Path(path).open(encoding="utf-8") as handle:
        workflow_request = json.load(handle)
    return check_request(workflow_request, gallery_path=gallery_path)


def check_batch_file(path, gallery_path=None):
    """Load a Workflow Batch Contract JSON file and run all AANA gates."""

    with pathlib.Path(path).open(encoding="utf-8") as handle:
        batch_request = json.load(handle)
    return check_batch(batch_request, gallery_path=gallery_path)


def result_object(result):
    """Convert a workflow result dictionary into a small typed object."""

    return WorkflowResult.from_dict(result)


def batch_result_object(result):
    """Convert a workflow batch result dictionary into a small typed object."""

    return WorkflowBatchResult.from_dict(result)


__all__ = [
    "WORKFLOW_CONTRACT_VERSION",
    "RUNTIME_API_VERSION",
    "AANACheckError",
    "AANAError",
    "AANAInputError",
    "AANAValidationError",
    "AANAClient",
    "AANAClientError",
    "CivicAANAClient",
    "CIVIC_CONNECTOR_CONTRACT_IDS",
    "CORE_CONNECTOR_CONTRACT_IDS",
    "SUPPORT_CONNECTOR_CONTRACT_IDS",
    "EnterpriseAANAClient",
    "EvidenceAuthContext",
    "EvidenceConnectorFailure",
    "EvidenceConnectorResult",
    "EvidenceFetchRequest",
    "LiveEvidenceConnectorManifest",
    "LiveHTTPJSONEvidenceConnector",
    "FamilyAANAClient",
    "PersonalAANAClient",
    "SupportAANAClient",
    "RuntimeResult",
    "ValidationReport",
    "WorkflowBatchRequest",
    "WorkflowBatchResult",
    "WorkflowRequest",
    "WorkflowResult",
    "append_audit_record",
    "apply_shadow_mode",
    "audit_aix_drift_report",
    "audit_aix_drift_report_file",
    "audit_dashboard",
    "audit_dashboard_file",
    "audit_event_check",
    "audit_redaction_report",
    "audit_workflow_batch",
    "audit_workflow_check",
    "check",
    "check_batch",
    "check_batch_file",
    "check_file",
    "check_request",
    "check_typed",
    "check_batch_typed",
    "check_batch_file_typed",
    "check_file_typed",
    "check_request_typed",
    "check_workflow",
    "check_workflow_batch",
    "check_workflow_request",
    "evidence_connector_contracts",
    "evidence_connector_marketplace",
    "evidence_integration_coverage",
    "evidence_integration_stubs",
    "evidence_mock_connector_matrix",
    "export_audit_metrics",
    "export_audit_metrics_file",
    "load_audit_records",
    "load_evidence_mock_fixtures",
    "load_evidence_registry",
    "load_json_object",
    "normalize_evidence_object",
    "run_evidence_mock_connector",
    "build_live_support_connectors",
    "live_support_connector_manifests",
    "run_live_support_connector",
    "support_evidence_boundary",
    "batch_result_object",
    "build_agent_event",
    "build_family_workflow_request",
    "build_workflow_request",
    "calculate_aix",
    "client",
    "decision_from_score",
    "result_object",
    "runtime_schemas",
    "schema_catalog",
    "normalize_evidence",
    "evidence_object",
    "summarize_audit_file",
    "summarize_audit_records",
    "validate_batch_typed",
    "validate_audit_file",
    "validate_audit_metrics_export",
    "validate_audit_records",
    "validate_workflow_batch_evidence",
    "validate_evidence_registry",
    "validate_request_typed",
    "validate_workflow_evidence",
    "validate_workflow_batch_request",
    "validate_workflow_request",
    "write_audit_reviewer_report",
]
