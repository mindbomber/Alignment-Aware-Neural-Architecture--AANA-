"""FastAPI service for AANA local checks.

This module exposes the small API surface developers need to wrap agent
actions:

- GET /health
- POST /pre-tool-check
- POST /agent-check

FastAPI serves OpenAPI JSON at /openapi.json and Swagger UI at /docs.
"""

from __future__ import annotations

import argparse
import collections
import os
import pathlib
import threading
import time
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

import aana
from eval_pipeline import (
    agent_api,
    aix_audit,
    durable_audit_storage,
    enterprise_connector_readiness,
    enterprise_live_connectors,
    enterprise_support_demo,
    live_monitoring,
    mlcommons_aix,
    production_candidate_check,
    production_candidate_profile,
    runtime_human_review,
)


DEFAULT_TOKEN_ENV = "AANA_BRIDGE_TOKEN"
DEFAULT_TOKEN_SCOPES_ENV = "AANA_BRIDGE_TOKEN_SCOPES"
DEFAULT_RATE_LIMIT_PER_MINUTE_ENV = "AANA_RATE_LIMIT_PER_MINUTE"
DEFAULT_MAX_REQUEST_BYTES_ENV = "AANA_MAX_REQUEST_BYTES"
FASTAPI_SERVICE_VERSION = "0.1"
AUDIT_APPEND_LOCK = threading.Lock()
RATE_LIMIT_LOCK = threading.Lock()
PRE_TOOL_CHECK_EXAMPLE = {
    "tool_name": "send_email",
    "tool_category": "write",
    "authorization_state": "user_claimed",
    "evidence_refs": ["draft_id:123"],
    "risk_domain": "customer_support",
    "proposed_arguments": {"to": "customer@example.com"},
    "recommended_route": "accept",
}
CONFIRMED_PRE_TOOL_CHECK_EXAMPLE = {
    "tool_name": "send_email",
    "tool_category": "write",
    "authorization_state": "confirmed",
    "evidence_refs": ["draft_id:123", "approval:user-confirmed-send"],
    "risk_domain": "customer_support",
    "proposed_arguments": {"to": "customer@example.com"},
    "recommended_route": "accept",
}
AGENT_CHECK_EXAMPLE = {
    "event_version": "0.1",
    "event_id": "demo-support-refund-001",
    "agent": "openclaw",
    "adapter_id": "support_reply",
    "user_request": (
        "Draft a customer-support reply for a refund request. Use only verified "
        "facts: customer name is Maya Chen, order ID and refund eligibility are "
        "not available, and do not include private account details or invent "
        "policy promises."
    ),
    "candidate_action": "Hi Maya, order #A1842 is eligible for a full refund and your card ending 4242 will be credited in 3 days.",
    "available_evidence": [
        "Customer name: Maya Chen",
        "Order ID: unavailable",
        "Refund eligibility: unavailable",
        "Private account details must not be included",
    ],
    "allowed_actions": ["accept", "revise", "ask", "defer", "refuse"],
}
WORKFLOW_CHECK_EXAMPLE = {
    "contract_version": "0.1",
    "workflow_id": "demo-support-workflow-001",
    "adapter": "support_reply",
    "request": "Draft a support reply using only verified facts.",
    "candidate": "Your refund has been approved and will arrive tomorrow.",
    "evidence": ["Refund eligibility: unavailable."],
    "allowed_actions": ["accept", "revise", "ask", "defer", "refuse"],
}
WORKFLOW_BATCH_EXAMPLE = {
    "contract_version": "0.1",
    "batch_id": "demo-enterprise-batch",
    "requests": [WORKFLOW_CHECK_EXAMPLE],
}
AIX_AUDIT_EXAMPLE = {
    "output_dir": "eval_outputs/aix_audit/fastapi-enterprise-ops",
    "shadow_mode": True,
}
ENTERPRISE_SUPPORT_DEMO_EXAMPLE = {
    "output_dir": "eval_outputs/demos/fastapi-enterprise-support",
    "shadow_mode": True,
}
ENTERPRISE_LIVE_CONNECTORS_EXAMPLE = {
    "mode": "dry_run",
    "config_path": "examples/enterprise_support_live_connectors.json",
}
MLCOMMONS_AIX_REPORT_EXAMPLE = {
    "results_path": "examples/mlcommons_ailuminate_results.json",
    "source_type": "ailuminate",
    "profile_path": "examples/mlcommons_aix_profile.json",
    "output_dir": "eval_outputs/mlcommons_aix/fastapi",
}
PRODUCTION_CANDIDATE_PROFILE_EXAMPLE = {
    "profile_path": "examples/production_candidate_profile_enterprise_support.json",
}
DURABLE_AUDIT_STORAGE_EXAMPLE = {
    "source_audit_log": "eval_outputs/aix_audit/enterprise_ops_pilot/audit.jsonl",
    "audit_path": "eval_outputs/durable_audit_storage/aana_audit.jsonl",
    "manifest_path": "eval_outputs/durable_audit_storage/aana_audit.jsonl.sha256.json",
}
HEALTH_EXAMPLE = {
    "status": "ok",
    "service": "aana-fastapi",
    "service_version": FASTAPI_SERVICE_VERSION,
    "auth_required": True,
    "auth_scopes": ["pre_tool_check", "agent_check"],
    "rate_limit": {"enabled": True, "requests_per_minute": 60},
    "request_size_limit": {"enabled": True, "max_bytes": 65536},
}


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "shadow"}


