# Use AANA With CRM Support Drafts

Use this recipe to check customer-facing support replies before an agent or support tool sends them. The CRM support adapter checks account facts, refund eligibility, private data, tone, and policy promises.

## Copy

Run the included CRM support workflow:

```powershell
python scripts/aana_cli.py workflow-check --workflow examples/workflow_crm_support_reply.json --evidence-registry examples/evidence_registry.json --require-structured-evidence --audit-log eval_outputs/audit/recipes/crm-support.jsonl
```

For HTTP integrations, start the bridge:

```powershell
$env:AANA_BRIDGE_TOKEN = "aana-local-dev-token"
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/recipes/crm-support.jsonl
```

Then post the Workflow Contract:

```powershell
$workflow = Get-Content examples/workflow_crm_support_reply.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/workflow-check -Headers @{ Authorization = "Bearer $env:AANA_BRIDGE_TOKEN" } -ContentType "application/json" -Body $workflow
```

## Evidence Expected

Use structured evidence objects from:

- `crm-record`
- `support-policy`
- `order-system`

Each object should include `source_id`, `retrieved_at`, `trust_tier`, `redaction_status`, and `text`. The checked-in workflow uses synthetic redacted evidence.

## Expected Result

The sample candidate invents an order ID, promises a refund, exposes payment details, and leaks an internal note. AANA should reject direct acceptance and return a safer support response that asks the customer to use secure verification or routes to human support.

Review metrics:

```powershell
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/recipes/crm-support.jsonl --output eval_outputs/audit/recipes/crm-support-metrics.json
```
