# AANA Production-Candidate Profile

The production-candidate profile is the configuration boundary between the enterprise pilot and a controlled production-candidate deployment.

It does not certify production launch. It collects the artifacts that must be in place before a customer can run AANA against live support/email/ticket workflows.

## Default Profile

```text
examples/production_candidate_profile_enterprise_support.json
```

The first profile covers:

```text
customer support + email send + ticket update
```

## What It Requires

- fail-closed runtime execution
- shadow mode as the default mode
- no writes in shadow mode
- direct execution only on `pass` + `accept` with no blockers
- enterprise connector readiness plan
- production-candidate live connector config
- deployment manifest
- governance policy
- observability policy
- audit retention policy
- incident response plan
- enterprise AIx audit kit

## CLI

Validate the checked-in profile:

```bash
python scripts/aana_cli.py production-candidate-profile
```

Write the default profile:

```bash
python scripts/aana_cli.py production-candidate-profile --write-default --profile examples/production_candidate_profile_enterprise_support.json
```

JSON output:

```bash
python scripts/aana_cli.py production-candidate-profile --json
```

## FastAPI

Route:

```text
POST /production-candidate-profile
```

Example body:

```json
{
  "profile_path": "examples/production_candidate_profile_enterprise_support.json"
}
```

## Readiness Meaning

`production_candidate_ready=true` means the local production-candidate configuration is coherent and linked to the required governance artifacts.

`go_live_ready=true` is stricter. The default checked-in profile is not go-live ready because live connector approvals and write enablement are intentionally disabled.

Go-live still requires customer-specific approval, immutable audit storage, staffed human review, security review, incident response rehearsal, and measured shadow-mode results.