def _append_audit_record(audit_log_path: str | pathlib.Path | None, record: dict[str, Any]) -> None:
    if not audit_log_path:
        return
    with AUDIT_APPEND_LOCK:
        agent_api.append_audit_record(pathlib.Path(audit_log_path), record)


def _scopes_from_env(value: str | None) -> set[str]:
    if not value:
        return {
            "pre_tool_check",
            "agent_check",
            "workflow_check",
            "workflow_batch",
            "validation",
            "aix_audit",
            "durable_audit_storage",
            "human_review_export",
            "live_monitoring",
            "enterprise_connectors",
            "enterprise_live_connectors",
            "enterprise_demo",
            "mlcommons_aix_report",
            "production_candidate_profile",
            "production_candidate_check",
        }
    scopes = {item.strip() for item in value.split(",") if item.strip()}
    return scopes or {"pre_tool_check", "agent_check"}


def _client_key(request: Request) -> str:
    auth = request.headers.get("authorization") or request.headers.get("x-aana-token")
    host = request.client.host if request.client else "unknown"
    return f"{host}:{hash(auth or 'anonymous')}"


def _rate_limited(
    request_times: dict[str, collections.deque[float]],
    key: str,
    *,
    limit_per_minute: int | None,
    now: float | None = None,
) -> tuple[bool, int | None]:
    if not limit_per_minute or limit_per_minute <= 0:
        return False, None
    current = now or time.time()
    window_start = current - 60
    with RATE_LIMIT_LOCK:
        bucket = request_times.setdefault(key, collections.deque())
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit_per_minute:
            retry_after = max(1, int(60 - (current - bucket[0])))
            return True, retry_after
        bucket.append(current)
    return False, None


def _tool_audit_record(event: dict[str, Any], result: dict[str, Any], started_at: float) -> dict[str, Any]:
    latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
    return agent_api.audit_tool_precheck(
        event,
        result,
        latency_ms=latency_ms,
        surface="fastapi",
        route="/pre-tool-check",
    )


def _authorized(
    *,
    configured_token: str | None,
    authorization: str | None,
    x_aana_token: str | None,
) -> bool:
    if not configured_token:
        return True
    if authorization and authorization.strip() == f"Bearer {configured_token}":
        return True
    return x_aana_token == configured_token


