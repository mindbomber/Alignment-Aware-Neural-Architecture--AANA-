# AANA Local Desktop/Browser Demos

The local desktop/browser demos are a curated surface for everyday irreversible
actions. They use synthetic evidence and the same HTTP bridge, Workflow
Contract, AIx scoring, correction policy, and redacted audit path as the rest of
the AANA runtime.

## Start

With Python:

```powershell
python scripts/demos/run_local_demos.py
```

With Docker:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:8765/demos
```

The default local token is `aana-local-dev-token` unless `AANA_BRIDGE_TOKEN` or
`--auth-token` is set.

## Included Demos

- Email send guardrail: recipient, intent, private data, attachments, and send
  approval.
- File operation guardrail: delete, move, write scope, backup status, user
  confirmation, and path safety.
- Calendar scheduling guardrail: availability, timezone, attendees, conflicts,
  and consent before sending invites.
- Purchase/booking guardrail: price, vendor, refundability, irreversible
  payment, and user confirmation.
- Research grounding checker: citations, source boundaries, unsupported claims,
  and uncertainty.
- Publication check: publication claims, citations, private information,
  brand/legal risk, and approval before publishing.
- Meeting summary checker: transcript faithfulness, action items, attribution,
  sensitive content, and distribution scope.

## What A User Can Do

1. Pick one of the seven everyday-action demos.
2. Edit the proposed action or answer.
3. Edit synthetic evidence facts such as recipient metadata, backup status,
   free/busy, cart details, source registry, publication approval, or meeting
   metadata.
4. Choose the allowed-action preset for the action surface.
5. Run the AANA check.
6. Inspect the gate decision, recommended action, candidate AIx, final AIx,
   verifier findings, safe response, and redacted audit preview.

The UI calls `GET /demos/scenarios` for the scenario bundle and
`POST /playground/check` for the actual Workflow Contract check. Launching the
bridge with `--audit-log` appends the same redacted audit record preview shown
in the browser.

## Files

- `web/demos/` contains the local browser UI.
- `examples/local_action_demos.json` contains synthetic scenario data and
  evidence templates.
- `scripts/demos/run_local_demos.py` starts the bridge with demo audit logging.

For real pilots, replace synthetic evidence with reviewed evidence connectors
and keep direct action blocked unless AANA returns `gate_decision: pass`,
`recommended_action: accept`, and no AIx hard blockers.
