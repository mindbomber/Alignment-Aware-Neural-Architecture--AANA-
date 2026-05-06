"""Registry of required MI contract shapes by communication boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


MI_CONTRACT_REGISTRY_VERSION = "0.1"
ACTIVE_MI_CONTRACT_VERSION = "0.1"
CORE_REQUIRED_FIELDS = (
    "contract_version",
    "handoff_id",
    "sender",
    "recipient",
    "message_schema",
    "message",
    "evidence",
    "constraint_map",
    "verifier_scores",
)
CORE_REQUIRED_CONSTRAINT_LAYERS = ("K_P", "K_B", "K_C")
CORE_REQUIRED_VERIFIER_LAYERS = ("P", "B", "C")


MI_CONTRACT_REGISTRY = {
    "agent_to_agent": {
        "registry_shape_version": "0.1",
        "compatible_contract_versions": ["0.1"],
        "sender_types": ["agent"],
        "recipient_types": ["agent"],
        "required_fields": list(CORE_REQUIRED_FIELDS),
        "required_constraint_layers": list(CORE_REQUIRED_CONSTRAINT_LAYERS),
        "required_verifier_layers": list(CORE_REQUIRED_VERIFIER_LAYERS),
        "evidence_required": True,
        "message_shape": {
            "required_fields": ["summary"],
            "allowed_kinds": ["natural_language", "candidate_answer", "draft_response", "workflow_output", "custom"],
        },
    },
    "agent_to_tool": {
        "registry_shape_version": "0.1",
        "compatible_contract_versions": ["0.1"],
        "sender_types": ["agent"],
        "recipient_types": ["tool", "connector", "adapter"],
        "required_fields": list(CORE_REQUIRED_FIELDS),
        "required_constraint_layers": list(CORE_REQUIRED_CONSTRAINT_LAYERS),
        "required_verifier_layers": list(CORE_REQUIRED_VERIFIER_LAYERS),
        "evidence_required": True,
        "message_shape": {
            "required_fields": ["summary"],
            "allowed_kinds": [
                "candidate_action",
                "candidate_answer",
                "tool_payload",
                "file_operation",
                "deployment_action",
                "permission_change",
                "data_export",
                "custom",
            ],
        },
    },
    "tool_to_agent": {
        "registry_shape_version": "0.1",
        "compatible_contract_versions": ["0.1"],
        "sender_types": ["tool", "connector", "adapter"],
        "recipient_types": ["agent"],
        "required_fields": list(CORE_REQUIRED_FIELDS),
        "required_constraint_layers": list(CORE_REQUIRED_CONSTRAINT_LAYERS),
        "required_verifier_layers": list(CORE_REQUIRED_VERIFIER_LAYERS),
        "evidence_required": True,
        "message_shape": {
            "required_fields": ["summary"],
            "allowed_kinds": ["tool_payload", "workflow_output", "evidence_summary", "custom"],
        },
    },
    "plugin_to_agent": {
        "registry_shape_version": "0.1",
        "compatible_contract_versions": ["0.1"],
        "sender_types": ["plugin"],
        "recipient_types": ["agent"],
        "required_fields": list(CORE_REQUIRED_FIELDS),
        "required_constraint_layers": list(CORE_REQUIRED_CONSTRAINT_LAYERS),
        "required_verifier_layers": list(CORE_REQUIRED_VERIFIER_LAYERS),
        "evidence_required": True,
        "message_shape": {
            "required_fields": ["summary"],
            "allowed_kinds": ["natural_language", "candidate_answer", "draft_response", "tool_payload", "custom"],
        },
    },
    "workflow_step_to_workflow_step": {
        "registry_shape_version": "0.1",
        "compatible_contract_versions": ["0.1"],
        "sender_types": ["workflow_step"],
        "recipient_types": ["workflow_step"],
        "required_fields": list(CORE_REQUIRED_FIELDS),
        "required_constraint_layers": list(CORE_REQUIRED_CONSTRAINT_LAYERS),
        "required_verifier_layers": list(CORE_REQUIRED_VERIFIER_LAYERS),
        "evidence_required": True,
        "message_shape": {
            "required_fields": ["summary"],
            "allowed_kinds": ["workflow_output", "candidate_action", "evidence_summary", "custom"],
        },
    },
}


def supported_boundaries() -> dict[str, tuple[set[str], set[str]]]:
    """Return the supported sender/recipient endpoint pairs."""

    return {
        boundary_type: (set(shape["sender_types"]), set(shape["recipient_types"]))
        for boundary_type, shape in MI_CONTRACT_REGISTRY.items()
    }


def mi_contract_registry() -> dict[str, Any]:
    """Return a deep copy of the active MI contract registry."""

    return {
        "mi_contract_registry_version": MI_CONTRACT_REGISTRY_VERSION,
        "active_contract_version": ACTIVE_MI_CONTRACT_VERSION,
        "boundaries": deepcopy(MI_CONTRACT_REGISTRY),
    }


def contract_shape_for_boundary(boundary_type: str) -> dict[str, Any] | None:
    """Return the registered contract shape for a supported boundary."""

    shape = MI_CONTRACT_REGISTRY.get(boundary_type)
    if shape is None:
        return None
    return deepcopy(shape)


def infer_registered_boundary_type(handoff: dict[str, Any]) -> str | None:
    """Infer a registry boundary type from sender and recipient endpoint types."""

    sender = handoff.get("sender") if isinstance(handoff, dict) else None
    recipient = handoff.get("recipient") if isinstance(handoff, dict) else None
    sender_type = sender.get("type") if isinstance(sender, dict) else None
    recipient_type = recipient.get("type") if isinstance(recipient, dict) else None
    if not isinstance(sender_type, str) or not isinstance(recipient_type, str):
        return None

    for boundary_type, shape in MI_CONTRACT_REGISTRY.items():
        if sender_type in shape["sender_types"] and recipient_type in shape["recipient_types"]:
            return boundary_type
    return None


def _declared_boundary_type(handoff: dict[str, Any]) -> str | None:
    metadata = handoff.get("metadata") if isinstance(handoff, dict) else None
    value = metadata.get("boundary_type") if isinstance(metadata, dict) else None
    return value if isinstance(value, str) and value.strip() else None


def _violation(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "id": code,
        "layer": "MI",
        "severity": "high",
        "message": message,
        "hard": True,
    }


def check_contract_version_compatibility(
    contract_version: str | None,
    boundary_type: str,
) -> dict[str, Any]:
    """Check whether a handoff contract version is supported for a boundary."""

    shape = MI_CONTRACT_REGISTRY.get(boundary_type)
    compatible_versions = shape.get("compatible_contract_versions", []) if isinstance(shape, dict) else []
    compatible = isinstance(contract_version, str) and contract_version in compatible_versions
    return {
        "mi_contract_registry_version": MI_CONTRACT_REGISTRY_VERSION,
        "boundary_type": boundary_type,
        "contract_version": contract_version,
        "compatible_contract_versions": list(compatible_versions),
        "compatible": compatible,
    }


def _missing_layers(payload: dict[str, Any], field: str, required_layers: list[str]) -> list[str]:
    block = payload.get(field)
    if not isinstance(block, dict):
        return list(required_layers)
    return [layer for layer in required_layers if layer not in block]


def validate_mi_contract_compatibility(handoff: dict[str, Any]) -> dict[str, Any]:
    """Validate a handoff against the registry shape for its boundary type."""

    payload = handoff if isinstance(handoff, dict) else {}
    declared = _declared_boundary_type(payload)
    inferred = infer_registered_boundary_type(payload)
    violations = []

    if declared and declared not in MI_CONTRACT_REGISTRY:
        violations.append(_violation("unsupported_boundary_type", f"Unsupported MI boundary_type: {declared}."))
        boundary_type = declared
        shape = None
    elif declared and inferred and declared != inferred:
        violations.append(
            _violation(
                "boundary_type_mismatch",
                f"Declared MI boundary_type {declared} does not match inferred boundary {inferred}.",
            )
        )
        boundary_type = declared
        shape = MI_CONTRACT_REGISTRY.get(boundary_type)
    else:
        boundary_type = declared or inferred
        shape = MI_CONTRACT_REGISTRY.get(boundary_type) if boundary_type else None

    if boundary_type is None:
        violations.append(
            _violation(
                "unsupported_endpoint_boundary",
                "Sender and recipient endpoint types do not form a supported MI boundary.",
            )
        )

    missing_fields: list[str] = []
    missing_constraint_layers: list[str] = []
    missing_verifier_layers: list[str] = []
    version_report = None

    if isinstance(shape, dict):
        required_fields = shape["required_fields"]
        missing_fields = [field for field in required_fields if field not in payload]
        for field in missing_fields:
            violations.append(
                _violation("missing_registry_required_field", f"Boundary {boundary_type} requires field: {field}.")
            )

        version_report = check_contract_version_compatibility(payload.get("contract_version"), str(boundary_type))
        if not version_report["compatible"]:
            violations.append(
                _violation(
                    "incompatible_contract_version",
                    (
                        f"Boundary {boundary_type} does not support contract_version "
                        f"{payload.get('contract_version')!r}."
                    ),
                )
            )

        missing_constraint_layers = _missing_layers(payload, "constraint_map", shape["required_constraint_layers"])
        for layer in missing_constraint_layers:
            violations.append(
                _violation("missing_registry_constraint_layer", f"Boundary {boundary_type} requires {layer}.")
            )

        missing_verifier_layers = _missing_layers(payload, "verifier_scores", shape["required_verifier_layers"])
        for layer in missing_verifier_layers:
            violations.append(
                _violation("missing_registry_verifier_layer", f"Boundary {boundary_type} requires {layer}.")
            )

    return {
        "mi_contract_registry_version": MI_CONTRACT_REGISTRY_VERSION,
        "boundary_type": boundary_type,
        "declared_boundary_type": declared,
        "inferred_boundary_type": inferred,
        "contract_version": payload.get("contract_version"),
        "registry_shape_version": shape.get("registry_shape_version") if isinstance(shape, dict) else None,
        "compatible": not violations,
        "version_compatible": version_report["compatible"] if isinstance(version_report, dict) else False,
        "missing_fields": missing_fields,
        "missing_constraint_layers": missing_constraint_layers,
        "missing_verifier_layers": missing_verifier_layers,
        "violations": violations,
    }


__all__ = [
    "ACTIVE_MI_CONTRACT_VERSION",
    "CORE_REQUIRED_CONSTRAINT_LAYERS",
    "CORE_REQUIRED_FIELDS",
    "CORE_REQUIRED_VERIFIER_LAYERS",
    "MI_CONTRACT_REGISTRY_VERSION",
    "check_contract_version_compatibility",
    "contract_shape_for_boundary",
    "infer_registered_boundary_type",
    "mi_contract_registry",
    "supported_boundaries",
    "validate_mi_contract_compatibility",
]
