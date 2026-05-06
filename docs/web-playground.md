# AANA Web Playground

The local web playground lets a non-engineer try adapter gallery demos without
memorizing CLI commands. It runs from the same HTTP bridge as the agent and
workflow APIs, so the browser can call AANA checks without CORS or extra setup.

## Start

With Python:

```powershell
python scripts/run_playground.py
```

With Docker:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:8765/playground
```

Open a specific adapter from the gallery:

```text
http://localhost:8765/playground?adapter=email_send_guardrail
```

Support adapter deep links:

```text
http://localhost:8765/playground?adapter=support_reply
http://localhost:8765/playground?adapter=crm_support_reply
http://localhost:8765/playground?adapter=ticket_update_checker
```

For the curated everyday-action demo surface, open:

```text
http://localhost:8765/demos
```

For the public searchable adapter gallery, open:

```text
http://localhost:8765/adapter-gallery
```

The local demo token is `aana-local-dev-token` unless you set
`AANA_BRIDGE_TOKEN` or pass `--auth-token`.

## What A User Can Do

1. Pick an adapter from the gallery.
2. Edit the request and candidate answer or action.
3. Optionally add evidence and constraints.
4. Choose an allowed-action fallback preset.
5. Run the AANA check.
6. Inspect the gate decision, recommended action, final AIx score, candidate
   AIx score, verifier violations, safe response, and redacted audit record.

The published adapter gallery links each detail pane to this playground with an
adapter query parameter. That makes the non-engineer trial path:

```text
docker compose up --build
open /adapter-gallery
choose adapter
click Try this adapter
click Run AANA Check
```

The playground calls `POST /playground/check`. The response includes the same
Workflow Contract result shape used by `/workflow-check`, plus a redacted audit
record preview. If the bridge was launched with `--audit-log`, the record is
also appended to the configured JSONL audit log.

## Endpoint Summary

- `GET /playground` serves the local UI.
- `GET /playground/gallery` returns adapter gallery demo metadata.
- `GET /adapter-gallery` serves the searchable published adapter catalog.
- `GET /adapter-gallery/data.json` returns public adapter metadata with risk
  tier, required evidence, supported surfaces, examples, and AIx tuning.
- `GET /demos` serves the curated desktop/browser action demos.
- `GET /demos/scenarios` returns synthetic demo evidence for email, files,
  calendar, purchase/booking, and research grounding.
- `POST /playground/check` runs one Workflow Contract check and returns the
  result plus audit preview.

For production pilots, replace the local demo token, use reviewed evidence
connectors, and keep the audit log in an approved append-only store.
