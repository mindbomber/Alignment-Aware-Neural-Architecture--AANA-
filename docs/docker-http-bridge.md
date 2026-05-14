# Dockerized AANA Runtime

This package runs the AANA production-candidate FastAPI runtime in a container.
It is the recommended Docker entry point for runtime checks, AIx audit routes,
connector readiness, human-review export, live monitoring, and
production-candidate checks.

The legacy `scripts/aana_server.py` HTTP bridge still exists for the local web
playground and static demo pages. Use this Docker package for API/runtime
integration work.

## One-Command Start

```powershell
docker compose up --build
```

The runtime listens on `http://localhost:8765` by default.

Port convention: the installed local service examples use `aana-fastapi` on
`127.0.0.1:8766`. Docker and deployment examples intentionally use host port
`8765`, mapped to container port `8765`, so containerized pilot commands stay
separate from the local developer service. Override the host port with
`AANA_BRIDGE_PORT` in `.env` only when `8765` is already in use.

Readiness does not require POST authorization:

```powershell
Invoke-RestMethod http://localhost:8765/ready
```

Interactive OpenAPI docs:

```text
http://localhost:8765/docs
```

Default local demo settings are defined in `docker-compose.yml`. Copy
`examples/aana_bridge.env.example` to `.env` or export individual variables to
override them.

```powershell
Copy-Item examples/aana_bridge.env.example .env
```

The default local token is `aana-local-dev-token`. Replace it before any real
pilot.

## Bundled Profiles

The Docker runtime uses these repo-local pilot assets:

- Adapter gallery: `examples/adapter_gallery.json`
- Evidence registry: `examples/evidence_registry.json`
- Production-candidate profile:
  `examples/production_candidate_profile_enterprise_support.json`
- Live connector config: `examples/enterprise_support_live_connectors.json`
- Live monitoring config: `examples/live_monitoring_metrics.json`
- Audit log: `eval_outputs/audit/docker/aana-fastapi.jsonl`

The audit log path is mounted through `./eval_outputs:/app/eval_outputs`, so
redacted audit records survive container restarts.

## Deployment Package

The deployable runtime package includes:

- `Dockerfile`: builds the FastAPI image, installs `.[api]`, starts
  `aana-fastapi`, runs as UID `10001`, and uses `/ready` as the container
  healthcheck.
- `docker-compose.yml`: local container startup with token auth, scoped API
  access, audit logging, request-size limits, rate limits, and a `/ready`
  healthcheck.
- `examples/aana_bridge.env.example`: copyable environment config for compose
  and internal pilots.
- `deploy/kubernetes/aana-bridge.yaml`: example Kubernetes deployment with
  Secret, ConfigMap, PVC-backed audit path, `/health` liveness probe, `/ready`
  readiness probe, and Service.
- `deploy/kubernetes/aana-bridge-production-template.yaml`: production-candidate
  Kubernetes template with Secret, ConfigMap, PVC, Deployment, Service,
  HTTPS-only Ingress, probes, CPU/memory requests and limits, non-root runtime
  context, edge rate-limit annotations, and an explicit rollback command.

The container command is:

```text
aana-fastapi --host "$AANA_BRIDGE_HOST" --port "$AANA_BRIDGE_PORT" --gallery "$AANA_ADAPTER_GALLERY" --audit-log "$AANA_AUDIT_LOG" --rate-limit-per-minute "$AANA_RATE_LIMIT_PER_MINUTE" --max-request-bytes "$AANA_MAX_REQUEST_BYTES"
```

## Auth And Scopes

POST routes use token auth when `AANA_BRIDGE_TOKEN` is configured. Send:

```http
Authorization: Bearer <token>
```

`AANA_BRIDGE_TOKEN_SCOPES` controls which product routes are enabled for that
token. The compose profile enables:

```text
pre_tool_check,agent_check,workflow_check,workflow_batch,validation,aix_audit,durable_audit_storage,human_review_export,live_monitoring,enterprise_connectors,enterprise_live_connectors,enterprise_demo,mlcommons_aix_report,production_candidate_profile,production_candidate_check
```

For narrower deployments, reduce scopes to the routes the caller needs.

## Runtime Checks

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

## Production-Candidate Routes

Generate an MLCommons-backed AIx Report:

```powershell
$headers = @{ Authorization = "Bearer aana-local-dev-token" }
$body = @{ results_path = "examples/mlcommons_ailuminate_results.json"; source_type = "ailuminate"; profile_path = "examples/mlcommons_aix_profile.json"; output_dir = "eval_outputs/mlcommons_aix/docker" } | ConvertTo-Json
Invoke-RestMethod http://localhost:8765/mlcommons-aix-report -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

Run the production-candidate profile check through the container:

```powershell
$headers = @{ Authorization = "Bearer aana-local-dev-token" }
$body = @{ profile_path = "examples/production_candidate_profile_enterprise_support.json" } | ConvertTo-Json
Invoke-RestMethod http://localhost:8765/production-candidate-check -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

Run the live connector smoke in dry-run mode:

```powershell
$headers = @{ Authorization = "Bearer aana-local-dev-token" }
$body = @{ mode = "dry_run"; config_path = "examples/enterprise_support_live_connectors.json" } | ConvertTo-Json
Invoke-RestMethod http://localhost:8765/enterprise-live-connectors -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

Generate live monitoring metrics from redacted audit records:

```powershell
$headers = @{ Authorization = "Bearer aana-local-dev-token" }
$body = @{ audit_log = "eval_outputs/audit/docker/aana-fastapi.jsonl"; output_path = "eval_outputs/monitoring/docker/live-monitoring.json" } | ConvertTo-Json
Invoke-RestMethod http://localhost:8765/live-monitoring -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

## Release Checks For The Same Profiles

Run the matching local release gate outside the container:

```powershell
python scripts/aana_cli.py production-candidate-check --profile examples/production_candidate_profile_enterprise_support.json
```

Use `python scripts/aana_cli.py pilot-certify` to confirm the CLI, Python API,
FastAPI service, contracts, connector stubs, enterprise pilot artifacts, and
contract freeze surfaces are locally pilot-ready.

## Production Deployment Assumptions

This Docker package is a production-candidate runtime package, not production
certification; it is not production certification. Before external production
use, a deployment still needs live connector authorization, domain-owner
signoff, approved audit retention, observability integration, staffed
human-review operations, security review, incident response, and measured
shadow-mode results.

The Kubernetes production template assumes TLS is terminated by the ingress
controller, HTTPS redirects are enforced, caller authentication is handled by
the AANA token or an upstream internal gateway, and tenant-aware edge limits are
enforced before traffic reaches the Python process. The runtime keeps its own
per-client rate limit as a second guard.

Rollback is an operational requirement. The production template declares:

```powershell
kubectl rollout undo deployment/aana-bridge -n aana-runtime
```

For support enforcement incidents, first switch affected adapters back to
shadow or advisory mode, then roll back the deployment, verify `/health` and
`/ready`, and rerun `production-candidate-check` before restoring enforcement.
