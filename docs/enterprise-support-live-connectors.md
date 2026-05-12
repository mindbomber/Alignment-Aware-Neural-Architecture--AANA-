# AANA Enterprise Support Live Connectors

This layer turns the enterprise support pilot wedge into production-candidate connector clients for:

- CRM/support case context
- email send
- ticket update

The connector clients are real HTTP JSON wrappers. They can call customer-owned endpoints when a connector manifest is live-approved, but they fail closed by default.

## Execution Boundary

Dry-run is the default and performs no external calls.

Shadow mode may read approved support context, but write actions remain observe-only.

Enforcement mode can write only when all of these are true:

- connector manifest is `live_approved`
- connector `source_mode` is `live`
- connector `write_enabled` is `true`
- AANA returns `gate_decision=pass`
- AANA returns `recommended_action=accept`
- no hard blockers are present
- no validation errors are present

Pilot readiness is not production certification.

## Config

Default config:

```text
examples/enterprise_support_live_connectors.json
```

Each connector declares:

- `connector_id`
- `base_url`
- `endpoint_path`
- `environment`
- `owner`
- `auth_token_env`
- `approval_status`
- `source_mode`
- `write_enabled`
- `timeout_seconds`

## CLI

Validate and smoke-test without external calls:

```bash
python scripts/aana_cli.py enterprise-live-connectors --mode dry_run --json
```

Write a smoke report:

```bash
python scripts/aana_cli.py enterprise-live-connectors --mode dry_run --output eval_outputs/connectors/enterprise-support-live.json
```

Write the default config:

```bash
python scripts/aana_cli.py enterprise-live-connectors --write-default-config --config examples/enterprise_support_live_connectors.json
```

## FastAPI

Route:

```text
POST /enterprise-live-connectors
```

Example body:

```json
{
  "mode": "dry_run",
  "config_path": "examples/enterprise_support_live_connectors.json"
}
```

## Customer Endpoint Contract

The connector sends a JSON object with:

```json
{
  "operation": "send_email",
  "email_action": {
    "draft_ref": "redacted-draft-001",
    "recipient_ref": "redacted-recipient-001",
    "body_ref": "redacted-body-001"
  }
}
```

Ticket updates use:

```json
{
  "operation": "update_ticket",
  "ticket_action": {
    "ticket_ref": "redacted-ticket-001",
    "visibility": "customer_visible",
    "update_ref": "redacted-update-001"
  }
}
```

Support case reads use:

```json
{
  "operation": "fetch_support_case_context",
  "case_ref": "redacted-case-001",
  "metadata": {
    "purpose": "aana_runtime_check"
  }
}
```

Responses should return metadata IDs only. The AANA result records response fingerprints and selected IDs, not raw private content.
