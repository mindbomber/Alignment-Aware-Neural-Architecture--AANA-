# Agent Event Examples

These are executable AANA agent events. Each file represents a planned agent action that should be checked before the agent sends, recommends, books, or commits to anything.

Run every example:

```powershell
python scripts/aana_cli.py run-agent-examples
```

Run one example:

```powershell
python scripts/aana_cli.py validate-event --event examples/agent_events/travel_booking.json
python scripts/aana_cli.py agent-check --event examples/agent_events/travel_booking.json
```

Create a new starter event from a gallery adapter:

```powershell
python scripts/aana_cli.py scaffold-agent-event support_reply --output-dir examples/agent_events
```

Then replace `candidate_action` with the action your agent is about to take and replace `available_evidence` with the verified context the gate should use.

Current examples:

- `support_reply.json`: support draft invents account facts and private payment detail.
- `travel_booking.json`: travel plan violates budget, transport, lunch, and ticket caps.
- `meal_planning.json`: meal plan violates budget, diet rules, and requested week coverage.

These are starter integration tests, not production policies. Production use should connect the same event shape to live data, stronger verifiers, audit logs, and review boundaries.
