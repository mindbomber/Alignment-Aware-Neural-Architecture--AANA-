"""Security and privacy checks for redacted MI artifacts."""

from __future__ import annotations

import re
from typing import Any


MI_PRIVACY_REVIEW_VERSION = "0.1"

RAW_PRIVATE_FIELD_NAMES = {
    "assumptions",
    "candidate",
    "claims",
    "customer_record",
    "customer_records",
    "developer_prompt",
    "evidence",
    "evidence_summary",
    "input",
    "message",
    "output",
    "payload",
    "private_record",
    "private_records",
    "prompt",
    "raw_evidence",
    "raw_message",
    "raw_prompt",
    "request",
    "safe_response",
    "secret",
    "secrets",
    "summary",
    "system_prompt",
    "text",
    "tool_result",
    "transcript",
    "user_prompt",
}

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE)),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
)

_ALLOWED_RAW_FIELD_PARENTS = {"fingerprints"}
_ALLOWED_RAW_FIELD_PATHS = {
    "$.fingerprints.message",
    "$.fingerprints.evidence",
}


def _json_path(parent: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{parent}[{key}]"
    if parent == "$":
        return f"$.{key}"
    return f"{parent}.{key}"


def _parent_name(path: str) -> str:
    if "." not in path:
        return ""
    return path.rsplit(".", 1)[-1]


def _is_allowed_raw_field(path: str, key: str) -> bool:
    if _json_path(path, key) in _ALLOWED_RAW_FIELD_PATHS:
        return True
    return _parent_name(path) in _ALLOWED_RAW_FIELD_PARENTS


def _secret_issues(value: str, path: str, artifact: str) -> list[dict[str, str]]:
    issues = []
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(value):
            issues.append(
                {
                    "artifact": artifact,
                    "path": path,
                    "message": f"Potential {name} leaked into redacted MI artifact.",
                }
            )
    return issues


def privacy_issues(
    value: Any,
    *,
    artifact: str = "artifact",
    path: str = "$",
) -> list[dict[str, str]]:
    """Return recursive privacy issues for a supposedly redacted MI artifact."""

    issues: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = _json_path(path, key_text)
            if key_text.lower() in RAW_PRIVATE_FIELD_NAMES and not _is_allowed_raw_field(path, key_text):
                issues.append(
                    {
                        "artifact": artifact,
                        "path": child_path,
                        "message": "Raw private content field is not allowed in redacted MI artifacts.",
                    }
                )
            issues.extend(privacy_issues(child, artifact=artifact, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(privacy_issues(child, artifact=artifact, path=_json_path(path, index)))
    elif isinstance(value, str):
        issues.extend(_secret_issues(value, path, artifact))
    return issues


def validate_redacted_artifact(value: Any, *, artifact: str = "artifact") -> dict[str, Any]:
    """Validate that an artifact contains no raw-content fields or secret-like strings."""

    issues = privacy_issues(value, artifact=artifact)
    return {
        "privacy_review_version": MI_PRIVACY_REVIEW_VERSION,
        "valid": not issues,
        "issue_count": len(issues),
        "issues": issues,
    }


def validate_redacted_artifacts(artifacts: dict[str, Any]) -> dict[str, Any]:
    """Validate a named collection of redacted artifacts."""

    issues = []
    for name, value in artifacts.items():
        issues.extend(privacy_issues(value, artifact=str(name)))
    return {
        "privacy_review_version": MI_PRIVACY_REVIEW_VERSION,
        "valid": not issues,
        "issue_count": len(issues),
        "issues": issues,
    }


__all__ = [
    "MI_PRIVACY_REVIEW_VERSION",
    "RAW_PRIVATE_FIELD_NAMES",
    "SECRET_PATTERNS",
    "privacy_issues",
    "validate_redacted_artifact",
    "validate_redacted_artifacts",
]
