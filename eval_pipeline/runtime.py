"""Typed public runtime API for AANA workflow checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import pathlib
from typing import Any

from eval_pipeline import agent_api
from eval_pipeline.workflow_contract import (
    WORKFLOW_CONTRACT_VERSION,
    WorkflowBatchRequest,
    WorkflowBatchResult,
    WorkflowRequest,
    WorkflowResult,
)


RUNTIME_API_VERSION = "0.1"


class AANAError(Exception):
    """Base exception for the public AANA runtime API."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None, cause: Exception | None = None):
        super().__init__(message)
        self.details = details or {}
        self.__cause__ = cause

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_version": RUNTIME_API_VERSION,
            "type": self.__class__.__name__,
            "message": str(self),
            "details": self.details,
        }


class AANAInputError(AANAError):
    """Raised when a file, JSON payload, or API argument cannot be loaded."""


class AANAValidationError(AANAError):
    """Raised when a request fails a versioned AANA contract validator."""

    def __init__(self, message: str, *, report: dict[str, Any], details: dict[str, Any] | None = None):
        super().__init__(message, details=details or {})
        self.report = report

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["report"] = self.report
        return payload


class AANACheckError(AANAError):
    """Raised when a valid request cannot be checked by the runtime."""


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    errors: int
    warnings: int
    issues: list[dict[str, Any]] = field(default_factory=list)
    api_version: str = RUNTIME_API_VERSION

    @classmethod
    def from_dict(cls, report: dict[str, Any]) -> "ValidationReport":
        return cls(
            valid=bool(report.get("valid")),
            errors=int(report.get("errors", 0)),
            warnings=int(report.get("warnings", 0)),
            issues=list(report.get("issues", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeResult:
    kind: str
    result: WorkflowResult | WorkflowBatchResult
    ok: bool
    validation: ValidationReport | None = None
    api_version: str = RUNTIME_API_VERSION

    @classmethod
    def workflow(cls, result: dict[str, Any], validation: ValidationReport | None = None) -> "RuntimeResult":
        result_object = WorkflowResult.from_dict(result)
        return cls(kind="workflow", result=result_object, ok=result_object.passed, validation=validation)

    @classmethod
    def workflow_batch(cls, result: dict[str, Any], validation: ValidationReport | None = None) -> "RuntimeResult":
        result_object = WorkflowBatchResult.from_dict(result)
        return cls(kind="workflow_batch", result=result_object, ok=result_object.passed, validation=validation)

    @property
    def contract_version(self) -> str:
        return self.result.contract_version

    @property
    def passed(self) -> bool:
        return self.ok

    @property
    def gate_decision(self) -> str | None:
        if isinstance(self.result, WorkflowResult):
            return self.result.gate_decision
        return None

    @property
    def recommended_action(self) -> str | None:
        if isinstance(self.result, WorkflowResult):
            return self.result.recommended_action
        return None

    @property
    def aix(self) -> dict[str, Any] | None:
        if isinstance(self.result, WorkflowResult):
            return self.result.aix
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_version": self.api_version,
            "kind": self.kind,
            "ok": self.ok,
            "contract_version": self.contract_version,
            "validation": self.validation.to_dict() if self.validation else None,
            "result": self.result.to_dict(),
        }


def load_json_object(path: str | pathlib.Path) -> dict[str, Any]:
    """Load a JSON object and raise public runtime exceptions on failure."""

    resolved = pathlib.Path(path)
    try:
        with resolved.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise AANAInputError(
            f"JSON file does not exist: {resolved}",
            details={"path": str(resolved)},
            cause=exc,
        ) from exc
    except OSError as exc:
        raise AANAInputError(
            f"Could not read JSON file: {resolved}",
            details={"path": str(resolved), "reason": str(exc)},
            cause=exc,
        ) from exc
    except json.JSONDecodeError as exc:
        raise AANAInputError(
            f"Invalid JSON in file: {resolved}",
            details={"path": str(resolved), "line": exc.lineno, "column": exc.colno},
            cause=exc,
        ) from exc

    if not isinstance(data, dict):
        raise AANAInputError(
            f"JSON file must contain an object: {resolved}",
            details={"path": str(resolved), "actual_type": type(data).__name__},
        )
    return data


def _validation_message(report: dict[str, Any], fallback: str) -> str:
    messages = [issue["message"] for issue in report.get("issues", []) if issue.get("level") == "error"]
    return "; ".join(messages) if messages else fallback


def _raise_validation(report: dict[str, Any], *, kind: str) -> None:
    if report.get("valid"):
        return
    raise AANAValidationError(
        _validation_message(report, f"{kind} contract validation failed."),
        report=report,
        details={"kind": kind},
    )


def _coerce_workflow_request(workflow_request: WorkflowRequest | dict[str, Any]) -> dict[str, Any]:
    if isinstance(workflow_request, WorkflowRequest):
        return workflow_request.to_dict()
    if isinstance(workflow_request, dict):
        return workflow_request
    raise AANAInputError(
        "workflow_request must be a WorkflowRequest or dict.",
        details={"actual_type": type(workflow_request).__name__},
    )


def _coerce_batch_request(batch_request: WorkflowBatchRequest | dict[str, Any]) -> dict[str, Any]:
    if isinstance(batch_request, WorkflowBatchRequest):
        return batch_request.to_dict()
    if isinstance(batch_request, dict):
        return batch_request
    raise AANAInputError(
        "batch_request must be a WorkflowBatchRequest or dict.",
        details={"actual_type": type(batch_request).__name__},
    )


def validate_request(workflow_request: WorkflowRequest | dict[str, Any]) -> ValidationReport:
    """Validate a Workflow Request and return a typed validation report."""

    payload = _coerce_workflow_request(workflow_request)
    return ValidationReport.from_dict(agent_api.validate_workflow_request(payload))


def validate_batch(batch_request: WorkflowBatchRequest | dict[str, Any]) -> ValidationReport:
    """Validate a Workflow Batch Request and return a typed validation report."""

    payload = _coerce_batch_request(batch_request)
    return ValidationReport.from_dict(agent_api.validate_workflow_batch_request(payload))


def check(
    *,
    adapter: str,
    request: str,
    candidate: str | None = None,
    evidence: list[str | dict[str, Any]] | str | None = None,
    constraints: list[str] | str | None = None,
    allowed_actions: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    workflow_id: str | None = None,
    gallery_path: str | pathlib.Path | None = None,
) -> RuntimeResult:
    """Check a proposed output or action and return a versioned runtime result."""

    workflow_request = WorkflowRequest(
        adapter=adapter,
        request=request,
        candidate=candidate,
        evidence=evidence if isinstance(evidence, list) else [evidence] if isinstance(evidence, str) else [],
        constraints=constraints if isinstance(constraints, list) else [constraints] if isinstance(constraints, str) else [],
        allowed_actions=allowed_actions or None,
        metadata=metadata or {},
        workflow_id=workflow_id,
    )
    return check_request(workflow_request, gallery_path=gallery_path)


def check_request(
    workflow_request: WorkflowRequest | dict[str, Any],
    *,
    gallery_path: str | pathlib.Path | None = None,
) -> RuntimeResult:
    """Check a Workflow Request and raise public runtime exceptions on failure."""

    payload = _coerce_workflow_request(workflow_request)
    report = agent_api.validate_workflow_request(payload)
    validation = ValidationReport.from_dict(report)
    _raise_validation(report, kind="workflow_request")
    try:
        result = agent_api.check_workflow_request(
            payload,
            gallery_path=gallery_path or agent_api.DEFAULT_GALLERY,
        )
    except AANAError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise AANAInputError("Runtime input could not be loaded.", details={"reason": str(exc)}, cause=exc) from exc
    except ValueError as exc:
        raise AANACheckError(str(exc), details={"kind": "workflow_request"}, cause=exc) from exc
    return RuntimeResult.workflow(result, validation=validation)


def check_batch(
    batch_request: WorkflowBatchRequest | dict[str, Any],
    *,
    gallery_path: str | pathlib.Path | None = None,
) -> RuntimeResult:
    """Check a Workflow Batch Request and return a versioned runtime result."""

    payload = _coerce_batch_request(batch_request)
    report = agent_api.validate_workflow_batch_request(payload)
    validation = ValidationReport.from_dict(report)
    _raise_validation(report, kind="workflow_batch_request")
    try:
        result = agent_api.check_workflow_batch(
            payload,
            gallery_path=gallery_path or agent_api.DEFAULT_GALLERY,
        )
    except AANAError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise AANAInputError("Runtime input could not be loaded.", details={"reason": str(exc)}, cause=exc) from exc
    except ValueError as exc:
        raise AANACheckError(str(exc), details={"kind": "workflow_batch_request"}, cause=exc) from exc
    return RuntimeResult.workflow_batch(result, validation=validation)


def check_file(path: str | pathlib.Path, *, gallery_path: str | pathlib.Path | None = None) -> RuntimeResult:
    """Load and check a Workflow Request JSON file."""

    return check_request(load_json_object(path), gallery_path=gallery_path)


def check_batch_file(path: str | pathlib.Path, *, gallery_path: str | pathlib.Path | None = None) -> RuntimeResult:
    """Load and check a Workflow Batch Request JSON file."""

    return check_batch(load_json_object(path), gallery_path=gallery_path)


def schemas() -> dict[str, Any]:
    """Return the versioned public schema catalog."""

    return agent_api.schema_catalog()


__all__ = [
    "RUNTIME_API_VERSION",
    "AANAError",
    "AANAInputError",
    "AANAValidationError",
    "AANACheckError",
    "RuntimeResult",
    "ValidationReport",
    "WorkflowRequest",
    "WorkflowResult",
    "WorkflowBatchRequest",
    "WorkflowBatchResult",
    "WORKFLOW_CONTRACT_VERSION",
    "check",
    "check_request",
    "check_batch",
    "check_file",
    "check_batch_file",
    "load_json_object",
    "schemas",
    "validate_request",
    "validate_batch",
]
