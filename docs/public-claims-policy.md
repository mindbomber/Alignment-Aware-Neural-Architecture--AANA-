# AANA Public Claims Policy

The main public claim is:

> AANA makes agents more auditable, safer, more grounded, and more controllable.

AANA must not be described as proven to be a raw agent-performance engine or as having raw agent-performance superiority. The approved boundary language is:

> AANA is not yet proven as a raw agent-performance engine.

## Benchmark Labels

Every reported benchmark or evaluation result must use one of these labels:

- `calibration`: tuning, threshold selection, route calibration, or adapter development evidence.
- `heldout`: a run on a split or task set not used for tuning.
- `diagnostic`: engineering evidence, smoke checks, ablations, or failure analysis.
- `probe`: runs that use probes, discovered flows, answer-key-like helpers, or task-specific recovery logic.
- `external_reporting`: a public-facing result artifact prepared from an external, held-out, or maintainer-accepted protocol.

Only `heldout` and `external_reporting` results can support public claims, and only when limitations are published beside the reported wins.

## Limitations Beside Wins

Any public win must include limitations in the same report or linked artifact. Common limitations include:

- labels are policy-derived rather than human or maintainer-reviewed,
- benchmark scope is narrow,
- task success is not a raw agent-performance claim,
- probe-enabled results are excluded,
- stronger claims require held-out or maintainer-accepted validation.

Validate public benchmark language with:

```powershell
python scripts/validation/validate_public_claims_policy.py
python scripts/validate_aana_platform.py
```
