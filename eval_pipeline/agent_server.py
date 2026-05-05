"""No-dependency local HTTP bridge for AANA agent checks."""

import argparse
import json
import mimetypes
import os
import pathlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api, agent_contract, aix, workflow_contract


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_MAX_BODY_BYTES = 1_048_576
DEFAULT_TOKEN_ENV = "AANA_BRIDGE_TOKEN"
DEFAULT_RATE_LIMIT_PER_MINUTE = 0
DEFAULT_READ_TIMEOUT_SECONDS = 30
BRIDGE_VERSION = "0.1"
PLAYGROUND_DIR = ROOT / "web" / "playground"
DEMOS_DIR = ROOT / "web" / "demos"
DASHBOARD_DIR = ROOT / "web" / "dashboard"
ADAPTER_GALLERY_DIR = ROOT / "docs" / "adapter-gallery"
FAMILY_ASSET_DIR = ROOT / "docs" / "families"
ENTERPRISE_DIR = ROOT / "docs" / "enterprise"
PERSONAL_PRODUCTIVITY_DIR = ROOT / "docs" / "personal-productivity"
GOVERNMENT_CIVIC_DIR = ROOT / "docs" / "government-civic"
DEFAULT_LOCAL_DEMOS = ROOT / "examples" / "local_action_demos.json"
PLAYGROUND_ASSET_ROUTES = {
    "/playground": PLAYGROUND_DIR / "index.html",
    "/playground/": PLAYGROUND_DIR / "index.html",
    "/playground/app.css": PLAYGROUND_DIR / "app.css",
    "/playground/app.js": PLAYGROUND_DIR / "app.js",
    "/playground/preview.png": ROOT / "assets" / "github-social-preview.png",
    "/demos": DEMOS_DIR / "index.html",
    "/demos/": DEMOS_DIR / "index.html",
    "/demos/app.css": DEMOS_DIR / "app.css",
    "/demos/app.js": DEMOS_DIR / "app.js",
    "/demos/preview.png": ROOT / "assets" / "github-social-preview.png",
    "/dashboard": DASHBOARD_DIR / "index.html",
    "/dashboard/": DASHBOARD_DIR / "index.html",
    "/dashboard/app.css": DASHBOARD_DIR / "app.css",
    "/dashboard/app.js": DASHBOARD_DIR / "app.js",
    "/dashboard/preview.png": ROOT / "assets" / "github-social-preview.png",
    "/adapter-gallery": ADAPTER_GALLERY_DIR / "index.html",
    "/adapter-gallery/": ADAPTER_GALLERY_DIR / "index.html",
    "/adapter-gallery/app.css": ADAPTER_GALLERY_DIR / "app.css",
    "/adapter-gallery/app.js": ADAPTER_GALLERY_DIR / "app.js",
    "/adapter-gallery/data.json": ADAPTER_GALLERY_DIR / "data.json",
    "/families/data.json": FAMILY_ASSET_DIR / "data.json",
    "/families/family-pack.css": FAMILY_ASSET_DIR / "family-pack.css",
    "/enterprise": ENTERPRISE_DIR / "index.html",
    "/enterprise/": ENTERPRISE_DIR / "index.html",
    "/personal-productivity": PERSONAL_PRODUCTIVITY_DIR / "index.html",
    "/personal-productivity/": PERSONAL_PRODUCTIVITY_DIR / "index.html",
    "/government-civic": GOVERNMENT_CIVIC_DIR / "index.html",
    "/government-civic/": GOVERNMENT_CIVIC_DIR / "index.html",
}


AUDIT_APPEND_LOCK = threading.Lock()


class AuditLogError(RuntimeError):
    pass


def error_payload(status, code, message, details=None):
    payload = {
        "error": message,
        "error_code": code,
        "status": status,
    }
    if details:
        payload["details"] = details
        payload.update(details)
    return payload


def _read_token_file(path):
    if not path:
        return None
    token_path = pathlib.Path(path)
    try:
        token = token_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return token or None


def _resolved_auth_token(auth_token=None, auth_token_file=None):
    if auth_token_file:
        return _read_token_file(auth_token_file)
    return auth_token


