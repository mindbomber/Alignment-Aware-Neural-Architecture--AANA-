# Agent Event Examples

These are executable AANA agent events. Each file represents a planned agent action that should be checked before the agent sends, recommends, books, or commits to anything.

These examples are for the trusted AANA repository and local development workflow. Do not copy this file-based pattern into a standalone agent skill unless the checker, install metadata, dependencies, and file-handling policy are bundled and reviewed with that skill.

Keep event files minimal and redacted. Do not include secrets, API keys, full payment numbers, bearer tokens, passwords, unrelated private messages, or unnecessary account records. Delete temporary event files after the check unless the user explicitly asks for an audit record.

Run every example:

```powershell
aana run-agent-examples
```

Run one example:

```powershell
aana validate-event --event examples/agent_events/travel_booking.json
aana agent-check --event examples/agent_events/travel_booking.json
```

Create a new starter event from a gallery adapter:

```powershell
aana scaffold-agent-event support_reply --output-dir examples/agent_events
```

Then replace `candidate_action` with the action your agent is about to take and replace `available_evidence` with the verified context the gate should use.

HTTP bridge flow:

```powershell
$event = Get-Content examples/agent_events/support_reply.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/validate-event -Body $event -ContentType 'application/json'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/agent-check -Body $event -ContentType 'application/json'
```

Current examples:

- `support_reply.json`: support draft invents account facts and private payment detail.
- `travel_booking.json`: travel plan violates budget, transport, lunch, and ticket caps.
- `meal_planning.json`: meal plan violates budget, diet rules, and requested week coverage.
- `research_summary.json`: research brief invents a citation, overstates evidence, and omits uncertainty.

These are starter integration tests, not production policies. Production use should connect the same event shape to live data, stronger verifiers, audit logs, and review boundaries.
