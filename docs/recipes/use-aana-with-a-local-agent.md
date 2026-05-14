# Use AANA With A Local Agent

Use this recipe when a local agent is about to send, publish, book, buy, edit files, answer from uncertain evidence, or make a support promise.

## Copy

Start the installed FastAPI policy service with token auth and redacted audit logging:

```powershell
$env:AANA_BRIDGE_TOKEN = "aana-local-dev-token"
aana-fastapi --host 127.0.0.1 --port 8766 --audit-log eval_outputs/audit/recipes/local-agent.jsonl --rate-limit-per-minute 120
```

Check the included support-reply event:

```powershell
$event = Get-Content examples/agent_event_support_reply.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8766/agent-check -Headers @{ Authorization = "Bearer $env:AANA_BRIDGE_TOKEN" } -ContentType "application/json" -Body $event
```

The same event can be checked through the CLI:

```powershell
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/recipes/local-agent.jsonl
```

## Agent Rule

Before the agent proceeds, inspect the response:

```text
Proceed only when gate_decision=pass, recommended_action=accept, aix.decision=accept, and aix.hard_blockers is empty.
Otherwise follow recommended_action: revise, ask, retrieve, defer, or refuse.
```

## Expected Result

The checked-in event proposes a refund reply with invented order and payment facts. AANA should return a non-accepting action, typically `revise`, with a safer support response and redacted audit record.

Review the audit log:

```powershell
python scripts/aana_cli.py audit-summary --audit-log eval_outputs/audit/recipes/local-agent.jsonl
```