def _rate_limit_key(headers=None, client_id=None):
    if client_id:
        return str(client_id)
    forwarded = _header_value(headers, "X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return "local"


def _truthy_query_value(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "shadow"}


def check_rate_limit(state, key, limit_per_minute, now=None):
    if not limit_per_minute or limit_per_minute <= 0:
        return True, {"limit_per_minute": limit_per_minute, "remaining": None}
    current_time = now or time.monotonic()
    window_seconds = 60.0
    lock = state.setdefault("_lock", threading.Lock())
    with lock:
        calls = state.setdefault("calls", {})
        history = [timestamp for timestamp in calls.get(key, []) if current_time - timestamp < window_seconds]
        allowed = len(history) < limit_per_minute
        if allowed:
            history.append(current_time)
        calls[key] = history
        remaining = max(0, limit_per_minute - len(history))
    return allowed, {
        "limit_per_minute": limit_per_minute,
        "remaining": remaining,
        "retry_after_seconds": 60,
    }


def openapi_schema(base_url=f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"):
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "AANA Agent Bridge",
            "version": agent_api.AGENT_EVENT_VERSION,
            "description": "Local HTTP bridge for checking AI-agent events with AANA adapters.",
        },
        "servers": [{"url": base_url}],
        "paths": {
            "/health": {
                "get": {
                    "operationId": "getHealth",
                    "summary": "Check whether the local AANA bridge is running.",
                    "responses": {
                        "200": {
                            "description": "Bridge status.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Health"}}},
                        }
                    },
                }
            },
            "/ready": {
                "get": {
                    "operationId": "getReadiness",
                    "summary": "Check whether the AANA bridge can serve checks with its configured gallery and audit sink.",
                    "responses": {
                        "200": {
                            "description": "Bridge dependencies are ready.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Readiness"}}},
                        },
                        "503": {
                            "description": "Bridge dependency check failed.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Readiness"}}},
                        },
                    },
                }
            },
            "/policy-presets": {
                "get": {
                    "operationId": "listPolicyPresets",
                    "summary": "List starter policy presets for deciding when an agent should call AANA.",
                    "responses": {
                        "200": {
                            "description": "Policy presets keyed by preset name.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/PolicyPresets"}}},
                        }
                    },
                }
            },
            "/agent-check": {
                "post": {
                    "operationId": "checkAgentEvent",
                    "summary": "Check a planned agent action against an AANA adapter.",
                    "parameters": [
                        {
                            "name": "adapter_id",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Optional adapter override. If omitted, adapter_id or workflow is read from the event.",
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AgentEvent"}}},
                    },
                    "responses": {
                        "200": {
                            "description": "AANA gate result and safe response.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AgentCheckResult"}}},
                        },
                        "400": {
                            "description": "Invalid event or unknown adapter.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                        },
                    },
                }
            },
            "/workflow-check": {
                "post": {
                    "operationId": "checkWorkflowRequest",
                    "summary": "Check a proposed AI output or action with the AANA Workflow Contract.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WorkflowRequest"}}},
                    },
                    "responses": {
                        "200": {
                            "description": "AANA workflow gate result.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WorkflowResult"}}},
                        },
                        "400": {
                            "description": "Invalid workflow request or unknown adapter.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                        },
                    },
                }
            },
            "/workflow-batch": {
                "post": {
                    "operationId": "checkWorkflowBatch",
                    "summary": "Check multiple proposed AI outputs or actions with the AANA Workflow Batch Contract.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WorkflowBatchRequest"}}},
                    },
                    "responses": {
                        "200": {
                            "description": "AANA workflow batch gate results.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WorkflowBatchResult"}}},
                        },
                        "400": {
                            "description": "Invalid workflow batch request or unknown adapter.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                        },
                    },
                }
            },
            "/validate-event": {
                "post": {
                    "operationId": "validateAgentEvent",
                    "summary": "Validate an AANA agent event without running the gate.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AgentEvent"}}},
                    },
                    "responses": {
                        "200": {
                            "description": "Validation report.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ValidationReport"}}},
                        },
                        "400": {
                            "description": "Request body is not valid JSON.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                        },
                    },
                }
            },
            "/validate-workflow": {
                "post": {
                    "operationId": "validateWorkflowRequest",
                    "summary": "Validate an AANA workflow request without running the gate.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WorkflowRequest"}}},
                    },
                    "responses": {
                        "200": {
                            "description": "Validation report.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ValidationReport"}}},
                        },
                        "400": {
                            "description": "Request body is not valid JSON.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                        },
                    },
                }
            },
            "/validate-workflow-batch": {
                "post": {
                    "operationId": "validateWorkflowBatch",
                    "summary": "Validate an AANA workflow batch request without running the gate.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WorkflowBatchRequest"}}},
                    },
                    "responses": {
                        "200": {
                            "description": "Validation report.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ValidationReport"}}},
                        },
                        "400": {
                            "description": "Request body is not valid JSON.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                        },
                    },
                }
            },
            "/openapi.json": {
                "get": {
                    "operationId": "getOpenApiSchema",
                    "summary": "Return this OpenAPI contract.",
                    "responses": {"200": {"description": "OpenAPI schema."}},
                }
            },
            "/playground/gallery": {
                "get": {
                    "operationId": "getPlaygroundGallery",
                    "summary": "Return adapter gallery demos for the local web playground.",
                    "responses": {"200": {"description": "Adapter gallery demo metadata."}},
                }
            },
            "/adapter-gallery/": {
                "get": {
                    "operationId": "getAdapterGalleryPage",
                    "summary": "Serve the searchable public AANA adapter gallery.",
                    "responses": {"200": {"description": "Searchable adapter gallery HTML."}},
                }
            },
            "/adapter-gallery/data.json": {
                "get": {
                    "operationId": "getPublishedAdapterGalleryData",
                    "summary": "Return published adapter metadata with risk tier, evidence, surfaces, examples, and AIx tuning.",
                    "responses": {"200": {"description": "Published adapter gallery data."}},
                }
            },
            "/enterprise/": {
                "get": {
                    "operationId": "getEnterpriseFamilyPage",
                    "summary": "Serve the Enterprise AANA family landing page.",
                    "responses": {"200": {"description": "Enterprise family page."}},
                }
            },
            "/personal-productivity/": {
                "get": {
                    "operationId": "getPersonalProductivityFamilyPage",
                    "summary": "Serve the Personal Productivity AANA family landing page.",
                    "responses": {"200": {"description": "Personal Productivity family page."}},
                }
            },
            "/government-civic/": {
                "get": {
                    "operationId": "getGovernmentCivicFamilyPage",
                    "summary": "Serve the Government and Civic AANA family landing page.",
                    "responses": {"200": {"description": "Government and Civic family page."}},
                }
            },
            "/families/data.json": {
                "get": {
                    "operationId": "getAanaFamilyPackData",
                    "summary": "Return AANA family-pack metadata for Enterprise, Personal Productivity, and Government/Civic.",
                    "responses": {"200": {"description": "Family pack metadata."}},
                }
            },
            "/demos/scenarios": {
                "get": {
                    "operationId": "getLocalActionDemos",
                    "summary": "Return local desktop/browser demo scenarios for everyday irreversible actions.",
                    "responses": {"200": {"description": "Local action demo metadata and synthetic evidence templates."}},
                }
            },
            "/dashboard/metrics": {
                "get": {
                    "operationId": "getAuditMetricsDashboard",
                    "summary": "Return dashboard-ready metrics from the configured redacted audit log.",
                    "responses": {
                        "200": {"description": "Dashboard metrics from redacted audit records."},
                        "404": {"description": "No audit log is configured or present."},
                    },
                }
            },
            "/playground/check": {
                "post": {
                    "operationId": "checkPlaygroundWorkflow",
                    "summary": "Run a playground workflow check and return the result plus redacted audit record preview.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WorkflowRequest"}}},
                    },
                    "responses": {
                        "200": {"description": "AANA workflow gate result and redacted audit preview."},
                        "400": {"description": "Invalid workflow request or unknown adapter."},
                    },
                }
            },
        },
        "components": {
            "schemas": {
                "AgentEvent": agent_contract.AGENT_EVENT_SCHEMA,
                "AgentCheckResult": agent_contract.AGENT_CHECK_RESULT_SCHEMA,
                "Aix": aix.AIX_SCHEMA,
                "WorkflowRequest": workflow_contract.WORKFLOW_REQUEST_SCHEMA,
                "WorkflowBatchRequest": workflow_contract.WORKFLOW_BATCH_REQUEST_SCHEMA,
                "WorkflowResult": workflow_contract.WORKFLOW_RESULT_SCHEMA,
                "WorkflowBatchResult": workflow_contract.WORKFLOW_BATCH_RESULT_SCHEMA,
                "Health": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "service": {"type": "string"},
                        "bridge_version": {"type": "string"},
                        "agent_check_version": {"type": "string"},
                    },
                },
                "Readiness": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "ready": {"type": "boolean"},
                        "checks": {"type": "array", "items": {"type": "object"}},
                    },
                },
                "PolicyPresets": {
                    "type": "object",
                    "properties": {"policy_presets": {"type": "object"}},
                },
                "Error": {
                    "type": "object",
                    "required": ["error", "error_code", "status"],
                    "properties": {
                        "error": {"type": "string"},
                        "error_code": {"type": "string"},
                        "status": {"type": "integer"},
                        "details": {"type": "object"},
                    },
                },
                "ValidationReport": {
                    "type": "object",
                    "required": ["valid", "errors", "warnings", "issues"],
                    "properties": {
                        "valid": {"type": "boolean"},
                        "errors": {"type": "integer"},
                        "warnings": {"type": "integer"},
                        "issues": {"type": "array", "items": {"type": "object"}},
                    },
                },
            }
        },
    }


