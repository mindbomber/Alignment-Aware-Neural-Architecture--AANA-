# AANA Durable Audit Storage

AANA now has a durable local append-only storage option for normal runtime audit records.

This is production-candidate infrastructure, not production certification. External production still needs customer-approved immutable storage, access control, backup/replication, retention enforcement, and legal-hold operations.

## Config

```text
examples/durable_audit_storage.json
```

The config requires:

- redacted records only
- raw payload storage disabled
- append-only writes
- tamper-evident manifest
- minimum 365-day retention expectation
- remote immutable backend before go-live

## CLI

Write the default config:

```bash
python scripts/aana_cli.py durable-audit-storage --write-config
```

Import an existing redacted audit log:

```bash
python scripts/aana_cli.py durable-audit-storage --source-audit-log eval_outputs/aix_audit/enterprise_ops_pilot/audit.jsonl
```

Verify durable storage:

```bash
python scripts/aana_cli.py durable-audit-storage --verify
```

## FastAPI

Route:

```text
POST /durable-audit-storage
```

Example:

```json
{
  "source_audit_log": "eval_outputs/aix_audit/enterprise_ops_pilot/audit.jsonl",
  "audit_path": "eval_outputs/durable_audit_storage/aana_audit.jsonl",
  "manifest_path": "eval_outputs/durable_audit_storage/aana_audit.jsonl.sha256.json"
}
```

## Behavior

Before appending, AANA verifies the current durable audit log against its manifest. If the log was modified, the next append fails.

After appending, AANA writes a manifest with:

- audit log SHA-256
- byte size
- record count
- previous audit prefix hash
- previous manifest hash
- summary metrics
- manifest self-hash

Verification checks the current log, manifest self-hash, schema/redaction validation, and append-only prefix preservation.
