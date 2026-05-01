"""Minimal Python SDK surface for AANA workflow checks."""

import json
import pathlib

from eval_pipeline.agent_api import (
    WORKFLOW_CONTRACT_VERSION,
    check_workflow,
    check_workflow_request,
    schema_catalog,
    validate_workflow_request,
)
from eval_pipeline.workflow_contract import WorkflowRequest, WorkflowResult


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


def check_file(path, gallery_path=None):
    """Load a Workflow Contract JSON file and run the AANA gate."""

    with pathlib.Path(path).open(encoding="utf-8") as handle:
        workflow_request = json.load(handle)
    return check_request(workflow_request, gallery_path=gallery_path)


def result_object(result):
    """Convert a workflow result dictionary into a small typed object."""

    return WorkflowResult.from_dict(result)


__all__ = [
    "WORKFLOW_CONTRACT_VERSION",
    "WorkflowRequest",
    "WorkflowResult",
    "check",
    "check_file",
    "check_request",
    "check_workflow",
    "check_workflow_request",
    "result_object",
    "schema_catalog",
    "validate_workflow_request",
]