def json_bytes(payload):
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def playground_static_response(target):
    parsed = urlparse(target)
    path = PLAYGROUND_ASSET_ROUTES.get(parsed.path)
    if not path:
        return None
    try:
        body = path.read_bytes()
    except OSError:
        return 404, "application/json; charset=utf-8", json_bytes(error_payload(404, "playground_asset_missing", "Playground asset is missing."))
    if parsed.path == "/adapter-gallery":
        body = body.replace(b'href="app.css"', b'href="/adapter-gallery/app.css"')
        body = body.replace(b'src="app.js"', b'src="/adapter-gallery/app.js"')
    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    if path.suffix in {".html", ".css", ".js"}:
        content_type = f"{content_type}; charset=utf-8"
    return 200, content_type, body


def playground_gallery(gallery_path=agent_api.DEFAULT_GALLERY):
    gallery = agent_api.load_gallery(gallery_path)
    adapters = []
    for entry in agent_api.gallery_entries(gallery):
        adapters.append(
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "status": entry.get("status"),
                "workflow": entry.get("workflow"),
                "best_for": entry.get("best_for", []),
                "prompt": entry.get("prompt"),
                "bad_candidate": entry.get("bad_candidate"),
                "expected": entry.get("expected", {}),
                "caveats": entry.get("caveats", []),
                "adapter_path": entry.get("adapter_path"),
            }
        )
    return {
        "playground_version": BRIDGE_VERSION,
        "gallery_path": str(gallery_path),
        "adapter_count": len(adapters),
        "adapters": adapters,
    }


