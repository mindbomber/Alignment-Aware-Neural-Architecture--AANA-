"""No-dependency local HTTP bridge for AANA agent checks."""

import argparse
import json
import os
import pathlib
import sys
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


class AuditLogError(RuntimeError):
    pass


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
                        "agent_check_version": {"type": "string"},
                    },
                },
                "PolicyPresets": {
                    "type": "object",
                    "properties": {"policy_presets": {"type": "object"}},
                },
                "Error": {
                    "type": "object",
                    "properties": {"error": {"type": "string"}},
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
        agent_api.append_audit_record(pathlib.Path(audit_log_path), record)
    except OSError as exc:
        raise AuditLogError(f"Audit append failed: {exc}") from exc


def _append_workflow_batch_audit(audit_log_path, batch_request, result):
    if not audit_log_path:
        return
    audit_record = agent_api.audit_workflow_batch(batch_request, result)
    for record in audit_record.get("records", []):
        _append_audit_record(audit_log_path, record)


def route_request(
    method,
    target,
    body=b"",
    gallery_path=agent_api.DEFAULT_GALLERY,
    headers=None,
    max_body_bytes=DEFAULT_MAX_BODY_BYTES,
    auth_token=None,
    audit_log_path=None,
):
    parsed = urlparse(target)
    query = parse_qs(parsed.query)

    if method == "POST" and len(body) > max_body_bytes:
        return 413, {
            "error": "Request body too large.",
            "max_body_bytes": max_body_bytes,
        }

    if method == "POST" and not _authorized(headers, auth_token):
        return 401, {"error": "Unauthorized."}

    if method == "GET" and parsed.path == "/health":
        return 200, {
            "status": "ok",
            "service": "aana-agent-bridge",
            "agent_check_version": agent_api.AGENT_EVENT_VERSION,
        }

    if method == "GET" and parsed.path == "/policy-presets":
        return 200, {"policy_presets": agent_api.list_policy_presets()}

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
            _append_audit_record(audit_log_path, agent_api.audit_event_check(event, result))
            return 200, result
        except AuditLogError as exc:
            return 500, {"error": str(exc)}
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            return 400, {"error": str(exc)}

    if method == "POST" and parsed.path == "/validate-event":
        try:
            event = json.loads(body.decode("utf-8") if body else "{}")
            return 200, agent_api.validate_event(event)
        except json.JSONDecodeError as exc:
            return 400, {"error": str(exc)}

    if method == "POST" and parsed.path == "/workflow-check":
        try:
            workflow_request = json.loads(body.decode("utf-8") if body else "{}")
            if not isinstance(workflow_request, dict):
                raise ValueError("Request body must be a JSON object.")
            result = agent_api.check_workflow_request(workflow_request, gallery_path=gallery_path)
            _append_audit_record(audit_log_path, agent_api.audit_workflow_check(workflow_request, result))
            return 200, result
        except AuditLogError as exc:
            return 500, {"error": str(exc)}
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            return 400, {"error": str(exc)}

    if method == "POST" and parsed.path == "/workflow-batch":
        try:
            batch_request = json.loads(body.decode("utf-8") if body else "{}")
            if not isinstance(batch_request, dict):
                raise ValueError("Request body must be a JSON object.")
            result = agent_api.check_workflow_batch(batch_request, gallery_path=gallery_path)
            _append_workflow_batch_audit(audit_log_path, batch_request, result)
            return 200, result
        except AuditLogError as exc:
            return 500, {"error": str(exc)}
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            return 400, {"error": str(exc)}

    if method == "POST" and parsed.path == "/validate-workflow":
        try:
            workflow_request = json.loads(body.decode("utf-8") if body else "{}")
            return 200, agent_api.validate_workflow_request(workflow_request)
        except json.JSONDecodeError as exc:
            return 400, {"error": str(exc)}

    if method == "POST" and parsed.path == "/validate-workflow-batch":
        try:
            batch_request = json.loads(body.decode("utf-8") if body else "{}")
            return 200, agent_api.validate_workflow_batch_request(batch_request)
        except json.JSONDecodeError as exc:
            return 400, {"error": str(exc)}

    return 404, {
        "error": "Unknown route.",
        "routes": [
            "GET /health",
            "GET /policy-presets",
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
            "POST /workflow-batch",
        ],
    }


class AanaAgentHandler(BaseHTTPRequestHandler):
    gallery_path = agent_api.DEFAULT_GALLERY
    max_body_bytes = DEFAULT_MAX_BODY_BYTES
    auth_token = None
    audit_log_path = None

    def do_GET(self):
        self.respond(*route_request("GET", self.path, gallery_path=self.gallery_path))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > self.max_body_bytes:
            self.respond(
                413,
                {
                    "error": "Request body too large.",
                    "max_body_bytes": self.max_body_bytes,
                },
            )
            return
        body = self.rfile.read(length)
        self.respond(
            *route_request(
                "POST",
                self.path,
                body=body,
                gallery_path=self.gallery_path,
                headers=self.headers,
                max_body_bytes=self.max_body_bytes,
                auth_token=self.auth_token,
                audit_log_path=self.audit_log_path,
            )
        )

    def log_message(self, format, *args):
        sys.stderr.write("aana_server: " + format % args + "\n")

    def respond(self, status, payload):
        data = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_handler(gallery_path, max_body_bytes=DEFAULT_MAX_BODY_BYTES, auth_token=None, audit_log_path=None):
    class ConfiguredAanaAgentHandler(AanaAgentHandler):
        pass

    ConfiguredAanaAgentHandler.gallery_path = gallery_path
    ConfiguredAanaAgentHandler.max_body_bytes = max_body_bytes
    ConfiguredAanaAgentHandler.auth_token = auth_token
    ConfiguredAanaAgentHandler.audit_log_path = audit_log_path
    return ConfiguredAanaAgentHandler


def run_server(
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    gallery_path=agent_api.DEFAULT_GALLERY,
    max_body_bytes=DEFAULT_MAX_BODY_BYTES,
    auth_token=None,
    audit_log_path=None,
):
    token = auth_token if auth_token is not None else os.environ.get(DEFAULT_TOKEN_ENV)
    server = ThreadingHTTPServer((host, port), make_handler(gallery_path, max_body_bytes, token, audit_log_path))
    print(f"AANA agent bridge listening on http://{host}:{port}")
    if token:
        print("Auth: bearer token required for POST routes.")
    else:
        print(f"Auth: no token configured. Set {DEFAULT_TOKEN_ENV} to require POST authorization.")
    if audit_log_path:
        print(f"Audit log: {audit_log_path}")
    else:
        print("Audit log: disabled. Pass --audit-log to append redacted gate records.")
    print(f"Max POST body: {max_body_bytes} bytes")
    print("Routes: GET /health, GET /policy-presets, GET /openapi.json, GET /schemas, POST /validate-event, POST /agent-check, POST /validate-workflow, POST /workflow-check, POST /validate-workflow-batch, POST /workflow-batch")
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
        "--audit-log",
        default=None,
        help="Optional JSONL path for redacted audit records from successful gate checks.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    run_server(args.host, args.port, args.gallery, args.max_body_bytes, args.auth_token, args.audit_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
