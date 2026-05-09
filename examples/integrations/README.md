# AANA Integration Examples

These examples show the adoption path:

```text
agent proposes -> AANA checks -> tool executes only if allowed
```

Each example is dependency-light and runnable from this repo without installing
the target framework. The comments show where the same wrapper is registered in
the real framework.

## Run

```powershell
python examples/integrations/openai_agents_sdk.py
python examples/integrations/openai_agents/demo.py
python examples/integrations/openai_agents/wrapped_tools.py
python examples/integrations/openai_agents/api_guard.py
python examples/integrations/langchain.py
python examples/integrations/autogen.py
python examples/integrations/crewai.py
python examples/integrations/mcp.py
python evals/openai_agents_aana/run_local.py
python evals/aana_controlled_agents/run_local.py
python scripts/aana_mcp_server.py --list-tools
python examples/chatgpt_app/aana_mcp_app.py
python scripts/validate_agent_integrations.py
```

## Examples

- `openai_agents_sdk.py`: wrap a function before registering it as an OpenAI Agents SDK tool.
- `openai_agents/`: repo-owned OpenAI Agents SDK demo with a side-effect ledger proving blocked tools do not execute.
- `openai_agents/wrapped_tools.py`: OpenAI Agents SDK-style functions wrapped with AANA before `function_tool(...)` registration.
- `openai_agents/api_guard.py`: HTTP-only guard for apps that call AANA FastAPI instead of importing the package.
- `langchain.py`: wrap a LangChain-style `.invoke(...)` tool.
- `autogen.py`: decorate an AutoGen-style registered function.
- `crewai.py`: wrap a CrewAI-style `_run(...)` tool object.
- `mcp.py`: wrap an MCP handler that receives tool-call arguments.
- `../../scripts/aana_mcp_server.py`: tool-only MCP-style surface exposing `aana_pre_tool_check`.
- `../chatgpt_app/`: FastAPI-hosted ChatGPT Apps/MCP prototype with `/mcp` and an optional decision viewer.
- `../../evals/openai_agents_aana/`: local OpenAI-style agent eval harness for guarded tool execution.
- `../../evals/aana_controlled_agents/`: multi-surface eval harness comparing permissive, SDK, API, and MCP controlled-agent paths.
- `../../scripts/validate_agent_integrations.py`: one-command validation for the OpenAI, FastAPI, MCP, and controlled-agent eval stack.

For write actions and private reads, pass metadata with authorization and
evidence. For public reads, one-line wrapping is enough:

```python
guarded = aana.wrap_agent_tool(get_public_status)
```
