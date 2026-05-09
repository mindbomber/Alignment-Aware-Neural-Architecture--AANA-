"""Prototype ChatGPT App / MCP HTTP server for AANA.

This is a small prototype, not a submission-ready public ChatGPT App. It exposes
the standard AANA `aana_pre_tool_check` MCP tool over a simple HTTP JSON-RPC
endpoint and serves the optional decision-viewer resource.
"""

from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from eval_pipeline import mcp_server


def create_app() -> FastAPI:
    app = FastAPI(
        title="AANA ChatGPT App Prototype",
        version="0.1.0",
        description="Prototype MCP-style ChatGPT App surface for AANA pre-tool checks.",
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "aana-chatgpt-app-prototype",
            "archetype": "tool-only-with-optional-widget",
            "mcp_endpoint": "/mcp",
            "tools": [tool["name"] for tool in mcp_server.list_tools()],
            "resources": [resource["uri"] for resource in mcp_server.list_resources()],
        }

    @app.post("/mcp")
    def mcp_endpoint(message: dict[str, Any] | list[dict[str, Any]] = Body(...)):
        if isinstance(message, list):
            responses = [mcp_server.handle_jsonrpc(item) for item in message]
            return JSONResponse([item for item in responses if item is not None])
        response = mcp_server.handle_jsonrpc(message)
        return JSONResponse(response or {})

    @app.get("/aana-decision.html", response_class=HTMLResponse)
    def decision_viewer() -> str:
        return mcp_server.AANA_DECISION_VIEWER_HTML

    return app


app = create_app()


def main() -> int:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - optional dependency path.
        raise SystemExit("Install the api extra first: pip install -e .[api]") from exc

    uvicorn.run(app, host="127.0.0.1", port=8770)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
