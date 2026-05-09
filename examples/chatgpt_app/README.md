# AANA ChatGPT App / MCP Prototype

This prototype exposes AANA as a ChatGPT Apps-style MCP server.

Archetype: `tool-only-with-optional-widget`.

## Tool

The app exposes one standard tool:

```text
aana_pre_tool_check
```

Use it when an agent is about to execute a consequential tool call. The tool
accepts the public Agent Action Contract v1 fields and returns route,
execution permission, AIx score, blockers, evidence refs, authorization state,
recovery guidance, and audit-safe metadata.

## Run

```powershell
python examples/chatgpt_app/aana_mcp_app.py
```

Then check:

```powershell
Invoke-RestMethod http://127.0.0.1:8770/health
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8770/mcp `
  -ContentType "application/json" `
  -Body '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## ChatGPT Developer Mode Shape

For local ChatGPT testing, expose the local server with an HTTPS tunnel and use:

```text
https://<your-tunnel>/mcp
```

This prototype is not submission-ready yet. Before public submission, harden the
transport, production auth, deployment domain, privacy policy, screenshots,
review prompts, and any widget CSP/resource metadata.

## Why This Shape

The enforcement boundary remains in the host runtime:

```text
agent proposes -> aana_pre_tool_check -> execute original tool only if accept
```

The model can request AANA's decision, but the side-effecting tool still needs a
runtime wrapper that refuses to execute unless AANA returns `accept`.
