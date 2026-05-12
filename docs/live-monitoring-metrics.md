# AANA Live Monitoring Metrics

The live monitoring layer evaluates redacted AANA runtime audit JSONL against production-candidate thresholds. It is intended for shadow-mode and controlled live pilots.

It does not store prompts, candidates, evidence text, safe responses, private records, or secrets.

## Signals

- audit record volume
- AIx average/min score
- AIx hard-blocker rate
- human-review escalation rate
- refusal/defer rate
- connector failure rate
- evidence freshness failure rate
- latency p95 when available
- shadow-mode would-block and would-intervene rates

## CLI

```powershell
python scripts/aana_cli.py live-monitoring `
  --audit-log eval_outputs/aix_audit/enterprise_ops_pilot/aana-audit.jsonl `
  --config examples/live_monitoring_metrics.json `
  --output eval_outputs/monitoring/live-monitoring-report.json `
  --json
```

Write the default config:

```powershell
python scripts/aana_cli.py live-monitoring --write-config --json
```

## FastAPI

```http
POST /live-monitoring
```

```json
{
  "audit_log_path": "eval_outputs/aix_audit/enterprise_ops_pilot/aana-audit.jsonl",
  "config_path": "examples/live_monitoring_metrics.json",
  "output_path": "eval_outputs/monitoring/live-monitoring-report.json"
}
```

## Status Labels

- `healthy`: all configured checks pass
- `warning`: one or more metrics are unavailable
- `critical`: one or more thresholds are breached

This is live monitoring readiness only, not production certification or go-live approval.
