# AANA Platform Layer

Phase 5 makes the three product families visible across the public surfaces.

## Families

- Enterprise: support, developer, deployment, data, access, billing, and incident guardrails.
- Personal Productivity: local irreversible-action checks before sending, scheduling, deleting, buying, publishing, summarizing, or citing.
- Government/Civic: synthetic public-service, procurement, grants, records, privacy, eligibility, and policy workflows.

## Platform Surfaces

- Family-aware gallery: `docs/adapter-gallery/` filters adapters by family, role, surface, risk tier, and readiness state.
- Family-aware metrics: audit dashboards now include `family_breakdown` and `role_breakdown` with usage, intervention, AIx, hard-blocker, human-review, and evidence-missing rates.
- Family-aware SDK: Python exports `EnterpriseAANAClient`, `PersonalAANAClient`, and `CivicAANAClient`; TypeScript mirrors those client classes.
- Connector marketplace: `python scripts/aana_cli.py connector-marketplace --json` lists connector source IDs, auth boundaries, freshness SLOs, redaction behavior, failure routing, and normalization requirements.
- Hosted synthetic demo: `docs/demo/` is a static, no-secret, no-live-action surface with Enterprise, Personal Productivity, and Government/Civic tabs.
- Production certification: `python scripts/aana_cli.py readiness-matrix --json` prints demo, pilot, production, and family-specific gates.

## Local Pilot Path

Run the Docker bridge and open the local surfaces:

```powershell
docker compose up
```

Then visit `http://127.0.0.1:8788/adapter-gallery`, `http://127.0.0.1:8788/playground`, and the dashboard/demo routes listed by `/ready`.
