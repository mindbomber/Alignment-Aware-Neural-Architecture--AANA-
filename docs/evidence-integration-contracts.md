# Evidence Integration Contracts

AANA evidence integrations are connector contracts, not live connectors. They define what production systems must return before adapter decisions can rely on CRM/support, ticketing, email, calendar, IAM, CI/GitHub, deployment, billing, data-export, file-system, or similar records.

Run the local contract check with:

```powershell
python scripts/aana_cli.py evidence-integrations --evidence-registry examples/evidence_registry.json --mock-fixtures examples/evidence_mock_connector_fixtures.json
python scripts/aana_cli.py evidence-integrations --evidence-registry examples/evidence_registry.json --mock-fixtures examples/evidence_mock_connector_fixtures.json --json
```

## Connector Contract

Each `EvidenceIntegrationStub` declares a stable connector contract:

- `integration_id`: stable connector family ID, such as `crm_support` or `deployment`.
- `required_source_ids`: evidence sources that must be present for the covered adapter family.
- `optional_source_ids`: extra sources a connector may return when relevant.
- `required_auth_scopes`: read-only scopes the connector must hold before retrieval.
- `auth_boundary`: the operational line between evidence retrieval and irreversible action execution.
- `freshness_slo_hours`: maximum allowed record age for connector output.
- `allowed_trust_tiers`: trust tiers accepted from that integration.
- `allowed_redaction_statuses`: redaction states accepted by default.
- `failure_modes`: routable failure codes such as `unauthorized`, `missing_source`, `stale_evidence`, `unredacted_evidence`, `invalid_shape`, and `connector_unavailable`.
- `contract`: machine-readable auth, source-scope, freshness, redaction, trust, failure-routing, and output-shape requirements.

The hardened core connector families are:

- `crm_support`: CRM records, support policy, and order-system facts.
- `ticketing`: ticket history, sprint status, support policy, and incident context summaries.
- `email_send`: draft email, recipient metadata, and user approval.
- `calendar`: free/busy, attendee list, and user instruction.
- `iam`: IAM request, role catalog, and approval record.
- `ci`: CI/GitHub diff, test output, and status evidence.
- `deployment`: deployment manifest, CI result, and release notes.
- `billing`: invoice, billing policy, and payment metadata.
- `data_export`: data classification, access grants, and export request.
- `workspace_files`: file metadata, requested action, diff preview, backup status, and user confirmation.

The connector must return normalized evidence objects:

```json
{
  "source_id": "deployment-manifest",
  "retrieved_at": "2026-05-05T00:00:00Z",
  "trust_tier": "verified",
  "redaction_status": "redacted",
  "text": "Deployment manifest summary: rollback plan and health checks are declared.",
  "metadata": {
    "connector_contract_version": "0.1",
    "integration_id": "deployment",
    "system_type": "deployment",
    "normalized": true,
    "freshness_slo_hours": 24,
    "raw_record_id": "deployment-manifest-001"
  }
}
```

Production connectors should keep raw records in the source system or approved raw-artifact store. AANA workflow checks should receive bounded summaries with source ID, freshness, trust tier, redaction status, and enough text for the verifier stack to check the candidate action.

## Connector Request Contract

Python integrations can use the typed request/auth helpers instead of hand-assembling connector calls:

```python
import aana

auth = aana.EvidenceAuthContext(
    scopes=("filesystem.metadata.read", "filesystem.diff_preview.read", "approval.read"),
    tenant_id="tenant-001",
    principal_id="user-001",
    request_id="req-001",
)

request = aana.EvidenceFetchRequest(
    integration_id="workspace_files",
    source_ids=("file-metadata", "diff-preview", "backup-status"),
    operation="read_diff_preview",
    auth=auth,
    adapter_id="file_operation_guardrail",
    subject_ref="workspace://project/path",
)
```

Production connector implementations must fail closed when:

- auth scopes are missing or not tenant/principal scoped;
- a requested source ID is not declared by the connector contract;
- evidence is older than `freshness_slo_hours`;
- evidence is not redacted to an allowed redaction status;
- the output shape omits required fields;
- the upstream source is unavailable.

`MockEvidenceConnector` enforces the same contract against synthetic fixtures. It is a local contract harness, not a production retrieval implementation.

## Mock Fixtures

`examples/evidence_mock_connector_fixtures.json` is the local fixture bundle for the core production systems:

- CRM/support
- ticketing and incident status
- email send
- calendar scheduling
- IAM/access
- CI/code review
- deployment/release
- billing/payment
- data export
- file system

The fixture bundle is intentionally synthetic and redacted. Its job is to prove that connector outputs can be normalized and accepted by `validate_workflow_evidence(..., require_structured=True)`.

## Failure Routing

Connector failures must not silently degrade into ungrounded acceptance.

- `unauthorized`: route to `defer`, `ask`, or an approved retrieval setup path.
- `missing_source`: route to `retrieve`, `ask`, or `defer`.
- `stale_evidence`: refresh evidence or defer.
- `unredacted_evidence`: redact before checking, or defer to a privacy-reviewed path.
- `invalid_shape`: fix the connector output before running the gate.
- `connector_unavailable`: route to `defer` unless the adapter explicitly allows a lower-confidence fallback.

Adapters still decide final routing through their gate and AIx configuration. The connector contract only guarantees the evidence entering that gate is source-scoped, fresh, redacted, and normalized.
