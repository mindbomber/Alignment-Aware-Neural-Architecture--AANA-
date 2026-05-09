# AANA FastAPI Service

AANA can run as a small FastAPI service for agent runtimes that need a simple HTTP control layer.

The service exposes AANA as:

```text
agent/app proposes -> AANA API checks -> agent/app executes only if allowed
```

This is the right integration mode for OpenAI-powered apps that should use AANA
without importing the Python package. The app sends proposed tool calls to
`POST /pre-tool-check`, checks the returned route and execution policy, and only
then runs the original tool body.

## Start

```powershell
$env:AANA_BRIDGE_TOKEN = "replace-with-a-local-secret"
python scripts/aana_fastapi.py --host 127.0.0.1 --port 8766 --audit-log eval_outputs/audit/aana-fastapi.jsonl
```

FastAPI serves OpenAPI JSON at `/openapi.json` and Swagger UI at `/docs`.

## Routes

- `GET /health`
- `POST /pre-tool-check`
- `POST /agent-check`
- `GET /openapi.json`
- `GET /docs`

`/docs` includes interactive request examples for both POST routes.

POST routes use token auth when `AANA_BRIDGE_TOKEN` or `--auth-token` is configured. Send either:

```http
Authorization: Bearer <token>
```

or:

```http
X-AANA-Token: <token>
```

## Production Auth Guidance

Local-only is the default posture: run on `127.0.0.1` unless the service is
behind an internal gateway, service mesh, or reverse proxy with TLS. Do not bind
to `0.0.0.0` for public internet exposure without an authenticated internal
deployment boundary.

Use a high-entropy bearer token for POST routes:

```powershell
$env:AANA_BRIDGE_TOKEN = "<random-32-byte-or-longer-secret>"
$env:AANA_BRIDGE_TOKEN_SCOPES = "pre_tool_check,agent_check"
```

Scopes are route-level:

- `pre_tool_check` allows `POST /pre-tool-check`
- `agent_check` allows `POST /agent-check`

Rotation is operationally simple because AANA does not store sessions: deploy a
new token through your secret manager, restart the service, update clients, then
retire the old secret. For multi-client production use, put AANA behind an
internal gateway that handles per-client tokens, rotation windows, mTLS, and
central audit.

The legacy `X-AANA-Token` header is supported for local tools. Prefer
`Authorization: Bearer <token>` for production clients.

## Limits

The service applies dependency-light local limits:

```powershell
$env:AANA_RATE_LIMIT_PER_MINUTE = "60"
$env:AANA_MAX_REQUEST_BYTES = "65536"
python scripts/aana_fastapi.py --rate-limit-per-minute 60 --max-request-bytes 65536
```

`AANA_RATE_LIMIT_PER_MINUTE` is an in-memory per-client limit intended to protect
local and internal deployments. Use gateway-level distributed rate limiting for
multi-instance deployments.

`AANA_MAX_REQUEST_BYTES` rejects oversized POST bodies before the check runs.
Keep raw prompts, private records, files, and large retrieval payloads out of
the API; pass redacted evidence refs and compact summaries instead.

## Enforcement And Shadow Mode

The API defaults to enforcement decisions. A tool should execute only when the
response includes:

- `gate_decision: "pass"`
- `recommended_action: "accept"`
- `architecture_decision.route: "accept"`
- no hard blockers
- no schema or contract validation errors

Add `?shadow_mode=true` to observe what AANA would do without blocking the host
application's production path. Shadow mode is explicit in the response with
`execution_mode: "shadow"` and `shadow_observation.enforcement: "observe_only"`.

## Pre-Tool Check

Use `/pre-tool-check` for the public [Agent Action Contract v1](agent-action-contract-v1.md). Example payloads are checked in under `examples/api/`.

Agent Action Contract v1 freezes these seven required request fields:

- `tool_name`
- `tool_category`
- `authorization_state`
- `evidence_refs`
- `risk_domain`
- `proposed_arguments`
- `recommended_route`

```powershell
$body = Get-Content examples/api/pre_tool_check_write_ask.json -Raw

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8766/pre-tool-check `
  -Headers @{ Authorization = "Bearer $env:AANA_BRIDGE_TOKEN" } `
  -Body $body `
  -ContentType "application/json"
