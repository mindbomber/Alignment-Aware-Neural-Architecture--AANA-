"""Versioned AANA workflow request and result contracts."""

from dataclasses import asdict, dataclass, field

from eval_pipeline import agent_contract


WORKFLOW_CONTRACT_VERSION = "0.1"
ALLOWED_ACTIONS = agent_contract.ALLOWED_ACTIONS
GATE_DECISIONS = agent_contract.GATE_DECISIONS
DEFAULT_ALLOWED_ACTIONS = ["accept", "revise", "retrieve", "ask", "defer", "refuse"]


@dataclass
class WorkflowRequest:
    adapter: str
    request: str
    candidate: str | None = None
    evidence: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_ACTIONS))
    metadata: dict = field(default_factory=dict)
    workflow_id: str | None = None
    contract_version: str = WORKFLOW_CONTRACT_VERSION

    @classmethod
    def from_dict(cls, data):
        normalized = normalize_workflow_request(
            adapter=data.get("adapter"),
            request=data.get("request"),
            candidate=data.get("candidate"),
            evidence=data.get("evidence"),
            constraints=data.get("constraints"),
            allowed_actions=data.get("allowed_actions"),
            metadata=data.get("metadata"),
            workflow_id=data.get("workflow_id"),
        )
        if data.get("contract_version"):
            normalized["contract_version"] = data.get("contract_version")
        return cls(**normalized)

    def to_dict(self):
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class WorkflowResult:
    adapter: str
    gate_decision: str
    recommended_action: str
    output: str | None
    workflow_id: str | None = None
    workflow: str | None = None
    candidate_gate: str | None = None
    violations: list[dict] = field(default_factory=list)
    raw_result: dict = field(default_factory=dict)
    contract_version: str = WORKFLOW_CONTRACT_VERSION

    @classmethod
    def from_dict(cls, data):
        return cls(
            contract_version=data.get("contract_version", WORKFLOW_CONTRACT_VERSION),
            workflow_id=data.get("workflow_id"),
            adapter=data.get("adapter"),
            workflow=data.get("workflow"),
            gate_decision=data.get("gate_decision"),
            recommended_action=data.get("recommended_action"),
            candidate_gate=data.get("candidate_gate"),
            violations=data.get("violations", []),
            output=data.get("output"),
            raw_result=data.get("raw_result", {}),
        )

    @property
    def passed(self):
        return self.gate_decision == "pass"

    def to_dict(self):
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class WorkflowBatchRequest:
    requests: list[WorkflowRequest | dict]
    batch_id: str | None = None
    contract_version: str = WORKFLOW_CONTRACT_VERSION

    @classmethod
    def from_dict(cls, data):
        requests = []
        for item in data.get("requests", []):
            if isinstance(item, WorkflowRequest):
                requests.append(item)
            else:
                requests.append(WorkflowRequest.from_dict(item))
        return cls(
            contract_version=data.get("contract_version", WORKFLOW_CONTRACT_VERSION),
            batch_id=data.get("batch_id"),
            requests=requests,
        )

    def to_dict(self):
        payload = {
            "contract_version": self.contract_version,
            "batch_id": self.batch_id,
            "requests": [item.to_dict() if isinstance(item, WorkflowRequest) else item for item in self.requests],
        }
        return {key: value for key, value in payload.items() if value is not None}


@dataclass
class WorkflowBatchResult:
    results: list[WorkflowResult | dict]
    batch_id: str | None = None
    summary: dict = field(default_factory=dict)
    contract_version: str = WORKFLOW_CONTRACT_VERSION

    @classmethod
    def from_dict(cls, data):
        results = []
        for item in data.get("results", []):
            if isinstance(item, WorkflowResult):
                results.append(item)
            else:
                results.append(WorkflowResult.from_dict(item))
        return cls(
            contract_version=data.get("contract_version", WORKFLOW_CONTRACT_VERSION),
            batch_id=data.get("batch_id"),
            summary=data.get("summary", {}),
            results=results,
        )

    @property
    def passed(self):
        return self.summary.get("failed", 0) == 0

    def to_dict(self):
        payload = {
            "contract_version": self.contract_version,
            "batch_id": self.batch_id,
            "summary": self.summary,
            "results": [item.to_dict() if isinstance(item, WorkflowResult) else item for item in self.results],
        }
        return {key: value for key, value in payload.items() if value is not None}


WORKFLOW_REQUEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/workflow-request.schema.json",
    "title": "AANA Workflow Request",
    "description": "A proposed AI output or action that AANA should verify before it is used.",
    "type": "object",
    "required": ["adapter", "request"],
    "properties": {
        "contract_version": {"type": "string", "examples": [WORKFLOW_CONTRACT_VERSION]},
        "workflow_id": {"type": "string"},
        "adapter": {"type": "string", "examples": ["research_summary"]},
        "request": {"type": "string", "minLength": 1},
        "candidate": {"type": ["string", "null"]},
        "evidence": {
            "oneOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}},
            ]
        },
        "constraints": {
            "oneOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}},
            ]
        },
        "allowed_actions": {"type": "array", "items": {"type": "string", "enum": ALLOWED_ACTIONS}},
        "metadata": {"type": "object"},
    },
    "additionalProperties": True,
}


