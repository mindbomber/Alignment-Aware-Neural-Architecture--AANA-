# AANA HTTP Bridge Runbook

This runbook covers the local AANA HTTP bridge used by external agent frameworks, tools, and pilot surfaces.

The bridge is a gate service. It does not execute downstream actions. A caller sends a planned answer or action, the bridge returns an AANA decision, and the caller must obey `gate_decision`, `recommended_action`, and AIx hard blockers before continuing.

## Start

Development default:

```powershell
python scripts/aana_server.py --host 127.0.0.1 --port 8765
```

Production-like local run:

```powershell
$env:AANA_BRIDGE_TOKEN = "replace-with-a-long-random-token"
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/aana-bridge.jsonl --rate-limit-per-minute 120 --max-body-bytes 1048576
```

Token-file run with rotation support:

```powershell
Set-Content -Path .runtime/aana-bridge-token.txt -Value "replace-with-a-long-random-token"
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --auth-token-file .runtime/aana-bridge-token.txt --audit-log eval_outputs/audit/aana-bridge.jsonl
```

When `--auth-token-file` is used, the bridge rereads the file on every POST request. Rotate by writing a new token to the file atomically in the host environment, then update clients. If the file cannot be read, POST routes return `503 auth_token_unavailable` instead of falling back to open access.

## Routes

Read-only routes:

- `GET /health`: liveness check for the process.
- `GET /ready`: dependency readiness for gallery loading, auth configuration, and audit-log parent directory.
- `GET /policy-presets`: starter policy presets for agent integrations.
- `GET /openapi.json`: machine-readable HTTP contract.
- `GET /schemas`: full schema catalog.

POST routes:

- `POST /validate-event`
- `POST /agent-check`
- `POST /validate-workflow`
- `POST /workflow-check`
- `POST /validate-workflow-batch`
- `POST /workflow-batch`

Clients authenticate POST requests with either:

```text
Authorization: Bearer <token>
```

or:

```text
X-AANA-Token: <token>
```

## Limits

`--max-body-bytes` rejects oversized POST bodies with `413 request_body_too_large`.

`--rate-limit-per-minute` applies a per-client POST limit in the bridge process. Use `0` to disable. In production, keep this bridge limit as a local guard and enforce stronger tenant-aware limits at the reverse proxy or API gateway.

`--read-timeout-seconds` sets the socket read timeout for POST request bodies. If a client stalls while sending the body, the bridge returns `408 request_timeout`. Adapter execution should still be bounded by the process supervisor, deployment platform, or caller timeout; the bridge does not kill in-flight Python adapter execution mid-function because doing so could create ambiguous audit and correction state.

## Errors

Errors use a stable JSON shape while preserving the legacy `error` string:

```json
{
  "error": "Unauthorized.",
  "error_code": "unauthorized",
  "status": 401
}
```

Common codes:

- `unauthorized`
- `auth_token_unavailable`
- `request_body_too_large`
- `rate_limited`
- `request_timeout`
- `invalid_json`
- `bad_request`
- `audit_append_failed`
- `unknown_route`

## Audit

When `--audit-log` is set, successful `/agent-check`, `/workflow-check`, and `/workflow-batch` calls append redacted audit records from the server process.

Audit guarantees:

- unauthenticated POST requests do not append audit records,
- validation-only routes do not append gate audit records,
- check routes return `500 audit_append_failed` if the bridge cannot append the required audit record,
- workflow batches append one redacted per-item workflow record,
- concurrent server-side appends are protected by a process-local lock,
- audit records contain fingerprints and decision metadata, not raw prompts, candidates, evidence, safe responses, or outputs.

The JSONL file is a local handoff format. Production deployments still need append-only storage, retention policy, access controls, backup, monitoring, and incident handling.

## Readiness

Use readiness before routing traffic:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8765/ready
```

`/ready` returns `200` when required local dependencies are usable and `503` when a required dependency fails. Missing auth or missing audit logging are warnings unless the deployment policy requires them; production release manifests should require both.

## Pilot Check

Run the bridge smoke test:

```powershell
$env:AANA_BRIDGE_TOKEN = "replace-with-a-long-random-token"
python scripts/pilot_smoke_test.py --audit-log eval_outputs/audit/aana-pilot-smoke.jsonl
```

Against an already-running bridge:

```powershell
python scripts/pilot_smoke_test.py --base-url http://127.0.0.1:8765 --token $env:AANA_BRIDGE_TOKEN --audit-log eval_outputs/audit/aana-pilot-smoke.jsonl
```

## Deployment Checklist

- Bind the Python bridge to `127.0.0.1` behind a reverse proxy unless the deployment environment provides equivalent network isolation.
- Terminate TLS outside the bridge.
- Use `AANA_BRIDGE_TOKEN`, `--auth-token`, or preferably `--auth-token-file`.
- Rotate tokens through the environment secret manager or token file, then update clients.
- Set `--max-body-bytes` to the smallest payload size that supports the selected workflows.
- Set `--rate-limit-per-minute` and enforce external tenant-aware rate limits.
- Set `--audit-log` to a reviewed local path or adapter that forwards to append-only storage.
- Monitor `/health`, `/ready`, HTTP status counts, audit append failures, gate decisions, recommended actions, AIx scores, and hard blockers.
- Keep caller timeouts shorter than the surrounding workflow timeout, and use the process supervisor for hard execution limits.
- Treat `revise`, `ask`, `defer`, and `refuse` as action-routing decisions the caller must handle before any irreversible tool call.
