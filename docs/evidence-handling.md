# Evidence Handling Hardening

AANA evidence refs must be audit-safe. They should identify evidence without leaking raw secrets, PII, or full private records.

## Evidence Ref Integrity

Tool-call evidence refs support these integrity fields:

- `source_id`: stable redacted evidence identifier.
- `trust_tier`: `verified`, `runtime`, `user_claimed`, `unverified`, or `unknown`.
- `redaction_status`: `public`, `redacted`, `sensitive`, or `unknown`.
- `retrieved_at`: optional ISO timestamp for freshness checks.
- `citation_url` or `retrieval_url`: optional provenance link or URI.
- `provenance`: optional redacted source label.
- `supports`: optional claim/action ids this evidence supports.
- `contradicts`: optional claim/action ids this evidence contradicts.

## Fail-Closed Cases

AANA fails closed when evidence refs contain:

- raw API keys, tokens, passwords, or secret-like strings;
- raw PII without redaction;
- `sensitive` or unredacted evidence status;
- stale or invalid freshness timestamps;
- malformed evidence refs or missing source ids;
- contradictory evidence for the proposed action.

Missing evidence and contradictory evidence are tracked separately. Missing evidence normally routes to `ask` or `defer`; contradictory evidence routes to `defer` or stronger review.

## Grounded QA Coverage

Grounded QA checks should track citation coverage separately from general evidence presence. AANA exposes `grounded_qa_evidence_coverage(answer, evidence_items)` for lightweight citation/source coverage reports.
