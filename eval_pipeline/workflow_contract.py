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
        "workflow_result": WORKFLOW_RESULT_SCHEMA,
    }
