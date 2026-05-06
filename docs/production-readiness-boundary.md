# Production Readiness Boundary

This repository can be demo-ready, pilot-ready, or production-candidate. It is not production-certified by local tests alone.

Production readiness requires:

- live evidence connectors
- domain owner signoff
- audit retention
- observability
- human review path
- security review
- deployment manifest
- incident response plan
- measured pilot results

Local tests can prove contract compatibility, fixture behavior, golden output stability, metadata-only audit shape, and release-gate wiring. They cannot prove live connector permissions, domain owner approval, retained audit evidence in a deployment, deployed observability, human review staffing, security approval, incident response readiness, or measured pilot performance on live traffic.

The executable boundary artifact is `examples/production_readiness_boundary.json`.

```powershell
python scripts/validate_production_readiness_boundary.py
```
