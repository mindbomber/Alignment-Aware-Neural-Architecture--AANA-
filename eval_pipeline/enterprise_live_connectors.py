"""Production-candidate support/email/ticket connector clients.

The clients in this module are real HTTP JSON connector wrappers: when a
manifest is live-approved they can call customer-owned endpoints. They are
still fail-closed by default: dry-run is the default mode, writes are disabled
unless the connector and AANA gate both explicitly allow execution, and returned
results contain fingerprints/metadata rather than raw customer content.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
ENTERPRISE_LIVE_CONNECTORS_VERSION = "0.1"
ENTERPRISE_LIVE_CONNECTORS_TYPE = "aana_enterprise_support_live_connectors"
DEFAULT_ENTERPRISE_LIVE_CONNECTORS_PATH = ROOT / "examples" / "enterprise_support_live_connectors.json"
SUPPORT_ACTION_CONNECTOR_IDS = ("crm_support", "email_send", "ticketing")
EXECUTION_MODES = ("dry_run", "shadow", "enforce")


class EnterpriseConnectorError(RuntimeError):
    """Raised when a live enterprise connector cannot safely run."""


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _fingerprint(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _load_json(path: str | pathlib.Path) -> dict[str, Any]:
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _write_json(path: str | pathlib.Path, payload: dict[str, Any]) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def aana_allows_execution(result: dict[str, Any] | None) -> dict[str, Any]:
    """Return the fail-closed execution decision for an AANA runtime result."""

    result = result if isinstance(result, dict) else {}
    aix = result.get("aix") if isinstance(result.get("aix"), dict) else {}
    hard_blockers = list(result.get("hard_blockers") or []) + list(aix.get("hard_blockers") or [])
    validation_errors = result.get("validation_errors") if isinstance(result.get("validation_errors"), list) else []
    allows = (
        result.get("gate_decision") == "pass"
        and result.get("recommended_action") == "accept"
        and not hard_blockers
        and not validation_errors
    )
    blockers: list[str] = []
    if result.get("gate_decision") != "pass":
        blockers.append("gate_decision_not_pass")
    if result.get("recommended_action") != "accept":
        blockers.append("recommended_action_not_accept")
    if hard_blockers:
        blockers.append("hard_blockers_present")
    if validation_errors:
        blockers.append("validation_errors_present")
    return {
        "allows_execution": allows,
        "fail_closed": not allows,
        "blockers": blockers,
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "aix_decision": aix.get("decision"),
        "aix_score": aix.get("score"),
        "hard_blocker_count": len(hard_blockers),
        "validation_error_count": len(validation_errors),
    }


@dataclass(frozen=True)
class EnterpriseConnectorManifest:
    connector_id: str
    display_name: str
    base_url: str
    endpoint_path: str
    environment: str
    owner: str
    auth_token_env: str | None = None
    approval_status: str = "pending"
    source_mode: str = "dry_run"
    timeout_seconds: int = 10
    write_enabled: bool = False
    supports_shadow_reads: bool = True

    @classmethod
    def from_value(cls, value: dict[str, Any]) -> "EnterpriseConnectorManifest":
        if not isinstance(value, dict):
            raise ValueError("Connector manifest must be an object.")
        connector_id = str(value.get("connector_id") or "").strip()
        base_url = str(value.get("base_url") or "").strip()
        endpoint_path = str(value.get("endpoint_path") or "").strip()
        if not connector_id:
            raise ValueError("Connector manifest requires connector_id.")
        if connector_id not in SUPPORT_ACTION_CONNECTOR_IDS:
            raise ValueError(f"Unsupported support connector_id: {connector_id!r}.")
        if not base_url:
            raise ValueError(f"Connector {connector_id!r} requires base_url.")
        if not endpoint_path.startswith("/"):
            raise ValueError(f"Connector {connector_id!r} endpoint_path must start with '/'.")
        return cls(
            connector_id=connector_id,
            display_name=str(value.get("display_name") or connector_id),
            base_url=base_url.rstrip("/"),
            endpoint_path=endpoint_path,
            environment=str(value.get("environment") or "pilot"),
            owner=str(value.get("owner") or "unassigned"),
            auth_token_env=value.get("auth_token_env"),
            approval_status=str(value.get("approval_status") or "pending"),
            source_mode=str(value.get("source_mode") or "dry_run"),
            timeout_seconds=int(value.get("timeout_seconds") or 10),
            write_enabled=bool(value.get("write_enabled")),
            supports_shadow_reads=bool(value.get("supports_shadow_reads", True)),
        )

    @property
    def endpoint_url(self) -> str:
        return f"{self.base_url}{self.endpoint_path}"

    @property
    def live_approved(self) -> bool:
        return self.approval_status in {"approved", "live_approved"} and self.source_mode in {"live", "shadow"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "display_name": self.display_name,
            "base_url": self.base_url,
            "endpoint_path": self.endpoint_path,
            "environment": self.environment,
            "owner": self.owner,
            "auth_token_env": self.auth_token_env,
            "approval_status": self.approval_status,
            "source_mode": self.source_mode,
            "timeout_seconds": self.timeout_seconds,
            "write_enabled": self.write_enabled,
            "supports_shadow_reads": self.supports_shadow_reads,
            "live_approved": self.live_approved,
        }


@dataclass
class EnterpriseHTTPJSONConnector:
    manifest: EnterpriseConnectorManifest
    transport: Any | None = None

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.transport is not None:
            response = self.transport(self.manifest, payload)
            if not isinstance(response, dict):
                raise EnterpriseConnectorError("Connector transport must return a JSON object.")
            return response

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.manifest.auth_token_env:
            token = os.environ.get(self.manifest.auth_token_env)
            if not token:
                raise EnterpriseConnectorError(f"Missing token env {self.manifest.auth_token_env!r}.")
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            self.manifest.endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.manifest.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise EnterpriseConnectorError(f"Connector request failed for {self.manifest.connector_id}: {exc}") from exc
        if not isinstance(data, dict):
            raise EnterpriseConnectorError("Connector response must be a JSON object.")
        return data

    def fetch_support_case(self, *, case_ref: str, metadata: dict[str, Any] | None = None, mode: str = "dry_run") -> dict[str, Any]:
        mode = _validate_mode(mode)
        payload = {
            "operation": "fetch_support_case_context",
            "case_ref": case_ref,
            "metadata": metadata or {},
        }
        return self._run_read(operation="fetch_support_case_context", payload=payload, mode=mode)

    def send_email(self, *, email_action: dict[str, Any], aana_result: dict[str, Any], mode: str = "dry_run") -> dict[str, Any]:
        payload = {"operation": "send_email", "email_action": email_action}
        return self._run_write(operation="send_email", payload=payload, aana_result=aana_result, mode=mode)

    def update_ticket(self, *, ticket_action: dict[str, Any], aana_result: dict[str, Any], mode: str = "dry_run") -> dict[str, Any]:
        payload = {"operation": "update_ticket", "ticket_action": ticket_action}
        return self._run_write(operation="update_ticket", payload=payload, aana_result=aana_result, mode=mode)

    def _base_result(self, *, operation: str, payload: dict[str, Any], mode: str) -> dict[str, Any]:
        return {
            "enterprise_live_connectors_version": ENTERPRISE_LIVE_CONNECTORS_VERSION,
            "connector_id": self.manifest.connector_id,
            "operation": operation,
            "execution_mode": mode,
            "executed": False,
            "created_at": _utc_now(),
            "request_fingerprint": _fingerprint(payload),
            "raw_payload_logged": False,
            "manifest": self.manifest.to_dict(),
        }

    def _run_read(self, *, operation: str, payload: dict[str, Any], mode: str) -> dict[str, Any]:
        result = self._base_result(operation=operation, payload=payload, mode=mode)
        if mode == "dry_run":
            return {
                **result,
                "valid": True,
                "executed": False,
                "route": "dry_run",
                "response_metadata": {"dry_run": True},
                "evidence": [],
            }
        if not self.manifest.live_approved:
            return {
                **result,
                "valid": False,
                "route": "defer",
                "blockers": ["connector_not_live_approved"],
                "evidence": [],
            }
        try:
            response = self._post(payload)
        except EnterpriseConnectorError as exc:
            return {
                **result,
                "valid": False,
                "route": "defer",
                "blockers": ["connector_unavailable"],
                "error": str(exc),
                "evidence": [],
            }
        evidence = response.get("evidence") if isinstance(response.get("evidence"), list) else []
        return {
            **result,
            "valid": True,
            "executed": True,
            "route": "accept",
            "response_metadata": _response_metadata(response),
            "evidence": evidence,
        }

    def _run_write(self, *, operation: str, payload: dict[str, Any], aana_result: dict[str, Any], mode: str) -> dict[str, Any]:
        mode = _validate_mode(mode)
        result = self._base_result(operation=operation, payload=payload, mode=mode)
        execution_check = aana_allows_execution(aana_result)
        base = {**result, "aana_execution_check": execution_check}
        if not execution_check["allows_execution"]:
            return {
                **base,
                "valid": False,
                "route": "defer",
                "blockers": execution_check["blockers"],
            }
        if mode in {"dry_run", "shadow"}:
            return {
                **base,
                "valid": True,
                "route": "observe_only" if mode == "shadow" else "dry_run",
                "response_metadata": {mode: True},
            }
        blockers = []
        if not self.manifest.live_approved:
            blockers.append("connector_not_live_approved")
        if not self.manifest.write_enabled:
            blockers.append("connector_write_not_enabled")
        if blockers:
            return {
                **base,
                "valid": False,
                "route": "defer",
                "blockers": blockers,
            }
        try:
            response = self._post(payload)
        except EnterpriseConnectorError as exc:
            return {
                **base,
                "valid": False,
                "route": "defer",
                "blockers": ["connector_unavailable"],
                "error": str(exc),
            }
        return {
            **base,
            "valid": True,
            "executed": True,
            "route": "accept",
            "response_metadata": _response_metadata(response),
        }


def _validate_mode(mode: str) -> str:
    mode = str(mode or "dry_run")
    if mode not in EXECUTION_MODES:
        raise ValueError(f"Unsupported execution mode {mode!r}; expected one of {EXECUTION_MODES}.")
    return mode


def _response_metadata(response: dict[str, Any]) -> dict[str, Any]:
    allowed = {"status", "status_code", "request_id", "external_id", "message_id", "ticket_update_id", "evidence_count"}
    metadata = {key: response[key] for key in sorted(allowed) if key in response}
    if "evidence" in response and "evidence_count" not in metadata and isinstance(response.get("evidence"), list):
        metadata["evidence_count"] = len(response["evidence"])
    metadata["response_fingerprint"] = _fingerprint(response)
    return metadata


def load_enterprise_live_connector_config(path: str | pathlib.Path = DEFAULT_ENTERPRISE_LIVE_CONNECTORS_PATH) -> dict[str, Any]:
    return _load_json(path)


def enterprise_connector_manifests(config: dict[str, Any]) -> dict[str, EnterpriseConnectorManifest]:
    raw = config.get("connectors") if isinstance(config, dict) else None
    if not isinstance(raw, list):
        raise ValueError("Enterprise live connector config requires a connectors array.")
    manifests = [EnterpriseConnectorManifest.from_value(item) for item in raw]
    return {manifest.connector_id: manifest for manifest in manifests}


def build_enterprise_support_connectors(
    config: dict[str, Any] | None = None,
    *,
    transports: dict[str, Any] | None = None,
) -> dict[str, EnterpriseHTTPJSONConnector]:
    config = config or load_enterprise_live_connector_config()
    transports = transports or {}
    return {
        connector_id: EnterpriseHTTPJSONConnector(manifest=manifest, transport=transports.get(connector_id))
        for connector_id, manifest in enterprise_connector_manifests(config).items()
    }


def validate_enterprise_live_connector_config(config: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        manifests = enterprise_connector_manifests(config)
    except (ValueError, TypeError) as exc:
        return {"valid": False, "issues": [{"level": "error", "path": "connectors", "message": str(exc)}]}
    missing = sorted(set(SUPPORT_ACTION_CONNECTOR_IDS) - set(manifests))
    for connector_id in missing:
        issues.append({"level": "error", "path": "connectors", "message": f"Missing connector {connector_id}."})
    for connector_id, manifest in manifests.items():
        path = f"connectors.{connector_id}"
        if manifest.write_enabled and not manifest.live_approved:
            issues.append({"level": "error", "path": path, "message": "Write-enabled connector must be live-approved."})
        if manifest.auth_token_env and manifest.auth_token_env.lower() in {"token", "secret", "password"}:
            issues.append({"level": "warning", "path": f"{path}.auth_token_env", "message": "Use a connector-specific token env name."})
        if manifest.connector_id in {"email_send", "ticketing"} and manifest.source_mode == "live" and not manifest.write_enabled:
            issues.append({"level": "warning", "path": path, "message": "Live write connector is approved but write_enabled is false."})
    return {
        "valid": not any(issue["level"] == "error" for issue in issues),
        "issues": issues,
        "summary": {
            "connector_count": len(manifests),
            "required_connector_ids": list(SUPPORT_ACTION_CONNECTOR_IDS),
            "live_approved_count": sum(1 for manifest in manifests.values() if manifest.live_approved),
            "write_enabled_count": sum(1 for manifest in manifests.values() if manifest.write_enabled),
        },
    }


def default_enterprise_live_connector_config() -> dict[str, Any]:
    return {
        "enterprise_live_connectors_version": ENTERPRISE_LIVE_CONNECTORS_VERSION,
        "config_type": ENTERPRISE_LIVE_CONNECTORS_TYPE,
        "claim_boundary": "Production-candidate connector configuration; not production certification.",
        "connectors": [
            {
                "connector_id": "crm_support",
                "display_name": "CRM/support case context",
                "base_url": "https://connectors.example.internal",
                "endpoint_path": "/aana/support/case-context",
                "environment": "pilot",
                "owner": "Support Operations",
                "auth_token_env": "AANA_CRM_SUPPORT_TOKEN",
                "approval_status": "pending",
                "source_mode": "dry_run",
                "timeout_seconds": 10,
                "write_enabled": False,
                "supports_shadow_reads": True,
            },
            {
                "connector_id": "email_send",
                "display_name": "Email send action",
                "base_url": "https://connectors.example.internal",
                "endpoint_path": "/aana/email/send",
                "environment": "pilot",
                "owner": "Support Operations",
                "auth_token_env": "AANA_EMAIL_SEND_TOKEN",
                "approval_status": "pending",
                "source_mode": "dry_run",
                "timeout_seconds": 10,
                "write_enabled": False,
                "supports_shadow_reads": False,
            },
            {
                "connector_id": "ticketing",
                "display_name": "Ticket update action",
                "base_url": "https://connectors.example.internal",
                "endpoint_path": "/aana/tickets/update",
                "environment": "pilot",
                "owner": "Support Operations",
                "auth_token_env": "AANA_TICKETING_TOKEN",
                "approval_status": "pending",
                "source_mode": "dry_run",
                "timeout_seconds": 10,
                "write_enabled": False,
                "supports_shadow_reads": False,
            },
        ],
    }


def write_enterprise_live_connector_config(path: str | pathlib.Path = DEFAULT_ENTERPRISE_LIVE_CONNECTORS_PATH) -> dict[str, Any]:
    config = default_enterprise_live_connector_config()
    validation = validate_enterprise_live_connector_config(config)
    _write_json(path, config)
    return {"path": str(path), "config": config, "validation": validation}


def run_enterprise_support_connector_smoke(
    *,
    config_path: str | pathlib.Path | None = None,
    output_path: str | pathlib.Path | None = None,
    mode: str = "dry_run",
    transports: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mode = _validate_mode(mode)
    config = load_enterprise_live_connector_config(config_path) if config_path else default_enterprise_live_connector_config()
    validation = validate_enterprise_live_connector_config(config)
    connectors = build_enterprise_support_connectors(config, transports=transports)
    safe_aana_result = {
        "gate_decision": "pass",
        "recommended_action": "accept",
        "aix": {"score": 0.96, "decision": "accept", "hard_blockers": []},
    }
    unsafe_aana_result = {
        "gate_decision": "fail",
        "recommended_action": "defer",
        "aix": {"score": 0.51, "decision": "defer", "hard_blockers": ["smoke_hard_blocker"]},
    }
    results = {
        "crm_support": connectors["crm_support"].fetch_support_case(
            case_ref="redacted-case-smoke-001",
            metadata={"purpose": "production_candidate_smoke"},
            mode=mode,
        ),
        "email_send": connectors["email_send"].send_email(
            email_action={
                "draft_ref": "redacted-draft-smoke-001",
                "recipient_ref": "redacted-recipient-smoke-001",
                "body_ref": "redacted-body-smoke-001",
            },
            aana_result=safe_aana_result,
            mode=mode,
        ),
        "ticketing": connectors["ticketing"].update_ticket(
            ticket_action={
                "ticket_ref": "redacted-ticket-smoke-001",
                "visibility": "customer_visible",
                "update_ref": "redacted-update-smoke-001",
            },
            aana_result=unsafe_aana_result,
            mode=mode,
        ),
    }
    report = {
        "enterprise_live_connectors_version": ENTERPRISE_LIVE_CONNECTORS_VERSION,
        "config_type": ENTERPRISE_LIVE_CONNECTORS_TYPE,
        "created_at": _utc_now(),
        "mode": mode,
        "valid": validation["valid"] and all(result.get("valid") is not None for result in results.values()),
        "claim_boundary": "Connector smoke evidence only; not production certification.",
        "validation": validation,
        "results": results,
        "summary": {
            "connector_count": len(results),
            "executed_count": sum(1 for result in results.values() if result.get("executed")),
            "blocked_count": sum(1 for result in results.values() if result.get("route") == "defer"),
            "raw_payload_logged": any(result.get("raw_payload_logged") for result in results.values()),
        },
    }
    if output_path:
        _write_json(output_path, report)
    return report


__all__ = [
    "DEFAULT_ENTERPRISE_LIVE_CONNECTORS_PATH",
    "ENTERPRISE_LIVE_CONNECTORS_TYPE",
    "ENTERPRISE_LIVE_CONNECTORS_VERSION",
    "EXECUTION_MODES",
    "SUPPORT_ACTION_CONNECTOR_IDS",
    "EnterpriseConnectorError",
    "EnterpriseConnectorManifest",
    "EnterpriseHTTPJSONConnector",
    "aana_allows_execution",
    "build_enterprise_support_connectors",
    "default_enterprise_live_connector_config",
    "enterprise_connector_manifests",
    "load_enterprise_live_connector_config",
    "run_enterprise_support_connector_smoke",
    "validate_enterprise_live_connector_config",
    "write_enterprise_live_connector_config",
]
