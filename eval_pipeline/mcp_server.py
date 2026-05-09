"""Dependency-light MCP-style tool surface for AANA.

This module exposes the standard `aana_pre_tool_check` tool. It is intentionally
small and dependency-free so the same handler can be used by ChatGPT Apps,
ordinary MCP clients, tests, and local demos. When an MCP SDK is available,
register `AANA_PRE_TOOL_CHECK_TOOL` and route calls to
`handle_aana_pre_tool_check`.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

import aana


AANA_PRE_TOOL_CHECK_TOOL: dict[str, Any] = {
    "name": "aana_pre_tool_check",
    "title": "AANA pre-tool check",
    "description": (
        "Use this when an agent is about to execute a consequential tool call. "
        "The tool checks the Agent Action Contract v1 and returns accept, ask, "
        "defer, or refuse with AIx score, hard blockers, evidence refs, "
        "authorization state, recovery guidance, and audit-safe metadata."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "tool_name",
            "tool_category",
            "authorization_state",
            "evidence_refs",
            "risk_domain",
            "proposed_arguments",
            "recommended_route",
        ],
        "properties": {
            "tool_name": {"type": "string", "minLength": 1},
            "tool_category": {"type": "string", "enum": ["public_read", "private_read", "write", "unknown"]},
            "authorization_state": {
                "type": "string",
                "enum": ["none", "user_claimed", "authenticated", "validated", "confirmed"],
            },
            "evidence_refs": {
                "type": "array",
                "items": {
                    "anyOf": [
                        {"type": "string", "minLength": 1},
                        {"type": "object", "additionalProperties": True},
                    ]
                },
            },
            "risk_domain": {"type": "string", "minLength": 1},
            "proposed_arguments": {"type": "object", "additionalProperties": True},
            "recommended_route": {"type": "string", "enum": ["accept", "ask", "defer", "refuse"]},
        },
    },
    "annotations": {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    "_meta": {
        "openai/outputTemplate": "ui://aana/decision.html",
        "openai/toolInvocation/invoking": "Checking tool call with AANA",
        "openai/toolInvocation/invoked": "AANA pre-tool check complete",
    },
}


AANA_DECISION_VIEWER_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AANA Decision</title>
  <style>
    body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, sans-serif; background: #f7f7f8; color: #1f2328; }
    main { max-width: 760px; margin: 0 auto; padding: 20px; }
    h1 { font-size: 20px; margin: 0 0 12px; }
    dl { display: grid; grid-template-columns: 160px 1fr; gap: 8px 14px; margin: 0; }
    dt { color: #59636e; }
    dd { margin: 0; font-weight: 600; overflow-wrap: anywhere; }
    pre { margin-top: 16px; padding: 12px; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; overflow: auto; }
  </style>
</head>
<body>
  <main>
    <h1>AANA Pre-Tool Decision</h1>
    <dl>
      <dt>Route</dt><dd id="route">waiting</dd>
      <dt>Execution</dt><dd id="execution">waiting</dd>
      <dt>AIx score</dt><dd id="aix">waiting</dd>
      <dt>Authorization</dt><dd id="auth">waiting</dd>
    </dl>
    <pre id="details">{}</pre>
  </main>
  <script>
    function pickDecision() {
      const openai = window.openai || {};
      return openai.toolOutput || openai.structuredContent || openai.toolResponseMetadata?.aana_decision || {};
    }
    function render(decision) {
      const data = decision.structuredContent || decision;
      document.getElementById("route").textContent = data.route || "unknown";
      document.getElementById("execution").textContent = String(data.execution_allowed ?? false);
      document.getElementById("aix").textContent = data.aix_score == null ? "n/a" : String(data.aix_score);
      document.getElementById("auth").textContent = data.authorization_state || "not declared";
      document.getElementById("details").textContent = JSON.stringify(data, null, 2);
    }
    render(pickDecision());
    window.addEventListener("message", () => render(pickDecision()));
  </script>
</body>
</html>
"""


