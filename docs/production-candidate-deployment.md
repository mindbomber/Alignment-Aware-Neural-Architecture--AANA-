# AANA Production-Candidate Deployment

This runbook packages AANA as a production-candidate runtime governance service
for controlled enterprise operations pilots. It covers Docker, Compose,
Kubernetes, artifact paths, runtime checks, audit outputs, and the external
go-live gates that remain outside this repository.

Production-candidate does not mean production certification.

## Build The Image

```powershell
docker build -t aana/enterprise-ops-runtime:local .
```

The image installs the API extra, starts `aana-fastapi`, exposes port `8765`,
runs as UID `10001`, and writes redacted audit records under
`/app/eval_outputs`.

Port convention: local installed-service docs use `aana-fastapi` on
`127.0.0.1:8766`; Docker and deployment runbooks intentionally use host port
`8765`, mapped to container port `8765`, to keep containerized pilot traffic
separate from the local developer service. Override the host port with
`AANA_BRIDGE_PORT` in `.env` only when `8765` is already in use.

## Run With Compose

```powershell
Copy-Item examples/aana_bridge.env.example .env
docker compose up --build
```

Verify the service:

```powershell
Invoke-RestMethod http://localhost:8765/health
Invoke-RestMethod http://localhost:8765/ready
```

Swagger UI is available at:

```text
http://localhost:8765/docs
```

## Required Runtime Settings

- `AANA_BRIDGE_TOKEN`: bearer token for POST routes.
- `AANA_BRIDGE_TOKEN_SCOPES`: comma-separated route scopes.
- `AANA_AUDIT_LOG`: redacted JSONL audit path.
- `AANA_MAX_REQUEST_BYTES`: request-size guard.
- `AANA_RATE_LIMIT_PER_MINUTE`: in-process per-client rate limit.
- `AANA_PRODUCTION_CANDIDATE_PROFILE`: profile used by the candidate check.
- `AANA_LIVE_CONNECTOR_CONFIG`: connector readiness config.
- `AANA_LIVE_MONITORING_CONFIG`: live monitoring config.

Keep raw prompts, candidates, evidence text, customer records, and secrets out
of request payloads and audit output. Use redacted refs, source IDs,
fingerprints, and compact evidence metadata.

## Kubernetes

The example manifest is for local or internal testing:

```powershell
kubectl apply -f deploy/kubernetes/aana-bridge.yaml
```

The production-candidate template is the hardened starting point:

```powershell
kubectl apply -f deploy/kubernetes/aana-bridge-production-template.yaml
```

Before applying the production template, replace the registry image, token,
evidence registry, connector config, monitoring config, ingress host, TLS
secret, review route, and owner-specific policy URLs.

Rollback:

```powershell
kubectl rollout undo deployment/aana-bridge -n aana-runtime
```

## Production-Candidate Check

Run locally:

```powershell
python scripts/aana_cli.py production-candidate-check --profile examples/production_candidate_profile_enterprise_support.json
```

Run through the deployed service:

```powershell
$headers = @{ Authorization = "Bearer aana-local-dev-token" }
$body = @{ profile_path = "examples/production_candidate_profile_enterprise_support.json" } | ConvertTo-Json
Invoke-RestMethod http://localhost:8765/production-candidate-check -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

The check should produce or reference:

- production-candidate profile validation
- live connector readiness
- durable audit storage manifest
- human-review queue/export path
- live monitoring metrics
- shadow-mode pilot evidence
- production-candidate AIx report

## Artifact Layout

Recommended local output paths:

- Runtime audit log: `eval_outputs/audit/docker/aana-fastapi.jsonl`
- AIx audit outputs: `eval_outputs/aix_audit/enterprise_ops_pilot/`
- Durable audit storage:
  `eval_outputs/durable_audit_storage/aana_audit.jsonl`
- Human-review export:
  `eval_outputs/human_review/enterprise_support_queue.jsonl`
- Live monitoring metrics:
  `eval_outputs/monitoring/docker/live-monitoring.json`
- Production-candidate AIx report:
  `eval_outputs/production_candidate/production-candidate-aix-report.json`

## Go-Live Gates Outside The Repo

These items are not proven by Docker, local pytest, or
`production-candidate-check`:

- live connector authorization and least-privilege access
- immutable audit retention in the customer environment
- domain-owner signoff
- security review and threat model
- staffed human-review operations
- deployed observability and alert routing
- incident response drill
- measured shadow-mode results on realistic records
- rollback approval and operator runbook

Treat these as customer-environment gates. AANA can supply templates,
validators, and reports; the deployment owner must approve the real system.
