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
python examples/integrations/openai_agents/api_guard.py
python examples/integrations/langchain.py
python examples/integrations/autogen.py
python examples/integrations/crewai.py
python examples/integrations/mcp.py
```

## Examples

- `openai_agents_sdk.py`: wrap a function before registering it as an OpenAI Agents SDK tool.
- `openai_agents/`: repo-owned OpenAI Agents SDK demo with a side-effect ledger proving blocked tools do not execute.
- `openai_agents/api_guard.py`: HTTP-only guard for apps that call AANA FastAPI instead of importing the package.
- `langchain.py`: wrap a LangChain-style `.invoke(...)` tool.
- `autogen.py`: decorate an AutoGen-style registered function.
- `crewai.py`: wrap a CrewAI-style `_run(...)` tool object.
- `mcp.py`: wrap an MCP handler that receives tool-call arguments.

For write actions and private reads, pass metadata with authorization and
evidence. For public reads, one-line wrapping is enough:

```python
guarded = aana.wrap_agent_tool(get_public_status)
```