AANA_DECISION_RESOURCE: dict[str, Any] = {
    "uri": "ui://aana/decision.html",
    "name": "AANA decision viewer",
    "mimeType": "text/html;profile=mcp-app",
    "_meta": {
        "openai/widgetDescription": "Shows the AANA route, execution decision, AIx score, blockers, and audit-safe metadata.",
        "openai/widgetPrefersBorder": True,
        "openai/widgetCSP": {
            "connect_domains": [],
            "resource_domains": [],
        },
    },
}


def list_tools() -> list[dict[str, Any]]:
    """Return MCP tool descriptors exposed by the AANA server."""

    return [AANA_PRE_TOOL_CHECK_TOOL]


def list_resources() -> list[dict[str, Any]]:
    """Return MCP resources exposed by the AANA server."""

    return [AANA_DECISION_RESOURCE]


def read_resource(uri: str) -> dict[str, Any]:
    """Read one MCP resource by URI."""

    if uri != AANA_DECISION_RESOURCE["uri"]:
        raise ValueError(f"Unknown AANA MCP resource: {uri!r}")
    return {
        "contents": [
            {
                "uri": AANA_DECISION_RESOURCE["uri"],
                "mimeType": AANA_DECISION_RESOURCE["mimeType"],
                "text": AANA_DECISION_VIEWER_HTML,
            }
        ]
    }


def _decision_summary(result: dict[str, Any]) -> dict[str, Any]:
    architecture = result.get("architecture_decision") if isinstance(result.get("architecture_decision"), dict) else {}
    policy = result.get("execution_policy") if isinstance(result.get("execution_policy"), dict) else {}
    return {
        "route": result.get("route") or architecture.get("route") or result.get("recommended_action"),
        "execution_allowed": policy.get("execution_allowed", False),
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "aix_score": architecture.get("aix_score"),
        "hard_blockers": architecture.get("hard_blockers", result.get("hard_blockers", [])),
        "evidence_refs": architecture.get("evidence_refs", {}),
        "authorization_state": architecture.get("authorization_state"),
        "correction_recovery_suggestion": architecture.get("correction_recovery_suggestion"),
        "audit_safe_log_event": architecture.get("audit_safe_log_event"),
    }


def handle_aana_pre_tool_check(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle an MCP `aana_pre_tool_check` tool call."""

    result = aana.check_tool_call(arguments)
    summary = _decision_summary(result)
    return {
        "structuredContent": summary,
        "content": [
            {
                "type": "text",
                "text": (
                    f"AANA route: {summary['route']}. "
                    f"Execution allowed: {str(summary['execution_allowed']).lower()}."
                ),
            }
        ],
        "_meta": {
            "aana_decision": result,
            "audit_safe_log_event": summary.get("audit_safe_log_event"),
        },
    }


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Route one MCP tool call by name."""

    if name != AANA_PRE_TOOL_CHECK_TOOL["name"]:
        raise ValueError(f"Unknown AANA MCP tool: {name!r}")
    return handle_aana_pre_tool_check(arguments or {})


def handle_jsonrpc(message: dict[str, Any]) -> dict[str, Any] | None:
    """Handle a tiny JSON-RPC subset useful for local MCP smoke testing."""

    method = message.get("method")
    request_id = message.get("id")
    try:
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": list_tools()}}
        if method == "tools/call":
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            result = call_tool(str(params.get("name") or ""), params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        if method == "resources/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"resources": list_resources()}}
        if method == "resources/read":
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            return {"jsonrpc": "2.0", "id": request_id, "result": read_resource(str(params.get("uri") or ""))}
        if method in {"initialize", "notifications/initialized"}:
            if method == "notifications/initialized":
                return None
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "aana-mcp", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            }
        raise ValueError(f"Unsupported JSON-RPC method: {method!r}")
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": str(exc)},
        }


def stdio_loop(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    """Run a minimal newline-delimited JSON-RPC loop."""

    for line in stdin:
        if not line.strip():
            continue
        response = handle_jsonrpc(json.loads(line))
        if response is not None:
            stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for local MCP smoke testing."""

    argv = argv or sys.argv[1:]
    if argv == ["--list-tools"]:
        print(json.dumps({"tools": list_tools()}, indent=2, sort_keys=True))
        return 0
    return stdio_loop()


if __name__ == "__main__":
    raise SystemExit(main())
