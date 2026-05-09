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
from datetime import UTC, datetime
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

import aana
from eval_pipeline import agent_api


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
        return {"pre_tool_check", "agent_check"}
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


def _safe_tool_event_summary(event: dict[str, Any]) -> dict[str, Any]:
    refs = event.get("evidence_refs") or []
    return {
        "tool_name": event.get("tool_name"),
        "tool_category": event.get("tool_category"),
        "authorization_state": event.get("authorization_state"),
        "risk_domain": event.get("risk_domain"),
        "recommended_route": event.get("recommended_route"),
        "evidence_ref_count": len(refs) if isinstance(refs, list) else 0,
        "proposed_argument_keys": sorted((event.get("proposed_arguments") or {}).keys()),
    }


def _tool_audit_record(event: dict[str, Any], result: dict[str, Any], started_at: float) -> dict[str, Any]:
    architecture = result.get("architecture_decision") or {}
    latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
    audit_safe = aana.audit_safe_decision_event(result, event, latency_ms=latency_ms)
    return {
        "audit_record_version": "aana.fastapi.tool_precheck.v1",
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "record_type": "tool_precheck",
        "surface": "fastapi",
        "route": "/pre-tool-check",
        "contract": "aana.agent_action_contract.v1",
        "request": _safe_tool_event_summary(event),
        "decision": {
            "gate_decision": result.get("gate_decision"),
            "recommended_action": result.get("recommended_action"),
            "candidate_gate": result.get("candidate_gate"),
            "aix_score": architecture.get("aix_score"),
            "aix_decision": architecture.get("aix_decision"),
            "hard_blockers": architecture.get("hard_blockers", result.get("hard_blockers", [])),
            "missing_evidence": architecture.get("evidence_refs", {}).get("missing", []),
            "evidence_refs": architecture.get("evidence_refs", {}),
            "authorization_state": audit_safe.get("authorization_state"),
            "correction_recovery_suggestion": architecture.get("correction_recovery_suggestion"),
        },
        "audit_safe_log_event": audit_safe,
        "audit_metadata": {
            "latency_ms": latency_ms,
            "raw_payload_logged": False,
        },
    }


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
            "routes": ["/health", "/pre-tool-check", "/agent-check", "/docs", "/openapi.json"],
            "docs": "/docs",
        }

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