def local_action_demos(path=DEFAULT_LOCAL_DEMOS):
    payload = agent_api.load_json_file(path)
    demos = payload.get("demos")
    if not isinstance(demos, list) or not demos:
        raise ValueError("Local action demos file must include a non-empty demos list.")
    return payload


def dashboard_metrics(audit_log_path=None):
    if not audit_log_path:
        return {
            "audit_dashboard_version": "0.1",
            "status": "missing_audit_log",
            "message": "Start the bridge with --audit-log to populate the dashboard.",
            "record_count": 0,
            "cards": {
                "total_records": 0,
                "gate_pass": 0,
                "gate_fail": 0,
                "accepted": 0,
                "revised": 0,
                "deferred": 0,
                "refused": 0,
                "violation_total": 0,
                "hard_blocker_total": 0,
                "shadow_records": 0,
                "shadow_would_block_rate": 0.0,
                "shadow_would_intervene_rate": 0.0,
            },
            "aix": {"count": 0, "average": None, "min": None, "max": None},
            "gate_decisions": {},
            "recommended_actions": {},
            "violation_trends": [],
            "top_violations": [],
            "hard_blockers": {"total": 0, "items": []},
            "adapter_breakdown": [],
            "shadow_mode": {
                "records": 0,
                "would_routes": {},
                "would_block": 0,
                "would_intervene": 0,
                "would_block_rate": 0.0,
                "would_intervene_rate": 0.0,
            },
        }
    audit_path = pathlib.Path(audit_log_path)
    if not audit_path.exists():
        return {
            **dashboard_metrics(None),
            "status": "audit_log_not_found",
            "message": f"Audit log does not exist yet: {audit_path}",
            "audit_log_path": str(audit_path),
        }
    payload = agent_api.audit_dashboard_file(audit_path)
    payload["status"] = "ok"
    return payload


def _header_value(headers, name):
    if not headers:
        return None
    lower_name = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lower_name:
            return value
    return None


def _authorized(headers, auth_token):
    if not auth_token:
        return True
    authorization = _header_value(headers, "Authorization")
    if authorization == f"Bearer {auth_token}":
        return True
    return _header_value(headers, "X-AANA-Token") == auth_token


def _append_audit_record(audit_log_path, record):
    if not audit_log_path:
        return
    try:
        with AUDIT_APPEND_LOCK:
            agent_api.append_audit_record(pathlib.Path(audit_log_path), record)
    except OSError as exc:
        raise AuditLogError(f"Audit append failed: {exc}") from exc


def _append_workflow_batch_audit(audit_log_path, batch_request, result):
    if not audit_log_path:
        return
    audit_record = agent_api.audit_workflow_batch(batch_request, result)
    for record in audit_record.get("records", []):
        _append_audit_record(audit_log_path, record)


