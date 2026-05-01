"""Minimal Python SDK surface for AANA workflow checks."""

from eval_pipeline.agent_api import (
    WORKFLOW_CONTRACT_VERSION,
    check_workflow,
    check_workflow_request,
    schema_catalog,
    validate_workflow_request,
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


__all__ = [
    "WORKFLOW_CONTRACT_VERSION",
    "check",
    "check_workflow",
    "check_workflow_request",
    "schema_catalog",
    "validate_workflow_request",
]