```

Expected route: `ask`, because a write action with only `user_claimed` authorization needs validation and/or confirmation before execution.

Confirmed write example:

```powershell
$body = Get-Content examples/api/pre_tool_check_confirmed_write.json -Raw

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8766/pre-tool-check `
  -Headers @{ "X-AANA-Token" = $env:AANA_BRIDGE_TOKEN } `
  -Body $body `
  -ContentType "application/json"
```

## Agent Check

Use `/agent-check` for adapter-backed Agent Event checks such as support replies, grounded answers, and policy-bound messages.

```powershell
$event = Get-Content examples/api/agent_check_support_reply.json -Raw

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8766/agent-check `
  -Headers @{ Authorization = "Bearer $env:AANA_BRIDGE_TOKEN" } `
  -Body $event `
  -ContentType "application/json"
```

## OpenAI Agent API Guard

The repo includes an HTTP-only OpenAI-style guard:

```powershell
$env:AANA_BRIDGE_TOKEN = "local-dev-secret"
python scripts/aana_fastapi.py --host 127.0.0.1 --port 8766

$env:AANA_API_URL = "http://127.0.0.1:8766"
python examples/integrations/openai_agents/api_guard.py
```

In an app, wrap the side-effecting tool:

```python
from examples.integrations.openai_agents.api_guard import AANAApiGuard, send_email

guard = AANAApiGuard(
    base_url="http://127.0.0.1:8766",
    token="<local-token>",
)

guarded_send_email = guard.guard_tool(
    send_email,
    tool_name="send_email",
    tool_category="write",
    authorization_state="user_claimed",
    evidence_refs=["draft_id:123"],
    risk_domain="customer_support",
)

result = guarded_send_email(to="customer@example.com", body="Needs confirmation")
```

If AANA returns `ask`, `defer`, or `refuse`, `result` is a blocked envelope and
the original `send_email` body is not called.

## Audit Logging

Pass `--audit-log path/to/audit.jsonl` to append redacted JSONL audit records.

For `/pre-tool-check`, the service does not log raw tool arguments. It stores:

- tool name/category
- authorization state
- risk domain
- recommended route
- evidence ref count
- proposed argument keys only
- final route, AIx score, blockers, evidence refs used/missing, and latency

For `/agent-check`, the service reuses the existing AANA redacted Agent Event audit record.

Audit records are JSONL and intentionally redacted. They are suitable for
operational review and metrics, not for reconstructing raw user prompts or
private tool arguments. Store them in append-only internal storage when used for
production audits.

## Deployment Examples

Local development:

```powershell
$env:AANA_BRIDGE_TOKEN = "local-dev-secret"
python scripts/aana_fastapi.py --host 127.0.0.1 --port 8766 --audit-log eval_outputs/audit/aana-fastapi.jsonl
```

Docker:

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY . /app
RUN pip install -e .[api]
ENV AANA_RATE_LIMIT_PER_MINUTE=60
ENV AANA_MAX_REQUEST_BYTES=65536
CMD ["python", "scripts/aana_fastapi.py", "--host", "127.0.0.1", "--port", "8766", "--audit-log", "eval_outputs/audit/aana-fastapi.jsonl"]
```

Internal service:

```powershell
$env:AANA_BRIDGE_TOKEN = "<secret-manager-injected-token>"
$env:AANA_BRIDGE_TOKEN_SCOPES = "pre_tool_check,agent_check"
python scripts/aana_fastapi.py `
  --host 127.0.0.1 `
  --port 8766 `
  --rate-limit-per-minute 120 `
  --max-request-bytes 65536 `
  --audit-log eval_outputs/audit/aana-fastapi.jsonl
```

Terminate TLS, authenticate callers, and perform distributed rate limiting at
the internal ingress. Keep the AANA service itself private and local to the
agent runtime or trusted internal network.

## Curl

```bash
curl -s http://127.0.0.1:8766/pre-tool-check \
  -H "Authorization: Bearer $AANA_BRIDGE_TOKEN" \
  -H "Content-Type: application/json" \
  --data @examples/api/pre_tool_check_write_ask.json
```