def create_app(
    *,
    auth_token: str | None = None,
    auth_scopes: set[str] | None = None,
    audit_log_path: str | pathlib.Path | None = None,
    gallery_path: str | pathlib.Path = agent_api.DEFAULT_GALLERY,
    rate_limit_per_minute: int | None = None,
    max_request_bytes: int | None = None,
) -> FastAPI:
    """Create the FastAPI AANA service."""

    configured_token = auth_token if auth_token is not None else os.environ.get(DEFAULT_TOKEN_ENV)
    configured_scopes = auth_scopes or _scopes_from_env(os.environ.get(DEFAULT_TOKEN_SCOPES_ENV))
    if rate_limit_per_minute is None:
        rate_limit_per_minute = int(os.environ.get(DEFAULT_RATE_LIMIT_PER_MINUTE_ENV, "60"))
    if max_request_bytes is None:
        max_request_bytes = int(os.environ.get(DEFAULT_MAX_REQUEST_BYTES_ENV, "65536"))
    request_times: dict[str, collections.deque[float]] = {}
    bearer_scheme = HTTPBearer(auto_error=False)
    api_key_scheme = APIKeyHeader(name="X-AANA-Token", auto_error=False)
    app = FastAPI(
        title="AANA Agent Action API",
        version=FASTAPI_SERVICE_VERSION,
        description=(
            "AANA API for checking proposed agent answers and tool calls before "
            "execution. The service returns accept, revise, ask, defer, or refuse "
            "routes with AIx scores, blockers, evidence refs, and audit-safe metadata."
        ),
        openapi_tags=[
            {"name": "runtime", "description": "AANA runtime health and service metadata."},
            {"name": "checks", "description": "Pre-execution checks for agent actions and agent events."},
        ],
    )

    @app.middleware("http")
    async def enforce_request_limits(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"} and max_request_bytes and max_request_bytes > 0:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > max_request_bytes:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "error": "request_too_large",
                        "message": f"Request body exceeds AANA_MAX_REQUEST_BYTES={max_request_bytes}.",
                        "max_request_bytes": max_request_bytes,
                    },
                )
        limited, retry_after = _rate_limited(request_times, _client_key(request), limit_per_minute=rate_limit_per_minute)
        if limited:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after or 60)},
                content={
                    "error": "rate_limited",
                    "message": "AANA FastAPI rate limit exceeded.",
                    "requests_per_minute": rate_limit_per_minute,
                    "retry_after_seconds": retry_after,
                },
            )
        return await call_next(request)

    def require_scope(scope: str):
        async def dependency(
            bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
            x_aana_token: str | None = Security(api_key_scheme),
        ) -> None:
            authorization = f"Bearer {bearer.credentials}" if bearer else None
            if not _authorized(configured_token=configured_token, authorization=authorization, x_aana_token=x_aana_token):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")
            if configured_token and scope not in configured_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error": "insufficient_scope", "required_scope": scope, "configured_scopes": sorted(configured_scopes)},
                )

        return dependency

    async def require_post_auth(
        bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
        x_aana_token: str | None = Security(api_key_scheme),
    ) -> None:
        authorization = f"Bearer {bearer.credentials}" if bearer else None
        if not _authorized(configured_token=configured_token, authorization=authorization, x_aana_token=x_aana_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")

    @app.get(
        "/health",
        tags=["runtime"],
        summary="Check AANA API health.",
        description="Returns safe runtime metadata, including whether POST auth and audit logging are configured.",
        responses={200: {"description": "Safe service metadata.", "content": {"application/json": {"example": HEALTH_EXAMPLE}}}},
    )
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "aana-fastapi",
            "service_version": FASTAPI_SERVICE_VERSION,
            "architecture_claim": aana.PUBLIC_ARCHITECTURE_CLAIM,
            "contract": "aana.agent_action_contract.v1",
            "auth_required": bool(configured_token),
            "auth_methods": ["Authorization: Bearer <token>", "X-AANA-Token: <token>"] if configured_token else [],
            "auth_scopes": sorted(configured_scopes) if configured_token else [],
            "audit_logging": "enabled" if audit_log_path else "disabled",
            "audit_log_configured": bool(audit_log_path),
            "rate_limit": {"enabled": bool(rate_limit_per_minute and rate_limit_per_minute > 0), "requests_per_minute": rate_limit_per_minute},
            "request_size_limit": {"enabled": bool(max_request_bytes and max_request_bytes > 0), "max_bytes": max_request_bytes},
            "routes": [
                "/health",
                "/ready",
                "/pre-tool-check",
                "/tool-precheck",
                "/agent-check",
                "/workflow-check",
                "/workflow-batch",
                "/aix-audit",
                "/durable-audit-storage",
                "/human-review-export",
                "/live-monitoring",
                "/enterprise-connectors",
                "/enterprise-live-connectors",
                "/enterprise-support-demo",
                "/production-candidate-profile",
                "/production-candidate-check",
                "/validate-event",
                "/validate-workflow",
                "/validate-tool-precheck",
                "/docs",
                "/openapi.json",
            ],
            "docs": "/docs",
        }

    @app.get(
        "/ready",
        tags=["runtime"],
        summary="Check AANA API readiness.",
        description="Alias for /health used by SDK clients and deployment probes.",
    )
    def ready() -> dict[str, Any]:
        return health()

    @app.post(
        "/tool-precheck",
        dependencies=[Depends(require_scope("pre_tool_check"))],
        tags=["checks"],
        summary="Alias for /pre-tool-check.",
        include_in_schema=False,
    )
    @app.post(
        "/pre-tool-check",
        dependencies=[Depends(require_scope("pre_tool_check"))],
        tags=["checks"],
        summary="Check an Agent Action Contract v1 tool call before execution.",
        description=(
            "Accepts the public seven-field Agent Action Contract v1 shape and "
            "returns an AANA route, AIx score, hard blockers, evidence refs, "
            "authorization state, and correction/recovery suggestion."
        ),
        responses={
            200: {
                "description": "AANA pre-tool decision.",
                "content": {"application/json": {"example": {"gate_decision": "fail", "recommended_action": "ask", "architecture_decision": {"route": "ask", "hard_blockers": ["write_missing_validation_or_confirmation"]}}}},
            },
            400: {"description": "Invalid request or failed check."},
            401: {"description": "Missing or invalid token when auth is configured."},
            403: {"description": "Token is valid but missing required scope."},
            413: {"description": "Request body exceeds configured size limit."},
            429: {"description": "Rate limit exceeded."},
        },
    )
    async def pre_tool_check(
        payload: dict[str, Any] = Body(
            ...,
            openapi_examples={
                "writeNeedsConfirmation": {
                    "summary": "Write action that should ask for confirmation",
                    "description": "A proposed email send with only user-claimed authorization. AANA returns ask.",
                    "value": PRE_TOOL_CHECK_EXAMPLE,
                },
                "confirmedWrite": {
                    "summary": "Confirmed write action",
                    "description": "A proposed email send with explicit confirmation evidence.",
                    "value": CONFIRMED_PRE_TOOL_CHECK_EXAMPLE,
                },
            },
        ),
        shadow_mode: bool | str | None = Query(
            default=None,
            description="Observe-only mode. AANA still reports the would-route; production effect is not blocked.",
        ),
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        try:
            result = aana.check_tool_call(payload)
            try:
                normalized = aana.normalize_tool_call_event(payload)
            except Exception:
                normalized = payload
            if _truthy(shadow_mode):
                result = agent_api.apply_shadow_mode(result)
                result = aana.with_architecture_decision(result, normalized)
            _append_audit_record(audit_log_path, _tool_audit_record(normalized, result, started_at))
            return result
        except Exception as exc:  # FastAPI converts this to a structured 400.
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "pre_tool_check_failed", "message": str(exc)}) from exc

    @app.post(
        "/agent-check",
        dependencies=[Depends(require_scope("agent_check"))],
        tags=["checks"],
        summary="Check a full AANA Agent Event before execution or response delivery.",
        description=(
            "Accepts the existing Agent Event Contract for answer/action checks. "
            "Use this for adapter-backed checks such as support replies, grounded "
            "answers, policy-bound messages, and other non-tool-call agent outputs."
        ),
        responses={
            200: {
                "description": "AANA agent-event decision.",
                "content": {"application/json": {"example": {"gate_decision": "pass", "recommended_action": "revise", "violations": [{"code": "unsupported_claim"}]}}},
            },
            400: {"description": "Invalid request or failed check."},
            401: {"description": "Missing or invalid token when auth is configured."},
            403: {"description": "Token is valid but missing required scope."},
            413: {"description": "Request body exceeds configured size limit."},
            429: {"description": "Rate limit exceeded."},
        },
    )
    async def agent_check(
        payload: dict[str, Any] = Body(
            ...,
            openapi_examples={
                "supportReplyNeedsRevision": {
                    "summary": "Support reply with unsupported private details",
                    "description": "A support response that invents order/refund facts. AANA returns revise.",
                    "value": AGENT_CHECK_EXAMPLE,
                }
            },
        ),
        adapter_id: str | None = Query(default=None),
        shadow_mode: bool | str | None = Query(default=None),
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        try:
            result = agent_api.check_event(payload, gallery_path=gallery_path, adapter_id=adapter_id)
            if _truthy(shadow_mode):
                result = agent_api.apply_shadow_mode(result)
            audit_result = dict(result)
            metadata = dict(audit_result.get("audit_metadata") or {})
            metadata["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
            audit_result["audit_metadata"] = metadata
            _append_audit_record(audit_log_path, agent_api.audit_event_check(payload, audit_result))
            return result
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "agent_check_failed", "message": str(exc)}) from exc

    @app.post(
        "/validate-event",
        dependencies=[Depends(require_scope("validation"))],
        tags=["checks"],
        summary="Validate an AANA Agent Event without running the gate.",
    )
    async def validate_event(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        return agent_api.validate_event(payload)

    @app.post(
        "/validate-workflow",
        dependencies=[Depends(require_scope("validation"))],
        tags=["checks"],
        summary="Validate a Workflow Contract request without running the gate.",
    )
    async def validate_workflow(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        return agent_api.validate_workflow_request(payload)

    @app.post(
        "/validate-tool-precheck",
        dependencies=[Depends(require_scope("validation"))],
        tags=["checks"],
        summary="Validate an Agent Action Contract v1 tool precheck event without running the gate.",
    )
    async def validate_tool_precheck(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        errors = aana.validate_tool_precheck_event(payload)
        return {"valid": not errors, "errors": errors, "schema_version": "aana.agent_tool_precheck.v1"}

    @app.post(
        "/workflow-check",
        dependencies=[Depends(require_scope("workflow_check"))],
        tags=["checks"],
        summary="Check a Workflow Contract request before using an AI output or action.",
        description="Returns gate decision, recommended action, violations, AIx, safe output, and audit-safe metadata.",
    )
    async def workflow_check(
        payload: dict[str, Any] = Body(
            ...,
            openapi_examples={
                "supportWorkflowNeedsRevision": {
                    "summary": "Support workflow with unsupported refund claim",
                    "description": "A workflow candidate that needs revision because evidence is missing.",
                    "value": WORKFLOW_CHECK_EXAMPLE,
                }
            },
        ),
        shadow_mode: bool | str | None = Query(default=None),
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        try:
            result = agent_api.check_workflow_request(payload, gallery_path=gallery_path)
            result.setdefault("audit_metadata", {})["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 3)
            if _truthy(shadow_mode):
                result = agent_api.apply_shadow_mode(result)
            _append_audit_record(audit_log_path, agent_api.audit_workflow_check(payload, result))
            return result
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "workflow_check_failed", "message": str(exc)}) from exc

    @app.post(
        "/workflow-batch",
        dependencies=[Depends(require_scope("workflow_batch"))],
        tags=["checks"],
        summary="Check a Workflow Contract batch and append per-item redacted audit records.",
    )
    async def workflow_batch(
        payload: dict[str, Any] = Body(
            ...,
            openapi_examples={
                "enterpriseBatch": {
                    "summary": "Enterprise workflow batch",
                    "description": "A batch request using Workflow Contract v1.",
                    "value": WORKFLOW_BATCH_EXAMPLE,
                }
            },
        ),
        shadow_mode: bool | str | None = Query(default=None),
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        try:
            result = agent_api.check_workflow_batch(payload, gallery_path=gallery_path)
            latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
            for item in result.get("results", []) if isinstance(result, dict) else []:
                if isinstance(item, dict):
                    item.setdefault("audit_metadata", {})["latency_ms"] = latency_ms
            if _truthy(shadow_mode):
                result = agent_api.apply_shadow_mode(result)
            audit_batch = agent_api.audit_workflow_batch(payload, result)
            for record in audit_batch.get("records", []):
                _append_audit_record(audit_log_path, record)
            return result
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "workflow_batch_failed", "message": str(exc)}) from exc

    @app.post(
        "/aix-audit",
        dependencies=[Depends(require_scope("aix_audit"))],
        tags=["checks"],
        summary="Run the enterprise-ops AANA AIx Audit and write local pilot artifacts.",
        description=(
            "Runs the same enterprise_ops_pilot audit path as the CLI: synthetic or supplied batch, "
            "redacted audit JSONL, metrics, drift report, integrity manifest, dashboard payload, "
            "connector readiness artifact, reviewer report, and AIx Report."
        ),
    )
    async def enterprise_aix_audit(
        payload: dict[str, Any] = Body(
            default_factory=dict,
            openapi_examples={
                "enterpriseOpsPilot": {
                    "summary": "Enterprise-ops pilot audit",
                    "description": "Generate the local AANA AIx Audit artifact bundle.",
                    "value": AIX_AUDIT_EXAMPLE,
                }
            },
        ),
    ) -> dict[str, Any]:
        try:
            return aix_audit.run_enterprise_ops_aix_audit(
                output_dir=payload.get("output_dir", aix_audit.DEFAULT_OUTPUT_DIR),
                batch_path=payload.get("batch_path") or payload.get("batch"),
                kit_dir=payload.get("kit_dir", aix_audit.DEFAULT_ENTERPRISE_KIT),
                gallery_path=payload.get("gallery_path", gallery_path),
                append=bool(payload.get("append", False)),
                shadow_mode=not _truthy(payload.get("enforce_mode")) if "shadow_mode" not in payload else _truthy(payload.get("shadow_mode")),
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "aix_audit_failed", "message": str(exc)}) from exc

    @app.post(
        "/durable-audit-storage",
        dependencies=[Depends(require_scope("durable_audit_storage"))],
        tags=["checks"],
        summary="Import or verify durable append-only storage for redacted AANA audit logs.",
        description=(
            "Provides a local production-candidate durable storage option for normal AANA runtime audit records. "
            "It accepts redacted audit JSONL, appends to durable storage, writes a tamper-evident manifest, "
            "and verifies append-only prefix preservation. It is not a substitute for customer-approved remote immutable storage."
        ),
    )
    async def durable_audit_storage_route(
        payload: dict[str, Any] = Body(
            default_factory=dict,
            openapi_examples={
                "importAudit": {
                    "summary": "Import redacted audit JSONL",
                    "description": "Append an existing audit log to durable local storage.",
                    "value": DURABLE_AUDIT_STORAGE_EXAMPLE,
                }
            },
        ),
    ) -> dict[str, Any]:
        try:
            audit_path = payload.get("audit_path", durable_audit_storage.DEFAULT_DURABLE_AUDIT_JSONL)
            manifest_path = payload.get("manifest_path", durable_audit_storage.DEFAULT_DURABLE_AUDIT_MANIFEST)
            if _truthy(payload.get("write_config")):
                return durable_audit_storage.write_durable_audit_storage_config(
                    payload.get("config_path", durable_audit_storage.DEFAULT_DURABLE_AUDIT_CONFIG_PATH)
                )
            if _truthy(payload.get("verify")):
                return durable_audit_storage.verify_durable_audit_storage(audit_path=audit_path, manifest_path=manifest_path)
            source = payload.get("source_audit_log")
            if not source:
                raise ValueError("source_audit_log is required unless write_config or verify is true.")
            return durable_audit_storage.import_audit_log_to_durable_storage(
                source,
                audit_path=audit_path,
                manifest_path=manifest_path,
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "durable_audit_storage_failed", "message": str(exc)}) from exc

    @app.post(
        "/human-review-export",
        dependencies=[Depends(require_scope("human_review_export"))],
        tags=["checks"],
        summary="Export human-review queue packets from redacted AANA runtime audit logs.",
        description=(
            "Creates standalone review packets and a summary JSON from already-redacted AANA audit JSONL. "
            "Packets preserve decisions, AIx summaries, blockers, violation codes, evidence source IDs, and fingerprints "
            "without copying prompts, candidates, evidence text, private records, or safe responses."
        ),
    )
    async def human_review_export_route(
        payload: dict[str, Any] = Body(
            default_factory=dict,
            openapi_examples={
                "exportReviewQueue": {
                    "summary": "Export runtime human-review queue",
                    "description": "Create review packets from redacted AANA audit JSONL.",
                    "value": {
                        "audit_log_path": "eval_outputs/aix_audit/enterprise_ops_pilot/aana-audit.jsonl",
                        "queue_path": "eval_outputs/human_review/runtime-review-queue.jsonl",
                        "summary_path": "eval_outputs/human_review/runtime-review-summary.json",
                    },
                }
            },
        ),
    ) -> dict[str, Any]:
        try:
            if _truthy(payload.get("write_config")):
                return runtime_human_review.write_human_review_export_config(
                    payload.get("config_path", runtime_human_review.DEFAULT_RUNTIME_HUMAN_REVIEW_CONFIG_PATH)
                )
            audit_log_path = payload.get("audit_log_path") or payload.get("audit_log")
            if not audit_log_path:
                raise ValueError("audit_log_path is required unless write_config is true.")
            return runtime_human_review.export_runtime_human_review_queue(
                audit_log_path,
                queue_path=payload.get("queue_path") or payload.get("queue_output", runtime_human_review.DEFAULT_RUNTIME_HUMAN_REVIEW_QUEUE_PATH),
                summary_path=payload.get("summary_path") or payload.get("summary_output", runtime_human_review.DEFAULT_RUNTIME_HUMAN_REVIEW_SUMMARY_PATH),
                include_all=_truthy(payload.get("include_all")),
                append=_truthy(payload.get("append")),
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "human_review_export_failed", "message": str(exc)}) from exc

    @app.post(
        "/live-monitoring",
        dependencies=[Depends(require_scope("live_monitoring"))],
        tags=["checks"],
        summary="Evaluate live monitoring metrics from redacted AANA runtime audit logs.",
        description=(
            "Builds live/shadow health metrics from redacted AANA audit JSONL and checks production-candidate thresholds "
            "for AIx score, blockers, connector failures, evidence freshness, human review, latency, and shadow interventions."
        ),
    )
    async def live_monitoring_route(
        payload: dict[str, Any] = Body(
            default_factory=dict,
            openapi_examples={
                "liveMonitoring": {
                    "summary": "Evaluate live monitoring metrics",
                    "value": {
                        "audit_log_path": "eval_outputs/aix_audit/enterprise_ops_pilot/aana-audit.jsonl",
                        "config_path": "examples/live_monitoring_metrics.json",
                        "output_path": "eval_outputs/monitoring/live-monitoring-report.json",
                    },
                }
            },
        ),
    ) -> dict[str, Any]:
        try:
            if _truthy(payload.get("write_config")):
                return live_monitoring.write_live_monitoring_config(
                    payload.get("config_path", live_monitoring.DEFAULT_LIVE_MONITORING_CONFIG_PATH)
                )
            audit_log_path = payload.get("audit_log_path") or payload.get("audit_log")
            if not audit_log_path:
                raise ValueError("audit_log_path is required unless write_config is true.")
            config_path = payload.get("config_path") or payload.get("config")
            config = live_monitoring.load_live_monitoring_config(config_path) if config_path else live_monitoring.live_monitoring_config()
            return live_monitoring.live_monitoring_report(
                audit_log_path,
                config=config,
                output_path=payload.get("output_path") or payload.get("output", live_monitoring.DEFAULT_LIVE_MONITORING_REPORT_PATH),
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "live_monitoring_failed", "message": str(exc)}) from exc

    @app.get(
        "/enterprise-connectors",
        dependencies=[Depends(require_scope("enterprise_connectors"))],
        tags=["checks"],
        summary="Return the enterprise-ops connector readiness plan.",
        description="Returns readiness requirements for CRM/support, ticketing, email send, IAM/access, CI/CD, deployment, and data export connectors.",
    )
    async def enterprise_connectors() -> dict[str, Any]:
        try:
            plan = enterprise_connector_readiness.enterprise_connector_readiness_plan()
            validation = enterprise_connector_readiness.validate_enterprise_connector_readiness_plan(plan)
            return {"plan": plan, "validation": validation}
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "enterprise_connectors_failed", "message": str(exc)}) from exc

    @app.post(
        "/enterprise-live-connectors",
        dependencies=[Depends(require_scope("enterprise_live_connectors"))],
        tags=["checks"],
        summary="Validate and smoke-test production-candidate support/email/ticket connectors.",
        description=(
            "Runs the real connector client layer in dry-run, shadow, or enforce mode. "
            "Dry-run performs no external calls. Writes execute only when the connector is "
            "live-approved/write-enabled and the AANA runtime result is pass/accept with no blockers."
        ),
    )
    async def enterprise_live_connectors_route(
        payload: dict[str, Any] = Body(
            default_factory=dict,
            openapi_examples={
                "dryRunSmoke": {
                    "summary": "Dry-run connector smoke",
                    "description": "Validate the production-candidate connector config without external calls.",
                    "value": ENTERPRISE_LIVE_CONNECTORS_EXAMPLE,
                }
            },
        ),
    ) -> dict[str, Any]:
        try:
            return enterprise_live_connectors.run_enterprise_support_connector_smoke(
                config_path=payload.get("config_path") or payload.get("config"),
                output_path=payload.get("output_path") or payload.get("output"),
                mode=payload.get("mode", "dry_run"),
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "enterprise_live_connectors_failed", "message": str(exc)}) from exc

    @app.post(
        "/mlcommons-aix-report",
        dependencies=[Depends(require_scope("mlcommons_aix_report"))],
        tags=["checks"],
        summary="Generate an AANA AIx Report from MLCommons benchmark results.",
        description=(
            "Imports AILuminate or ModelBench-style result artifacts and writes normalized MLCommons results, "
            "an AIx report JSON, and a Markdown report. This is production-candidate evidence only, not production certification."
        ),
    )
    async def mlcommons_aix_report_route(
        payload: dict[str, Any] = Body(
            default_factory=dict,
            openapi_examples={
                "ailuminate": {
                    "summary": "AILuminate result import",
                    "description": "Generate an AANA AIx Report from AILuminate-style hazard scores.",
                    "value": MLCOMMONS_AIX_REPORT_EXAMPLE,
                }
            },
        ),
    ) -> dict[str, Any]:
        try:
            return mlcommons_aix.run_mlcommons_aix_report(
                results_path=payload.get("results_path") or payload.get("results", mlcommons_aix.DEFAULT_MLCOMMONS_RESULTS_PATH),
                source_type=payload.get("source_type", "ailuminate"),
                profile_path=payload.get("profile_path") or payload.get("profile", mlcommons_aix.DEFAULT_MLCOMMONS_PROFILE_PATH),
                output_dir=payload.get("output_dir") or payload.get("output", mlcommons_aix.DEFAULT_MLCOMMONS_OUTPUT_DIR),
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "mlcommons_aix_report_failed", "message": str(exc)}) from exc

    @app.post(
        "/production-candidate-profile",
        dependencies=[Depends(require_scope("production_candidate_profile"))],
        tags=["checks"],
        summary="Validate the enterprise support production-candidate config profile.",
        description=(
            "Validates the profile tying together runtime fail-closed policy, live connector config, "
            "connector readiness, deployment, governance, observability, audit retention, incident response, "
            "and promotion requirements. A valid profile is not go-live approval."
        ),
    )
    async def production_candidate_profile_route(
        payload: dict[str, Any] = Body(
            default_factory=dict,
            openapi_examples={
                "enterpriseSupport": {
                    "summary": "Enterprise support production-candidate profile",
                    "description": "Validate the local profile artifact and linked production-candidate configs.",
                    "value": PRODUCTION_CANDIDATE_PROFILE_EXAMPLE,
                }
            },
        ),
    ) -> dict[str, Any]:
        try:
            path = payload.get("profile_path") or payload.get("profile")
            profile = (
                production_candidate_profile.load_production_candidate_profile(path)
                if path
                else production_candidate_profile.default_production_candidate_profile()
            )
            validation = production_candidate_profile.validate_production_candidate_profile(profile)
            return {"profile": profile, "validation": validation}
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "production_candidate_profile_failed", "message": str(exc)}) from exc

    @app.post(
        "/production-candidate-check",
        dependencies=[Depends(require_scope("production_candidate_check"))],
        tags=["checks"],
        summary="Validate production-candidate config and optional shadow-pilot artifacts.",
        description=(
            "Combines the production-candidate profile guard with optional run-artifact checks for redacted audit logs, "
            "live monitoring, human-review export, durable audit storage, connector smoke evidence, and AIx report boundaries."
        ),
    )
    async def production_candidate_check_route(
        payload: dict[str, Any] = Body(
            default_factory=dict,
            openapi_examples={
                "shadowPilot": {
                    "summary": "Check a shadow pilot artifact directory",
                    "value": {
                        "profile_path": "examples/production_candidate_profile_enterprise_support.json",
                        "artifact_dir": "eval_outputs/internal_shadow_pilot/enterprise_ops_2026_05_12",
                    },
                }
            },
        ),
    ) -> dict[str, Any]:
        try:
            return production_candidate_check.production_candidate_check(
                profile_path=payload.get("profile_path") or payload.get("profile", production_candidate_check.DEFAULT_PRODUCTION_CANDIDATE_PROFILE_PATH),
                artifact_dir=payload.get("artifact_dir"),
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "production_candidate_check_failed", "message": str(exc)}) from exc

    @app.post(
        "/enterprise-support-demo",
        dependencies=[Depends(require_scope("enterprise_demo"))],
        tags=["checks"],
        summary="Run the customer support + email send + ticket update demo flow.",
        description=(
            "Runs the buyer demo flow and writes the same local artifacts as the CLI: demo-flow JSON, "
            "redacted audit log, metrics, dashboard, drift report, integrity manifest, connector readiness, "
            "reviewer report, and AIx Report."
        ),
    )
    async def enterprise_support_demo_route(
        payload: dict[str, Any] = Body(
            default_factory=dict,
            openapi_examples={
                "supportEmailTicket": {
                    "summary": "Support/email/ticket shadow demo",
                    "description": "Generate the local buyer demo artifact bundle.",
                    "value": ENTERPRISE_SUPPORT_DEMO_EXAMPLE,
                }
            },
        ),
    ) -> dict[str, Any]:
        try:
            return enterprise_support_demo.run_enterprise_support_demo(
                output_dir=payload.get("output_dir", enterprise_support_demo.DEFAULT_OUTPUT_DIR),
                gallery_path=payload.get("gallery_path", gallery_path),
                shadow_mode=_truthy(payload.get("shadow_mode", False)),
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "enterprise_support_demo_failed", "message": str(exc)}) from exc

    return app


