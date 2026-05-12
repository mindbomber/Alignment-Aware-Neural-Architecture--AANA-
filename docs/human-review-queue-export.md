# AANA Human-Review Queue Export

The runtime human-review export turns redacted AANA audit JSONL into standalone reviewer packets for operations teams. It is the handoff path for `ask`, `defer`, `refuse`, hard blockers, or records marked `human_review_queue.required=true`.

This is a production-candidate workflow artifact, not production certification or go-live approval.

## What It Exports

Each packet includes:

- source record fingerprint and non-sensitive identity fields
- queue, route, priority, triggers, and reason
- gate decision, recommended action, candidate gate, and authorization state
- AIx score, decision, component scores, beta, thresholds, and hard blockers
- violation codes, missing evidence IDs, connector failures, and freshness failures
- evidence source IDs, input fingerprints, and audit-safe decision metadata
- reviewer workflow fields and allowed reviewer decisions

Packets do not include raw prompts, candidate text, evidence text, private records, safe responses, or secrets.

## CLI

```powershell
python scripts/aana_cli.py human-review-export `
  --audit-log eval_outputs/aix_audit/enterprise_ops_pilot/aana-audit.jsonl `
  --queue-output eval_outputs/human_review/runtime-review-queue.jsonl `
  --summary-output eval_outputs/human_review/runtime-review-summary.json `
  --json
```

Write the default config:

```powershell
python scripts/aana_cli.py human-review-export --write-config --json
```

## FastAPI

```http
POST /human-review-export
```

Example body:

```json
{
  "audit_log_path": "eval_outputs/aix_audit/enterprise_ops_pilot/aana-audit.jsonl",
  "queue_path": "eval_outputs/human_review/runtime-review-queue.jsonl",
  "summary_path": "eval_outputs/human_review/runtime-review-summary.json"
}
```

## TypeScript SDK

```ts
await client.humanReviewExport({
  audit_log_path: "eval_outputs/aix_audit/enterprise_ops_pilot/aana-audit.jsonl",
  queue_path: "eval_outputs/human_review/runtime-review-queue.jsonl",
  summary_path: "eval_outputs/human_review/runtime-review-summary.json"
});
```

## Production Boundary

For a real production deployment, customers still need staffed review queues, domain-owner SLAs, access controls, immutable retention, incident routing, and a reviewed process for writing reviewer decisions back into AANA audit metadata.
