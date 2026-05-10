# AANA Government/Civic Family

The government/civic family packages AANA adapters for synthetic public-service, procurement, grant, records, privacy, eligibility, policy, and public-communication workflows.

## Product Boundary

Use this family before civic workflows that could affect applicants, constituents, vendors, public records, policy interpretation, or public statements.

AANA must not make final legal, benefits, grant, procurement, or records-release determinations. It routes unsafe or under-evidenced candidates to revise, ask, defer, refuse, or human review.

## Core Pack

- Procurement/vendor risk
- Grant/application review
- Insurance/benefits eligibility triage
- Public-records/privacy redaction
- Policy memo grounding
- Public communication/publication check
- Casework response checker
- FOIA/public-records response checker

## Evidence Connectors

- Program rules and submitted documents
- Rubrics
- Vendor profiles
- Public law and policy sources
- Redaction/classification registry
- Case/ticket history
- Benefits and claim files
- Civic source registry

Connectors must return fresh, redacted, structured evidence with source IDs, jurisdiction/source-law metadata where relevant, and no raw private records in AANA payloads.

## Agent Skills

- Benefits eligibility boundary skill
- Procurement review skill
- Grant scoring consistency skill
- Policy memo grounding skill
- Public-records privacy skill
- Public statement risk skill

## Pilot Surface

The civic pilot surface is synthetic-only by default. It includes the `/government-civic` landing page, the adapter gallery, the web playground, the starter pilot kit, redacted audit exports, and metrics reports.

Run:

```powershell
python scripts/pilots/run_starter_pilot_kit.py --kit government_civic
python scripts/aana_cli.py civic-certify --json
```

## Certification Controls

Civic certification checks source-law traceability, jurisdiction labeling, privacy redaction, human-review routing, redacted audit exports, public-records retention/audit policy, connector contracts, starter workflows, and skill conformance.
