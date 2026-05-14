# AANA Shadow Mode

Shadow mode lets early users run AANA beside an existing production workflow
without changing production behavior. AANA still checks proposed actions, writes
redacted audit telemetry, and exports metrics, but the integration treats the
decision as observe-only.

## Guarantees

- AANA does not execute, send, delete, book, publish, export, deploy, or commit
  anything.
- Shadow audit records store redacted decision metadata only: adapter, gate,
  recommended action, AIx summary, violation codes, fingerprints, and shadow
  would-action fields.
- Raw request, candidate, evidence, constraints, safe response, and output text
  remain prohibited in audit JSONL.
- CLI checks return a non-blocking exit code when `--shadow-mode` is set.
- HTTP checks include `execution_mode: shadow`, `shadow_observation`, and
  `production_decision.production_effect: not_blocked`.

## CLI

Agent event:

```powershell
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl --shadow-mode
```

Workflow:

```powershell
python scripts/aana_cli.py workflow-check --workflow examples/workflow_research_summary.json --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl --shadow-mode
```

Batch:

```powershell
python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl --shadow-mode
```

Export the dashboard metrics:

```powershell
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl --output eval_outputs/audit/shadow/aana-shadow-metrics.json
```

The metrics export includes:

- `shadow_records_total`
- `shadow_would_action_count`
- `shadow_would_pass_count`
- `shadow_would_revise_count`
- `shadow_would_defer_count`
- `shadow_would_refuse_count`

## FastAPI Service

Start the installed FastAPI policy service:

```powershell
$env:AANA_BRIDGE_TOKEN = "aana-local-dev-token"
aana-fastapi --host 127.0.0.1 --port 8766 --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl
```

Enable shadow mode for one request:

```powershell
Invoke-RestMethod "http://127.0.0.1:8766/workflow-check?shadow_mode=true" -Method Post -Headers @{ Authorization = "Bearer $env:AANA_BRIDGE_TOKEN" } -ContentType "application/json" -Body (Get-Content examples/workflow_research_summary.json -Raw)
```

The service still returns the AANA recommendation, but the response explicitly
marks the production effect as `not_blocked`.

## Repo-Local Dashboard

The dashboard route is part of the legacy repo-local bridge, not the installed
FastAPI policy service. Use it only when you need the local dashboard UI:

```powershell
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl --shadow-mode
```

Open:

```text
http://127.0.0.1:8765/dashboard
```

## Interpreting Would Actions

Shadow metrics normalize AANA recommendations into four dashboard routes:

- `would-pass`: AANA would accept the action.
- `would-revise`: AANA would require revision, retrieval, or clarification.
- `would-defer`: AANA would route to human review or stronger evidence.
- `would-refuse`: AANA would refuse the proposed action.

Use shadow mode to identify high-value adapters, missing evidence connectors,
over-refusal, and review-queue volume before turning on enforcement.