app = create_app()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AANA FastAPI service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--auth-token", default=None, help=f"POST auth token. Defaults to {DEFAULT_TOKEN_ENV}.")
    parser.add_argument("--auth-scopes", default=None, help=f"Comma-separated token scopes. Defaults to {DEFAULT_TOKEN_SCOPES_ENV} or pre_tool_check,agent_check.")
    parser.add_argument("--audit-log", default=None, help="Optional JSONL path for redacted audit records.")
    parser.add_argument("--gallery", default=str(agent_api.DEFAULT_GALLERY), help="Adapter gallery path for /agent-check.")
    parser.add_argument("--rate-limit-per-minute", type=int, default=None, help=f"Per-client in-memory request limit. Defaults to {DEFAULT_RATE_LIMIT_PER_MINUTE_ENV} or 60. Use 0 to disable.")
    parser.add_argument("--max-request-bytes", type=int, default=None, help=f"Reject larger POST bodies. Defaults to {DEFAULT_MAX_REQUEST_BYTES_ENV} or 65536. Use 0 to disable.")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - exercised only when optional dependency is missing.
        raise SystemExit("Install the api extra first: pip install -e .[api]") from exc

    service = create_app(
        auth_token=args.auth_token or os.environ.get(DEFAULT_TOKEN_ENV),
        auth_scopes=_scopes_from_env(args.auth_scopes) if args.auth_scopes is not None else None,
        audit_log_path=args.audit_log,
        gallery_path=args.gallery,
        rate_limit_per_minute=args.rate_limit_per_minute,
        max_request_bytes=args.max_request_bytes,
    )
    uvicorn.run(service, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
