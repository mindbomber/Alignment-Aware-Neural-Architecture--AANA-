"""Config-backed adapter generalization hints."""

from __future__ import annotations

import json
import pathlib
from functools import lru_cache
from typing import Any


ADAPTER_GENERALIZATION_CONFIG_VERSION = "aana.adapter_generalization_config.v1"
DEFAULT_CONFIG_PATH = pathlib.Path(__file__).resolve().parents[1] / "examples" / "adapter_generalization_config.json"
REQUIRED_TOOL_KEYS = {
    "read_policy_tools",
    "private_read_hints",
    "identity_bound_argument_keys",
    "write_hints",
    "required_write_hints",
    "risky_write_hints",
    "public_read_hints",
    "risk_domain_keywords",
}


def load_adapter_generalization_config(path: str | pathlib.Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Adapter generalization config must be a JSON object.")
    return payload


def validate_adapter_generalization_config(config: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if config.get("schema_version") != ADAPTER_GENERALIZATION_CONFIG_VERSION:
        issues.append({"level": "error", "path": "schema_version", "message": f"Must be {ADAPTER_GENERALIZATION_CONFIG_VERSION}."})
    tool = config.get("tool_classification")
    if not isinstance(tool, dict):
        issues.append({"level": "error", "path": "tool_classification", "message": "tool_classification must be an object."})
        tool = {}
    for key in sorted(REQUIRED_TOOL_KEYS):
        value = tool.get(key)
        if key == "risk_domain_keywords":
            if not isinstance(value, dict) or not value:
                issues.append({"level": "error", "path": f"tool_classification.{key}", "message": "risk_domain_keywords must be a non-empty object."})
            elif any(not isinstance(items, list) or not all(isinstance(item, str) and item for item in items) for items in value.values()):
                issues.append({"level": "error", "path": f"tool_classification.{key}", "message": "Each risk domain must map to non-empty string keywords."})
        elif not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
            issues.append({"level": "error", "path": f"tool_classification.{key}", "message": "Field must be a non-empty list of strings."})
    policy = config.get("blocked_literal_policy")
    if not isinstance(policy, dict):
        issues.append({"level": "error", "path": "blocked_literal_policy", "message": "blocked_literal_policy must be an object."})
    else:
        for key in ("no_benchmark_ids", "no_answer_keys", "no_task_specific_probe_literals"):
            if policy.get(key) is not True:
                issues.append({"level": "error", "path": f"blocked_literal_policy.{key}", "message": "Policy flag must be true."})
    errors = sum(1 for issue in issues if issue["level"] == "error")
    return {"valid": errors == 0, "errors": errors, "issues": issues}


@lru_cache(maxsize=4)
def _cached_default_config(path: str) -> dict[str, Any]:
    config = load_adapter_generalization_config(path)
    report = validate_adapter_generalization_config(config)
    if not report["valid"]:
        raise ValueError(f"Invalid adapter generalization config: {report['issues']}")
    return config


def default_adapter_generalization_config() -> dict[str, Any]:
    return _cached_default_config(str(DEFAULT_CONFIG_PATH))


def tool_classification_config() -> dict[str, Any]:
    return default_adapter_generalization_config()["tool_classification"]


def configured_set(key: str) -> set[str]:
    value = tool_classification_config()[key]
    if not isinstance(value, list):
        raise ValueError(f"Configured value is not a list: {key}")
    return set(value)


def configured_tuple(key: str) -> tuple[str, ...]:
    value = tool_classification_config()[key]
    if not isinstance(value, list):
        raise ValueError(f"Configured value is not a list: {key}")
    return tuple(value)


def risk_domain_keywords() -> dict[str, tuple[str, ...]]:
    value = tool_classification_config()["risk_domain_keywords"]
    return {str(key): tuple(str(item) for item in items) for key, items in value.items()}


__all__ = [
    "ADAPTER_GENERALIZATION_CONFIG_VERSION",
    "DEFAULT_CONFIG_PATH",
    "configured_set",
    "configured_tuple",
    "default_adapter_generalization_config",
    "load_adapter_generalization_config",
    "risk_domain_keywords",
    "tool_classification_config",
    "validate_adapter_generalization_config",
]
