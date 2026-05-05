# Use AANA In Shadow Mode

Use this recipe when you want to evaluate AANA beside an existing workflow without blocking production behavior. Shadow mode still records what AANA would have done.

## Copy

Run a batch in observe-only mode:

```powershell
python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json --audit-log eval_outputs/audit/recipes/shadow-mode.jsonl --shadow-mode
```

Export metrics:

```powershell
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/recipes/shadow-mode.jsonl --output eval_outputs/audit/recipes/shadow-mode-metrics.json
```

Start the local dashboard:

```powershell
$env:AANA_BRIDGE_TOKEN = "aana-local-dev-token"
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/recipes/shadow-mode.jsonl --shadow-mode
```

Open:

```text
http://127.0.0.1:8765/dashboard
```

## HTTP Per-Request Shadow Mode

Use `?shadow_mode=true` when only one request should be observe-only:

```powershell
$workflow = Get-Content examples/workflow_deployment_readiness.json -Raw
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/workflow-check?shadow_mode=true" -Headers @{ Authorization = "Bearer $env:AANA_BRIDGE_TOKEN" } -ContentType "application/json" -Body $workflow
```

## Expected Result

CLI and HTTP responses include `execution_mode: shadow`, `shadow_observation`, and `production_decision.production_effect: not_blocked`. The metrics export includes:

- `shadow_records_total`
- `shadow_would_pass_count`
- `shadow_would_revise_count`
- `shadow_would_defer_count`
- `shadow_would_refuse_count`

Use the would-block and would-intervene rates to decide which adapters are worth enforcing first.
