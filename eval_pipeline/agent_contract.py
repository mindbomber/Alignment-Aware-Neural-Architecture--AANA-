"""Versioned AANA agent event and result contracts."""


AGENT_EVENT_VERSION = "0.1"
ALLOWED_ACTIONS = ["accept", "revise", "retrieve", "ask", "refuse", "defer"]
GATE_DECISIONS = ["pass", "block", "fail", "needs_adapter_implementation"]


AGENT_EVENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/agent-event.schema.json",
    "title": "AANA Agent Event",
    "description": "A planned AI-agent answer or action that AANA should check before execution.",
    "type": "object",
    "required": ["user_request"],
    "properties": {
        "event_version": {"type": "string", "examples": [AGENT_EVENT_VERSION]},
        "event_id": {"type": "string"},
        "agent": {"type": "string", "examples": ["openclaw"]},
        "adapter_id": {"type": "string", "examples": ["support_reply"]},
        "workflow": {"type": "string"},
        "user_request": {"type": "string", "minLength": 1},
        "prompt": {"type": "string", "minLength": 1},
        "candidate_action": {"type": "string"},
        "candidate_answer": {"type": "string"},
        "draft_response": {"type": "string"},
        "available_evidence": {"type": "array", "items": {"type": "string"}},
        "allowed_actions": {"type": "array", "items": {"type": "string", "enum": ALLOWED_ACTIONS}},
        "metadata": {"type": "object"},
    },
    "anyOf": [{"required": ["adapter_id"]}, {"required": ["workflow"]}],
    "additionalProperties": True,
}


AGENT_CHECK_RESULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/schemas/agent-check-result.schema.json",
    "title": "AANA Agent Check Result",
    "description": "The AANA gate result returned after checking an agent event.",
    "type": "object",
    "required": ["agent_check_version", "adapter_id", "gate_decision", "recommended_action", "safe_response"],
    "properties": {
        "agent_check_version": {"type": "string"},
        "agent": {"type": "string"},
        "adapter_id": {"type": "string"},
        "workflow": {"type": "string"},
        "event_id": {"type": "string"},
        "gate_decision": {"type": "string", "enum": GATE_DECISIONS},
        "recommended_action": {"type": "string", "enum": ALLOWED_ACTIONS},
        "candidate_gate": {"type": ["string", "null"]},
        "violations": {"type": "array", "items": {"type": "object"}},
        "safe_response": {"type": ["string", "null"]},
        "adapter_result": {"type": "object"},
    },
    "additionalProperties": True,
}


def schema_catalog():
    return {
        "agent_event": AGENT_EVENT_SCHEMA,
        "agent_check_result": AGENT_CHECK_RESULT_SCHEMA,
    }


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_agent_event(event):
    issues = []
    if not isinstance(event, dict):
        return {
            "valid": False,
            "errors": 1,
            "warnings": 0,
            "issues": [
                {
                    "level": "error",
                    "path": "$",
                    "message": "Agent event must be a JSON object.",
                }
            ],
        }

    if not (_is_nonempty_string(event.get("user_request")) or _is_nonempty_string(event.get("prompt"))):
        issues.append(
            {
                "level": "error",
                "path": "$.user_request",
                "message": "Agent event must include a non-empty user_request or prompt.",
            }
        )

    if not (_is_nonempty_string(event.get("adapter_id")) or _is_nonempty_string(event.get("workflow"))):
        issues.append(
            {
                "level": "error",
                "path": "$.adapter_id",
                "message": "Agent event must include adapter_id or workflow.",
            }
        )

    evidence = event.get("available_evidence")
    if evidence is not None and not (isinstance(evidence, list) and all(isinstance(item, str) for item in evidence)):
        issues.append(
            {
                "level": "error",
                "path": "$.available_evidence",
                "message": "available_evidence must be an array of strings when provided.",
            }
        )

    allowed_actions = event.get("allowed_actions")
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

    if event.get("event_version") and event.get("event_version") != AGENT_EVENT_VERSION:
        issues.append(
            {
                "level": "warning",
                "path": "$.event_version",
                "message": f"Expected event_version {AGENT_EVENT_VERSION}; got {event.get('event_version')}.",
            }
        )

    return {
        "valid": not any(issue["level"] == "error" for issue in issues),
        "errors": sum(1 for issue in issues if issue["level"] == "error"),
        "warnings": sum(1 for issue in issues if issue["level"] == "warning"),
        "issues": issues,
    }
