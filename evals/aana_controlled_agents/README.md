# AANA-Controlled Agents Eval Harness

This harness evaluates the core AANA control pattern across multiple runtime
surfaces:

```text
agent proposes -> AANA checks -> tool executes only if allowed
```

It compares:

- `permissive`: executes every proposed tool call.
- `sdk`: uses the in-process Python AANA SDK.
- `api`: uses the FastAPI policy-service path in-process through `TestClient`.
- `mcp`: uses the MCP-style `aana_pre_tool_check` tool.

## Run

```powershell
python evals/aana_controlled_agents/run_local.py
```

The runner writes `evals/aana_controlled_agents/results/latest.json` and exits
non-zero if any AANA-controlled surface fails the behavior matrix.

## What It Measures

- unsafe-action prevention;
- private-read authorization;
- write confirmation;
- unknown-tool and missing-evidence fail-closed behavior;
- safe execution preservation;
- route quality across SDK, API, and MCP surfaces.

This is a local integration harness, not an official benchmark submission.
