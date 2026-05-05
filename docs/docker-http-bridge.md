# Dockerized AANA HTTP Bridge

This package runs the local AANA HTTP bridge in a container with the adapter
gallery and internal pilot profiles bundled into the image.

## One-Command Start

```powershell
docker compose up --build
```

The bridge listens on `http://localhost:8765` by default.

The web playground is served by the same bridge:

```text
http://localhost:8765/playground
```

The curated local desktop/browser demos are also served by the bridge:

```text
http://localhost:8765/demos
```

The published searchable adapter gallery is served by the same bridge:

```text
http://localhost:8765/adapter-gallery
```

Use the gallery as the recommended first trial surface: choose an adapter,
click **Try this adapter**, then run the preloaded example in the playground.
Deep links also work directly, for example:

```text
http://localhost:8765/playground?adapter=deployment_readiness
```

The first productized family pages are also served by the bridge:

```text
http://localhost:8765/enterprise
http://localhost:8765/personal-productivity
http://localhost:8765/government-civic
```

Each page defines the family boundary, adapters, risk tiers, required evidence,
expected outcomes, a browser try link, and the one-command starter pilot kit.

Default local demo settings are defined in `docker-compose.yml`. Copy
`examples/aana_bridge.env.example` to `.env` or export individual variables to
override them.

```powershell
Copy-Item examples/aana_bridge.env.example .env
```

The default local token is `aana-local-dev-token`. Replace it before any real
pilot.

For observe-only pilot runs, add `--shadow-mode` to the bridge command or call
POST routes with `?shadow_mode=true`. Shadow records stay redacted and
`audit-metrics` reports would-pass, would-revise, would-defer, and would-refuse
counts. See `docs/shadow-mode.md`.

## Bundled Profiles

The Docker runtime uses these repo-local pilot assets:

- Adapter gallery: `examples/adapter_gallery.json`
- Deployment profile: `examples/production_deployment_internal_pilot.json`
- Governance policy: `examples/human_governance_policy_internal_pilot.json`
- Evidence registry: `examples/evidence_registry.json`
- Observability policy: `examples/observability_policy_internal_pilot.json`
- Audit log: `eval_outputs/audit/docker/aana-bridge.jsonl`

The audit log path is mounted through `./eval_outputs:/app/eval_outputs`, so
redacted audit records survive container restarts.

## Endpoint Checks

Readiness does not require POST authorization:

```powershell
Invoke-RestMethod http://localhost:8765/ready
```

Open the local pilot reviewer dashboard after checks have written redacted audit records:

```text
http://localhost:8765/dashboard
```

The dashboard reads `GET /dashboard/metrics` and shows gate/action counts, violation trends, AIx score range, hard blockers, adapter breakdowns, and shadow-mode would-block rates.

Playground gallery metadata:

```powershell
Invoke-RestMethod http://localhost:8765/playground/gallery
```

Published adapter gallery metadata:

```powershell
Invoke-RestMethod http://localhost:8765/adapter-gallery/data.json
```

Local action demo metadata:

```powershell
Invoke-RestMethod http://localhost:8765/demos/scenarios
```

Agent event check:

```powershell
$headers = @{ Authorization = "Bearer aana-local-dev-token" }
$body = Get-Content examples/agent_event_support_reply.json -Raw
Invoke-RestMethod http://localhost:8765/agent-check -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

Workflow check:

```powershell
$headers = @{ Authorization = "Bearer aana-local-dev-token" }
$body = Get-Content examples/workflow_research_summary_structured.json -Raw
Invoke-RestMethod http://localhost:8765/workflow-check -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

Workflow batch:

```powershell
$headers = @{ Authorization = "Bearer aana-local-dev-token" }
$body = Get-Content examples/workflow_batch_productive_work.json -Raw
Invoke-RestMethod http://localhost:8765/workflow-batch -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

## Release Checks For The Same Profiles

Run the matching local release gate outside the container:

```powershell
python scripts/aana_cli.py release-check --deployment-manifest examples/production_deployment_internal_pilot.json --governance-policy examples/human_governance_policy_internal_pilot.json --evidence-registry examples/evidence_registry.json --observability-policy examples/observability_policy_internal_pilot.json --audit-log eval_outputs/audit/docker/aana-bridge.jsonl
```

Use `python scripts/aana_cli.py pilot-certify` to confirm the CLI, Python API,
HTTP bridge, contracts, skills/plugins, evidence stubs, and contract freeze
surfaces are locally pilot-ready.