def readiness_report(gallery_path=agent_api.DEFAULT_GALLERY, audit_log_path=None, auth_token=None, auth_token_file=None):
    checks = []
    try:
        gallery = agent_api.load_gallery(gallery_path)
        adapter_count = len(agent_api.gallery_entries(gallery))
        checks.append(
            {
                "name": "adapter_gallery",
                "status": "pass",
                "message": "Adapter gallery can be loaded.",
                "details": {"adapter_count": adapter_count, "gallery_path": str(gallery_path)},
            }
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        checks.append(
            {
                "name": "adapter_gallery",
                "status": "fail",
                "message": str(exc),
                "details": {"gallery_path": str(gallery_path)},
            }
        )

    token = _resolved_auth_token(auth_token=auth_token, auth_token_file=auth_token_file)
    if auth_token_file and not token:
        auth_status = "fail"
        auth_message = "POST auth token file is configured but no token could be read."
    elif token:
        auth_status = "pass"
        auth_message = "POST auth token is configured."
    else:
        auth_status = "warn"
        auth_message = "POST auth token is not configured."
    checks.append(
        {
            "name": "post_auth",
            "status": auth_status,
            "message": auth_message,
            "details": {"token_source": "file" if auth_token_file else "value" if auth_token else "none"},
        }
    )

    if audit_log_path:
        audit_path = pathlib.Path(audit_log_path)
        parent = audit_path.parent
        if parent.exists() and parent.is_dir():
            status = "pass"
            message = "Audit log parent directory exists."
        else:
            status = "fail"
            message = "Audit log parent directory does not exist."
        checks.append(
            {
                "name": "audit_log",
                "status": status,
                "message": message,
                "details": {"audit_log_path": str(audit_path)},
            }
        )
    else:
        checks.append(
            {
                "name": "audit_log",
                "status": "warn",
                "message": "Audit log append is disabled.",
                "details": {},
            }
        )

    failed = [item for item in checks if item["status"] == "fail"]
    warnings = [item for item in checks if item["status"] == "warn"]
    return {
        "status": "ready" if not failed else "not_ready",
        "ready": not failed,
        "bridge_version": BRIDGE_VERSION,
        "checks": checks,
        "summary": {
            "checks": len(checks),
            "failures": len(failed),
            "warnings": len(warnings),
        },
    }


def route_request(
    method,
    target,
    body=b"",
    gallery_path=agent_api.DEFAULT_GALLERY,
    headers=None,
    max_body_bytes=DEFAULT_MAX_BODY_BYTES,
    auth_token=None,
    auth_token_file=None,
    audit_log_path=None,
    rate_limit_per_minute=DEFAULT_RATE_LIMIT_PER_MINUTE,
    rate_limit_state=None,
    client_id=None,
    shadow_mode=False,
):
    parsed = urlparse(target)
    query = parse_qs(parsed.query)
    request_shadow_mode = shadow_mode or _truthy_query_value(query.get("shadow_mode", [None])[0])

    if method == "POST" and len(body) > max_body_bytes:
        return 413, error_payload(
            413,
            "request_body_too_large",
            "Request body too large.",
            {"max_body_bytes": max_body_bytes},
        )

    token = _resolved_auth_token(auth_token=auth_token, auth_token_file=auth_token_file)
    if method == "POST" and auth_token_file and not token:
        return 503, error_payload(503, "auth_token_unavailable", "Auth token file is configured but no token could be read.")
    if method == "POST" and not _authorized(headers, token):
        return 401, error_payload(401, "unauthorized", "Unauthorized.")

    if method == "POST" and rate_limit_per_minute and rate_limit_per_minute > 0:
        state = rate_limit_state if rate_limit_state is not None else {}
        allowed, details = check_rate_limit(state, _rate_limit_key(headers=headers, client_id=client_id), rate_limit_per_minute)
        if not allowed:
            return 429, error_payload(429, "rate_limited", "Rate limit exceeded.", details)

    if method == "GET" and parsed.path == "/health":
        return 200, {
            "status": "ok",
            "service": "aana-agent-bridge",
            "bridge_version": BRIDGE_VERSION,
            "agent_check_version": agent_api.AGENT_EVENT_VERSION,
        }

    if method == "GET" and parsed.path == "/ready":
        report = readiness_report(
            gallery_path=gallery_path,
            audit_log_path=audit_log_path,
            auth_token=auth_token,
            auth_token_file=auth_token_file,
        )
        return 200 if report["ready"] else 503, report

    if method == "GET" and parsed.path == "/policy-presets":
        return 200, {"policy_presets": agent_api.list_policy_presets()}

    if method == "GET" and parsed.path == "/playground/gallery":
        try:
            return 200, playground_gallery(gallery_path=gallery_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return 500, error_payload(500, "playground_gallery_failed", str(exc))

    if method == "GET" and parsed.path == "/demos/scenarios":
        try:
            return 200, local_action_demos()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return 500, error_payload(500, "local_action_demos_failed", str(exc))

    if method == "GET" and parsed.path == "/dashboard/metrics":
        try:
            payload = dashboard_metrics(audit_log_path=audit_log_path)
            return 200, payload
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return 500, error_payload(500, "dashboard_metrics_failed", str(exc))

    if method == "GET" and parsed.path == "/openapi.json":
        return 200, openapi_schema()

    if method == "GET" and parsed.path == "/schemas/agent-event.schema.json":
        return 200, agent_contract.AGENT_EVENT_SCHEMA

    if method == "GET" and parsed.path == "/schemas/agent-check-result.schema.json":
        return 200, agent_contract.AGENT_CHECK_RESULT_SCHEMA

    if method == "GET" and parsed.path == "/schemas/aix.schema.json":
        return 200, aix.AIX_SCHEMA

    if method == "GET" and parsed.path == "/schemas/workflow-request.schema.json":
        return 200, workflow_contract.WORKFLOW_REQUEST_SCHEMA

    if method == "GET" and parsed.path == "/schemas/workflow-batch-request.schema.json":
        return 200, workflow_contract.WORKFLOW_BATCH_REQUEST_SCHEMA

    if method == "GET" and parsed.path == "/schemas/workflow-result.schema.json":
        return 200, workflow_contract.WORKFLOW_RESULT_SCHEMA

    if method == "GET" and parsed.path == "/schemas/workflow-batch-result.schema.json":
        return 200, workflow_contract.WORKFLOW_BATCH_RESULT_SCHEMA

    if method == "GET" and parsed.path == "/schemas":
        return 200, agent_api.schema_catalog()

    if method == "POST" and parsed.path == "/agent-check":
        try:
            event = json.loads(body.decode("utf-8") if body else "{}")
            if not isinstance(event, dict):
                raise ValueError("Request body must be a JSON object.")
            adapter_id = query.get("adapter_id", [None])[0]
            result = agent_api.check_event(event, gallery_path=gallery_path, adapter_id=adapter_id)
            if request_shadow_mode:
                result = agent_api.apply_shadow_mode(result)
            _append_audit_record(audit_log_path, agent_api.audit_event_check(event, result))
            return 200, result
        except AuditLogError as exc:
            return 500, error_payload(500, "audit_append_failed", str(exc))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            return 400, error_payload(400, "bad_request", str(exc))

    if method == "POST" and parsed.path == "/validate-event":
        try:
            event = json.loads(body.decode("utf-8") if body else "{}")
            return 200, agent_api.validate_event(event)
        except json.JSONDecodeError as exc:
            return 400, error_payload(400, "invalid_json", str(exc))

    if method == "POST" and parsed.path == "/workflow-check":
        try:
            workflow_request = json.loads(body.decode("utf-8") if body else "{}")
            if not isinstance(workflow_request, dict):
                raise ValueError("Request body must be a JSON object.")
            result = agent_api.check_workflow_request(workflow_request, gallery_path=gallery_path)
            if request_shadow_mode:
                result = agent_api.apply_shadow_mode(result)
            _append_audit_record(audit_log_path, agent_api.audit_workflow_check(workflow_request, result))
            return 200, result
        except AuditLogError as exc:
            return 500, error_payload(500, "audit_append_failed", str(exc))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            return 400, error_payload(400, "bad_request", str(exc))

    if method == "POST" and parsed.path == "/playground/check":
        try:
            workflow_request = json.loads(body.decode("utf-8") if body else "{}")
            if not isinstance(workflow_request, dict):
                raise ValueError("Request body must be a JSON object.")
            result = agent_api.check_workflow_request(workflow_request, gallery_path=gallery_path)
            if request_shadow_mode:
                result = agent_api.apply_shadow_mode(result)
            audit_record = agent_api.audit_workflow_check(workflow_request, result)
            _append_audit_record(audit_log_path, audit_record)
            return 200, {
                "playground_check_version": BRIDGE_VERSION,
                "result": result,
                "audit_record": audit_record,
                "audit_appended": bool(audit_log_path),
            }
        except AuditLogError as exc:
            return 500, error_payload(500, "audit_append_failed", str(exc))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            return 400, error_payload(400, "bad_request", str(exc))

    if method == "POST" and parsed.path == "/workflow-batch":
        try:
            batch_request = json.loads(body.decode("utf-8") if body else "{}")
            if not isinstance(batch_request, dict):
                raise ValueError("Request body must be a JSON object.")
            result = agent_api.check_workflow_batch(batch_request, gallery_path=gallery_path)
            if request_shadow_mode:
                result = agent_api.apply_shadow_mode(result)
            _append_workflow_batch_audit(audit_log_path, batch_request, result)
            return 200, result
        except AuditLogError as exc:
            return 500, error_payload(500, "audit_append_failed", str(exc))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            return 400, error_payload(400, "bad_request", str(exc))

    if method == "POST" and parsed.path == "/validate-workflow":
        try:
            workflow_request = json.loads(body.decode("utf-8") if body else "{}")
            return 200, agent_api.validate_workflow_request(workflow_request)
        except json.JSONDecodeError as exc:
            return 400, error_payload(400, "invalid_json", str(exc))

    if method == "POST" and parsed.path == "/validate-workflow-batch":
        try:
            batch_request = json.loads(body.decode("utf-8") if body else "{}")
            return 200, agent_api.validate_workflow_batch_request(batch_request)
        except json.JSONDecodeError as exc:
            return 400, error_payload(400, "invalid_json", str(exc))

    return 404, error_payload(
        404,
        "unknown_route",
        "Unknown route.",
        {
            "routes": [
                "GET /health",
                "GET /ready",
                "GET /policy-presets",
                "GET /playground",
                "GET /playground/gallery",
                "GET /adapter-gallery",
                "GET /adapter-gallery/data.json",
                "GET /enterprise",
                "GET /personal-productivity",
                "GET /government-civic",
                "GET /families/data.json",
                "GET /demos",
                "GET /demos/scenarios",
                "GET /dashboard",
                "GET /dashboard/metrics",
                "GET /openapi.json",
                "GET /schemas",
                "GET /schemas/agent-event.schema.json",
                "GET /schemas/agent-check-result.schema.json",
                "GET /schemas/aix.schema.json",
                "GET /schemas/workflow-request.schema.json",
                "GET /schemas/workflow-batch-request.schema.json",
                "GET /schemas/workflow-result.schema.json",
                "GET /schemas/workflow-batch-result.schema.json",
                "POST /validate-event",
                "POST /agent-check",
                "POST /validate-workflow",
                "POST /validate-workflow-batch",
                "POST /workflow-check",
                "POST /playground/check",
                "POST /workflow-batch",
            ],
        },
    )


class AanaAgentHandler(BaseHTTPRequestHandler):
    gallery_path = agent_api.DEFAULT_GALLERY
    max_body_bytes = DEFAULT_MAX_BODY_BYTES
    auth_token = None
    auth_token_file = None
    audit_log_path = None
    rate_limit_per_minute = DEFAULT_RATE_LIMIT_PER_MINUTE
    rate_limit_state = None
    read_timeout_seconds = DEFAULT_READ_TIMEOUT_SECONDS
    shadow_mode = False

    def do_GET(self):
        static = playground_static_response(self.path)
        if static:
            self.respond_raw(*static)
            return
        self.respond(
            *route_request(
                "GET",
                self.path,
                gallery_path=self.gallery_path,
                auth_token=self.auth_token,
                auth_token_file=self.auth_token_file,
                audit_log_path=self.audit_log_path,
            )
        )

    def do_POST(self):
        self.connection.settimeout(self.read_timeout_seconds)
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > self.max_body_bytes:
            self.respond(
                413,
                error_payload(
                    413,
                    "request_body_too_large",
                    "Request body too large.",
                    {"max_body_bytes": self.max_body_bytes},
                ),
            )
            return
        try:
            body = self.rfile.read(length)
        except TimeoutError:
            self.respond(408, error_payload(408, "request_timeout", "Timed out while reading request body."))
            return
        self.respond(
            *route_request(
                "POST",
                self.path,
                body=body,
                gallery_path=self.gallery_path,
                headers=self.headers,
                max_body_bytes=self.max_body_bytes,
                auth_token=self.auth_token,
                auth_token_file=self.auth_token_file,
                audit_log_path=self.audit_log_path,
                rate_limit_per_minute=self.rate_limit_per_minute,
                rate_limit_state=self.rate_limit_state,
                client_id=self.client_address[0] if self.client_address else None,
                shadow_mode=self.shadow_mode,
            )
        )

    def respond_raw(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        sys.stderr.write("aana_server: " + format % args + "\n")

    def respond(self, status, payload):
        data = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_handler(
    gallery_path,
    max_body_bytes=DEFAULT_MAX_BODY_BYTES,
    auth_token=None,
    auth_token_file=None,
    audit_log_path=None,
    rate_limit_per_minute=DEFAULT_RATE_LIMIT_PER_MINUTE,
    read_timeout_seconds=DEFAULT_READ_TIMEOUT_SECONDS,
    shadow_mode=False,
):
    class ConfiguredAanaAgentHandler(AanaAgentHandler):
        pass

    ConfiguredAanaAgentHandler.gallery_path = gallery_path
    ConfiguredAanaAgentHandler.max_body_bytes = max_body_bytes
    ConfiguredAanaAgentHandler.auth_token = auth_token
    ConfiguredAanaAgentHandler.auth_token_file = auth_token_file
    ConfiguredAanaAgentHandler.audit_log_path = audit_log_path
    ConfiguredAanaAgentHandler.rate_limit_per_minute = rate_limit_per_minute
    ConfiguredAanaAgentHandler.rate_limit_state = {"calls": {}}
    ConfiguredAanaAgentHandler.read_timeout_seconds = read_timeout_seconds
    ConfiguredAanaAgentHandler.shadow_mode = shadow_mode
    return ConfiguredAanaAgentHandler


def run_server(
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    gallery_path=agent_api.DEFAULT_GALLERY,
    max_body_bytes=DEFAULT_MAX_BODY_BYTES,
    auth_token=None,
    auth_token_file=None,
    audit_log_path=None,
    rate_limit_per_minute=DEFAULT_RATE_LIMIT_PER_MINUTE,
    read_timeout_seconds=DEFAULT_READ_TIMEOUT_SECONDS,
    shadow_mode=False,
):
    token = auth_token if auth_token is not None else os.environ.get(DEFAULT_TOKEN_ENV)
    server = ThreadingHTTPServer(
        (host, port),
        make_handler(
            gallery_path,
            max_body_bytes=max_body_bytes,
            auth_token=token,
            auth_token_file=auth_token_file,
            audit_log_path=audit_log_path,
            rate_limit_per_minute=rate_limit_per_minute,
            read_timeout_seconds=read_timeout_seconds,
            shadow_mode=shadow_mode,
        ),
    )
    print(f"AANA agent bridge listening on http://{host}:{port}")
    if auth_token_file:
        print(f"Auth: bearer token required for POST routes from token file {auth_token_file}.")
    elif token:
        print("Auth: bearer token required for POST routes.")
    else:
        print(f"Auth: no token configured. Set {DEFAULT_TOKEN_ENV} to require POST authorization.")
    if audit_log_path:
        print(f"Audit log: {audit_log_path}")
    else:
        print("Audit log: disabled. Pass --audit-log to append redacted gate records.")
    print(f"Max POST body: {max_body_bytes} bytes")
    print(f"Rate limit: {'disabled' if not rate_limit_per_minute else str(rate_limit_per_minute) + ' POST request(s)/minute/client'}")
    print(f"Read timeout: {read_timeout_seconds} seconds")
    print(f"Shadow mode: {'enabled (observe only)' if shadow_mode else 'disabled'}")
    print("Routes: GET /health, GET /ready, GET /policy-presets, GET /playground, GET /playground/gallery, GET /adapter-gallery, GET /adapter-gallery/data.json, GET /enterprise, GET /personal-productivity, GET /government-civic, GET /families/data.json, GET /demos, GET /demos/scenarios, GET /dashboard, GET /dashboard/metrics, GET /openapi.json, GET /schemas, POST /validate-event, POST /agent-check, POST /validate-workflow, POST /workflow-check, POST /playground/check, POST /validate-workflow-batch, POST /workflow-batch")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AANA agent bridge.")
    finally:
        server.server_close()


def build_parser():
    parser = argparse.ArgumentParser(description="Run the local AANA agent HTTP bridge.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind.")
    parser.add_argument("--gallery", default=str(agent_api.DEFAULT_GALLERY), help="Adapter gallery JSON path.")
    parser.add_argument(
        "--max-body-bytes",
        type=int,
        default=DEFAULT_MAX_BODY_BYTES,
        help="Maximum accepted POST body size.",
    )
    parser.add_argument(
        "--auth-token",
        default=None,
        help=f"Optional POST auth token. Prefer setting {DEFAULT_TOKEN_ENV} in production-like runs.",
    )
    parser.add_argument(
        "--auth-token-file",
        default=None,
        help="Optional file containing the POST auth token. The file is reread on each request to support rotation.",
    )
    parser.add_argument(
        "--audit-log",
        default=None,
        help="Optional JSONL path for redacted audit records from successful gate checks.",
    )
    parser.add_argument(
        "--rate-limit-per-minute",
        type=int,
        default=DEFAULT_RATE_LIMIT_PER_MINUTE,
        help="Maximum POST requests per minute per client. Use 0 to disable.",
    )
    parser.add_argument(
        "--read-timeout-seconds",
        type=float,
        default=DEFAULT_READ_TIMEOUT_SECONDS,
        help="Socket read timeout for request body reads.",
    )
    parser.add_argument(
        "--shadow-mode",
        action="store_true",
        help="Observe proposed actions and write would-pass/revise/defer/refuse telemetry without enforcing a block.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    run_server(
        host=args.host,
        port=args.port,
        gallery_path=args.gallery,
        max_body_bytes=args.max_body_bytes,
        auth_token=args.auth_token,
        auth_token_file=args.auth_token_file,
        audit_log_path=args.audit_log,
        rate_limit_per_minute=args.rate_limit_per_minute,
        read_timeout_seconds=args.read_timeout_seconds,
        shadow_mode=args.shadow_mode,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