WORKFLOW_BATCH_REQUEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/workflow-batch-request.schema.json",
    "title": "AANA Workflow Batch Request",
    "description": "A batch of proposed AI outputs or actions that AANA should verify.",
    "type": "object",
    "required": ["requests"],
    "properties": {
        "contract_version": {"type": "string", "examples": [WORKFLOW_CONTRACT_VERSION]},
        "batch_id": {"type": "string"},
        "requests": {"type": "array", "minItems": 1, "items": WORKFLOW_REQUEST_SCHEMA},
    },
    "additionalProperties": True,
}


WORKFLOW_RESULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/workflow-result.schema.json",
    "title": "AANA Workflow Result",
    "description": "The AANA gate result returned for a workflow request.",
    "type": "object",
    "required": ["contract_version", "adapter", "gate_decision", "recommended_action", "output"],
    "properties": {
        "contract_version": {"type": "string"},
        "workflow_id": {"type": ["string", "null"]},
        "adapter": {"type": "string"},
        "workflow": {"type": "string"},
        "gate_decision": {"type": "string", "enum": GATE_DECISIONS},
        "recommended_action": {"type": "string", "enum": ALLOWED_ACTIONS},
        "candidate_gate": {"type": ["string", "null"]},
        "violations": {"type": "array", "items": {"type": "object"}},
        "output": {"type": ["string", "null"]},
        "raw_result": {"type": "object"},
    },
    "additionalProperties": True,
}


WORKFLOW_BATCH_RESULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/workflow-batch-result.schema.json",
    "title": "AANA Workflow Batch Result",
    "description": "A summary and per-item AANA gate results for a workflow batch.",
    "type": "object",
    "required": ["contract_version", "summary", "results"],
    "properties": {
        "contract_version": {"type": "string"},
        "batch_id": {"type": ["string", "null"]},
        "summary": {
            "type": "object",
            "required": ["total", "passed", "failed"],
            "properties": {
                "total": {"type": "integer"},
                "passed": {"type": "integer"},
                "failed": {"type": "integer"},
                "recommended_actions": {"type": "object"},
                "gate_decisions": {"type": "object"},
            },
        },
        "results": {"type": "array", "items": WORKFLOW_RESULT_SCHEMA},
    },
    "additionalProperties": True,
}


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _string_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return None


def allowed_actions_or_default(value):
    if value is None:
        return list(DEFAULT_ALLOWED_ACTIONS)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return value


def action_within_allowed(action, allowed_actions):
    allowed = allowed_actions_or_default(allowed_actions)
    if not isinstance(allowed, list) or not allowed:
        return action, None
    if action in allowed:
        return action, None
    for fallback in ("defer", "ask", "refuse", "revise", "accept", "retrieve"):
        if fallback in allowed:
            return fallback, {
                "code": "recommended_action_not_allowed",
                "severity": "medium",
                "message": f"Adapter recommended {action!r}, but the workflow allows only: {', '.join(allowed)}. Using {fallback!r}.",
            }
    return action, None


def validate_workflow_request(request):
    issues = []
    if not isinstance(request, dict):
        return {
            "valid": False,
            "errors": 1,
            "warnings": 0,
            "issues": [
                {
                    "level": "error",
                    "path": "$",
                    "message": "Workflow request must be a JSON object.",
                }
            ],
        }

    if not _is_nonempty_string(request.get("adapter")):
        issues.append(
            {
                "level": "error",
                "path": "$.adapter",
                "message": "Workflow request must include a non-empty adapter.",
            }
        )

    if not _is_nonempty_string(request.get("request")):
        issues.append(
            {
                "level": "error",
                "path": "$.request",
                "message": "Workflow request must include a non-empty request.",
            }
        )

    if request.get("candidate") is not None and not isinstance(request.get("candidate"), str):
        issues.append(
            {
                "level": "error",
                "path": "$.candidate",
                "message": "candidate must be a string or null when provided.",
            }
        )

    if request.get("workflow_id") is not None and not isinstance(request.get("workflow_id"), str):
        issues.append(
            {
                "level": "error",
                "path": "$.workflow_id",
                "message": "workflow_id must be a string when provided.",
            }
        )

    if request.get("metadata") is not None and not isinstance(request.get("metadata"), dict):
        issues.append(
            {
                "level": "error",
                "path": "$.metadata",
                "message": "metadata must be an object when provided.",
            }
        )

    for key in ("evidence", "constraints"):
        if _string_list(request.get(key)) is None:
            issues.append(
                {
                    "level": "error",
                    "path": f"$.{key}",
                    "message": f"{key} must be a string or array of strings when provided.",
                }
            )

    allowed_actions = request.get("allowed_actions")
    if allowed_actions is not None:
        if not isinstance(allowed_actions, list) or not all(isinstance(item, str) for item in allowed_actions):
            issues.append(
                {
                    "level": "error",
                    "path": "$.allowed_actions",
                    "message": "allowed_actions must be an array of strings when provided.",
                }
            )
        else:
            unknown = sorted(set(allowed_actions) - set(ALLOWED_ACTIONS))
            if unknown:
                issues.append(
                    {
                        "level": "error",
                        "path": "$.allowed_actions",
                        "message": "allowed_actions contains unsupported actions: " + ", ".join(unknown),
                    }
                )

    if request.get("contract_version") and request.get("contract_version") != WORKFLOW_CONTRACT_VERSION:
        issues.append(
            {
                "level": "warning",
                "path": "$.contract_version",
                "message": f"Expected contract_version {WORKFLOW_CONTRACT_VERSION}; got {request.get('contract_version')}.",
            }
        )

    return {
        "valid": not any(issue["level"] == "error" for issue in issues),
        "errors": sum(1 for issue in issues if issue["level"] == "error"),
        "warnings": sum(1 for issue in issues if issue["level"] == "warning"),
        "issues": issues,
    }


