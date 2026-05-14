# AANA Enterprise Ops Pilot Guide

This guide is the first buyer-facing path for `AANA AIx Audit`. It uses synthetic enterprise data to generate the same runtime artifacts a shadow pilot uses: Workflow Contract batch input, redacted audit JSONL, metrics, enterprise dashboard JSON, AIx drift report, audit integrity manifest, reviewer report, and AIx Report.

AANA AIx Audit is pilot evidence, not production certification. Production use still requires live connectors, domain-owner signoff, immutable audit retention, observability, human review operations, security review, incident response, and measured pilot results.

For the concise buyer-facing packet, see [`aana-aix-audit-enterprise-ops-pilot-packet.md`](aana-aix-audit-enterprise-ops-pilot-packet.md).

For customer onboarding templates, see [`aana-aix-audit-customer-onboarding-templates.md`](aana-aix-audit-customer-onboarding-templates.md).

For connector setup requirements, see [`enterprise-connector-readiness.md`](enterprise-connector-readiness.md).

For the polished customer-support wedge demo, see [`enterprise-support-demo-flow.md`](enterprise-support-demo-flow.md).

## Run The Synthetic Pilot

```powershell
python scripts/aana_cli.py aix-audit
```

The command writes artifacts under:

```text
eval_outputs/aix_audit/enterprise_ops_pilot/
```

Key outputs:

- `enterprise-workflow-batch.json` - materialized Workflow Contract batch.
- `audit.jsonl` - redacted per-workflow audit records.
- `metrics.json` - dashboard-ready aggregate metrics.
- `enterprise-dashboard.json` - local enterprise pilot dashboard payload from redacted audit metrics.
- `enterprise-connector-readiness.json` - concrete connector setup and go-live readiness plan.
- `aix-drift.json` - AIx drift and hard-blocker review.
- `audit-integrity.json` - SHA-256 audit integrity manifest.
- `reviewer-report.md` - operational audit handoff.
- `aix-report.json` and `aix-report.md` - buyer-facing AIx Report.

## Pilot Surfaces

The v1 enterprise-ops package covers three surfaces:

- Support/customer communications: support replies, CRM support replies, email send, and ticket updates.
- Data/access controls: data export and access permission changes.
- DevOps/release controls: code review, deployment readiness, and incident response updates.

The normalized adapter declaration lives in:

```text
examples/starter_pilot_kits/enterprise/adapter_config.json
```

Each adapter declares risk tier, AIx beta, layer weights, thresholds, evidence requirements, human-review triggers, fixture coverage, and known caveats.

Calibration fixture coverage lives in:

```text
examples/starter_pilot_kits/enterprise/calibration_fixtures.json
```

The fixture set covers clean accept, revise, ask, defer, refuse, missing evidence, hard blockers, privacy leakage, unsupported claims, and irreversible-action routing. These fixtures calibrate pilot release parameters; they are not theoretical proof.

## Shadow Mode Path

Use the synthetic report to confirm routing and audit shape before connecting real systems. For real pilots, run the installed FastAPI service first, then send shadow-mode checks with `?shadow_mode=true` or an SDK client configured for shadow mode:

```powershell
$env:AANA_BRIDGE_TOKEN = "replace-with-a-secret"
aana-fastapi --host 127.0.0.1 --port 8766 --audit-log eval_outputs/audit/enterprise-shadow.jsonl
```

For containerized pilots, use the Docker runtime in [`docker-http-bridge.md`](docker-http-bridge.md); Docker intentionally uses host port `8765` while the installed local service examples use `8766`.

Then connect approved evidence sources for CRM/support, ticketing, email, IAM, CI, deployment, and data export. Keep raw prompts, candidates, private records, outputs, and safe responses out of the redacted audit log.

## Decision Boundary

Use AIx as a governance signal:

- `pilot_ready`: synthetic or shadow evidence supports expanding the pilot.
- `pilot_ready_with_controls`: continue with human review, stronger evidence, or remediation.
- `not_pilot_ready`: do not expand until blockers are resolved.
- `insufficient_evidence`: gather more runtime evidence before making a pilot decision.

Do not describe any pilot report as production-certified.
