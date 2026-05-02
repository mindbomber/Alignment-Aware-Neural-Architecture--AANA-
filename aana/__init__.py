"""Minimal Python SDK surface for AANA workflow checks."""

import json
import pathlib

from eval_pipeline.agent_api import (
    WORKFLOW_CONTRACT_VERSION,
    check_workflow,
    check_workflow_batch,
    check_workflow_request,
    schema_catalog,
    validate_workflow_batch_request,
    validate_workflow_request,
)
from eval_pipeline.workflow_contract import WorkflowBatchRequest, WorkflowBatchResult, WorkflowRequest, WorkflowResult


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
    "WorkflowBatchRequest",
    "WorkflowBatchResult",
    "WorkflowRequest",
    "WorkflowResult",
    "check",
    "check_batch",
    "check_batch_file",
    "check_file",
    "check_request",
    "check_workflow",
    "check_workflow_batch",
    "check_workflow_request",
    "batch_result_object",
    "result_object",
    "schema_catalog",
    "validate_workflow_batch_request",
    "validate_workflow_request",
]