def validate_workflow_batch_request(batch_request):
    issues = []
    if not isinstance(batch_request, dict):
        return {
            "valid": False,
            "errors": 1,
            "warnings": 0,
            "issues": [
                {
                    "level": "error",
                    "path": "$",
                    "message": "Workflow batch request must be a JSON object.",
                }
            ],
        }

    if batch_request.get("batch_id") is not None and not isinstance(batch_request.get("batch_id"), str):
        issues.append(
            {
                "level": "error",
                "path": "$.batch_id",
                "message": "batch_id must be a string when provided.",
            }
        )

    requests = batch_request.get("requests")
    if not isinstance(requests, list) or not requests:
        issues.append(
            {
                "level": "error",
                "path": "$.requests",
                "message": "Workflow batch request must include a non-empty requests array.",
            }
        )
    elif not all(isinstance(item, dict) for item in requests):
        issues.append(
            {
                "level": "error",
                "path": "$.requests",
                "message": "Every workflow batch request item must be a JSON object.",
            }
        )
    else:
        for index, request in enumerate(requests):
            report = validate_workflow_request(request)
            for issue in report["issues"]:
                issues.append({**issue, "path": f"$.requests[{index}]{issue['path'][1:]}"})

    if batch_request.get("contract_version") and batch_request.get("contract_version") != WORKFLOW_CONTRACT_VERSION:
        issues.append(
            {
                "level": "warning",
                "path": "$.contract_version",
                "message": f"Expected contract_version {WORKFLOW_CONTRACT_VERSION}; got {batch_request.get('contract_version')}.",
            }
        )

    return {
        "valid": not any(issue["level"] == "error" for issue in issues),
        "errors": sum(1 for issue in issues if issue["level"] == "error"),
        "warnings": sum(1 for issue in issues if issue["level"] == "warning"),
        "issues": issues,
    }


def normalize_workflow_request(
    adapter,
    request,
    candidate=None,
    evidence=None,
    constraints=None,
    allowed_actions=None,
    metadata=None,
    workflow_id=None,
):
    evidence_items = _string_list(evidence)
    constraints_items = _string_list(constraints)
    payload = {
        "contract_version": WORKFLOW_CONTRACT_VERSION,
        "workflow_id": workflow_id,
        "adapter": adapter,
        "request": request,
        "candidate": candidate,
        "evidence": evidence_items if evidence_items is not None else evidence,
        "constraints": constraints_items if constraints_items is not None else constraints,
        "allowed_actions": allowed_actions_or_default(allowed_actions),
        "metadata": metadata or {},
    }
    return {key: value for key, value in payload.items() if value is not None}


def workflow_request_to_agent_event(request, agent="workflow"):
    evidence = _string_list(request.get("evidence")) or []
    constraints = _string_list(request.get("constraints")) or []
    if constraints:
        evidence = evidence + [f"Constraint to preserve: {item}" for item in constraints]

    metadata = request.get("metadata", {}) if isinstance(request.get("metadata"), dict) else {}
    metadata = {
        **metadata,
        "workflow_contract_version": request.get("contract_version", WORKFLOW_CONTRACT_VERSION),
    }

    return {
        "event_version": agent_contract.AGENT_EVENT_VERSION,
        "event_id": request.get("workflow_id"),
        "agent": agent,
        "adapter_id": request.get("adapter"),
        "user_request": request.get("request"),
        "candidate_action": request.get("candidate"),
        "available_evidence": evidence,
        "allowed_actions": request.get("allowed_actions", list(DEFAULT_ALLOWED_ACTIONS)),
        "metadata": metadata,
    }


def schema_catalog():
    return {
        "workflow_request": WORKFLOW_REQUEST_SCHEMA,
        "workflow_batch_request": WORKFLOW_BATCH_REQUEST_SCHEMA,
        "workflow_result": WORKFLOW_RESULT_SCHEMA,
        "workflow_batch_result": WORKFLOW_BATCH_RESULT_SCHEMA,
    }
