# AANA Agent Action Contract v1 Space

This local Hugging Face Space artifact is the repo-owned source for the public
"try AANA" demo. It accepts the frozen Agent Action Contract v1 fields and
returns the same route decision used by the Python SDK, FastAPI service, and MCP
tool.

Frozen required fields:

- `tool_name`
- `tool_category`
- `authorization_state`
- `evidence_refs`
- `risk_domain`
- `proposed_arguments`
- `recommended_route`

The Space should call `aana.check_tool_call` with these fields and display
`accept`, `ask`, `defer`, or `refuse` along with AIx score, hard blockers,
evidence refs, authorization state, recovery guidance, and an audit-safe log
event.
