# AANA MCP / ChatGPT App Direction

AANA exposes a tool-only MCP-style surface for agent runtimes that want a
standard pre-execution control point:

```text
agent proposes consequential tool call
-> call aana_pre_tool_check
-> execute original tool only when route is accept
```

## Tool

`aana_pre_tool_check` accepts the public Agent Action Contract v1 fields:

- `tool_name`
- `tool_category`
- `authorization_state`
- `evidence_refs`
- `risk_domain`
- `proposed_arguments`
- `recommended_route`

It returns:

- `structuredContent`: route, execution permission, AIx score, blockers,
  evidence refs, authorization state, recovery guidance, and audit-safe metadata.
- `content`: short model-visible summary.
- `_meta`: full AANA decision and audit-safe event for the host runtime.

## Local Smoke

List tools:

```powershell
python scripts/integrations/aana_mcp_server.py --list-tools
```

Call through the minimal newline-delimited JSON-RPC loop:

```powershell
'{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python scripts/integrations/aana_mcp_server.py
```

For a real MCP SDK or ChatGPT Apps server, register the descriptor from
`eval_pipeline.mcp_server.AANA_PRE_TOOL_CHECK_TOOL` and route calls to
`eval_pipeline.mcp_server.handle_aana_pre_tool_check(...)`.

## ChatGPT Apps Shape

This is currently a `tool-only` app archetype. A widget is not required for the
core control layer. A later ChatGPT App can add a small audit widget that renders
the `structuredContent` decision, blockers, missing evidence, and recovery
suggestion.

## Prototype HTTP App

A minimal ChatGPT Apps-style prototype lives in `examples/chatgpt_app/`:

```powershell
python examples/chatgpt_app/aana_mcp_app.py
```

It exposes:

- `GET /health`
- `POST /mcp`
- `GET /aana-decision.html`

Use `/mcp` as the local MCP endpoint when testing through an HTTPS tunnel. The
HTML resource is intentionally small and reads the tool output exposed by the
host environment.

Keep the enforcement boundary in the host runtime: the model can call
`aana_pre_tool_check`, but the actual side-effecting tool should still be
wrapped so it cannot run unless the host sees an AANA `accept` decision.
