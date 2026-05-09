"""Security hardening checks for AANA platform release hygiene."""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any


SECURITY_HARDENING_VERSION = "0.1"
REQUIRED_DEMO_BLOCKED_CAPABILITIES = {
    "send",
    "delete",
    "purchase",
    "deploy",
    "export",
}
REQUIRED_THREAT_MODEL_TERMS = {
    "malicious agent",
    "bypass",
    "prompt injection",
    "tool argument",
    "token",
    "audit",
    "fail closed",
    "shadow mode",
    "enforcement mode",
}


def _issue(level: str, path: str, message: str) -> dict[str, str]:
    return {"level": level, "path": path, "message": message}


def _read_text(root: pathlib.Path, relative_path: str) -> str:
    return (root / relative_path).read_text(encoding="utf-8")


def _load_json(root: pathlib.Path, relative_path: str) -> dict[str, Any]:
    payload = json.loads(_read_text(root, relative_path))
    if not isinstance(payload, dict):
        raise ValueError(f"{relative_path} must contain a JSON object.")
    return payload


def _contains_any(text: str, needles: set[str]) -> set[str]:
    lowered = text.lower()
    return {needle for needle in needles if needle in lowered}


def validate_ci_security(ci_text: str) -> list[dict[str, str]]:
    issues = []
    lowered = ci_text.lower()
    if "scripts/validate_secrets_scan.py" not in ci_text:
        issues.append(_issue("error", ".github/workflows/ci.yml", "CI must run the repo-local secret scanner."))
    if "gitleaks" not in lowered:
        issues.append(_issue("error", ".github/workflows/ci.yml", "CI must include a gitleaks-style history/content secret scan."))
    if "pip-audit" not in lowered:
        issues.append(_issue("error", ".github/workflows/ci.yml", "CI must run a dependency audit check with pip-audit."))
    upload_section = ci_text.split("Upload production profile audit artifacts", 1)[-1] if "Upload production profile audit artifacts" in ci_text else ""
    if "upload-artifact" in upload_section.lower() and "eval_outputs/audit/ci/aana-ci-audit.jsonl" in upload_section:
        issues.append(
            _issue(
                "error",
                ".github/workflows/ci.yml",
                "CI must not upload raw audit JSONL artifacts; upload metrics/manifests/reports only.",
            )
        )
    return issues


def validate_public_demo_safety(root: str | pathlib.Path = ".") -> list[dict[str, str]]:
    root_path = pathlib.Path(root)
    issues: list[dict[str, str]] = []
    manifest = _load_json(root_path, "docs/demo/scenarios.json")
    if manifest.get("synthetic_only") is not True:
        issues.append(_issue("error", "docs/demo/scenarios.json.synthetic_only", "Hosted demo must stay synthetic-only."))
    if manifest.get("real_side_effects") is not False:
        issues.append(_issue("error", "docs/demo/scenarios.json.real_side_effects", "Hosted demo must disable real side effects."))
    if manifest.get("secrets_required") is not False:
        issues.append(_issue("error", "docs/demo/scenarios.json.secrets_required", "Hosted demo must not require secrets."))
    blocked = {str(item).lower() for item in manifest.get("blocked_capabilities", [])}
    for required in sorted(REQUIRED_DEMO_BLOCKED_CAPABILITIES):
        if not any(required in item for item in blocked):
            issues.append(_issue("error", "docs/demo/scenarios.json.blocked_capabilities", f"Hosted demo must block {required} actions."))

    tool_demo = _read_text(root_path, "docs/tool-call-demo/app.js")
    if "SAFE_DEMO_MODE = true" not in tool_demo:
        issues.append(_issue("error", "docs/tool-call-demo/app.js", "Tool-call demo must declare SAFE_DEMO_MODE = true."))
    if "forbiddenExecutionActions" not in tool_demo:
        issues.append(_issue("error", "docs/tool-call-demo/app.js", "Tool-call demo must declare forbidden execution actions."))
    if re.search(r"\bfetch\s*\(", tool_demo):
        issues.append(_issue("error", "docs/tool-call-demo/app.js", "Tool-call demo must not call network APIs or execute tools."))
    return issues


def validate_threat_model(root: str | pathlib.Path = ".") -> list[dict[str, str]]:
    root_path = pathlib.Path(root)
    relative = "docs/aana-security-threat-model.md"
    path = root_path / relative
    if not path.exists():
        return [_issue("error", relative, "Threat model document is required.")]
    text = path.read_text(encoding="utf-8")
    covered = _contains_any(text, REQUIRED_THREAT_MODEL_TERMS)
    missing = sorted(REQUIRED_THREAT_MODEL_TERMS - covered)
    return [_issue("error", relative, f"Threat model missing required coverage: {missing}.")] if missing else []


def validate_security_hardening(root: str | pathlib.Path = ".") -> dict[str, Any]:
    root_path = pathlib.Path(root)
    issues: list[dict[str, str]] = []
    issues.extend(validate_ci_security(_read_text(root_path, ".github/workflows/ci.yml")))
    issues.extend(validate_public_demo_safety(root_path))
    issues.extend(validate_threat_model(root_path))
    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")
    return {
        "security_hardening_version": SECURITY_HARDENING_VERSION,
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
    }


__all__ = ["SECURITY_HARDENING_VERSION", "validate_security_hardening"]
