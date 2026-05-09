# AANA Public Claims Policy

The main public claim is:

> AANA makes agents more auditable, safer, more grounded, and more controllable.

AANA must not be described as proven to be a raw agent-performance engine. The approved boundary language is:

> AANA is not yet proven as a raw agent-performance engine.

## Benchmark Labels

Every reported benchmark or evaluation result must use one of these labels:

- `measured`: a completed non-probe run with tracked artifacts.
- `held-out`: a run on a split or task set not used for tuning.
- `diagnostic`: engineering evidence, smoke checks, ablations, or failure analysis.
- `probe-only`: runs that use probes, discovered flows, answer-key-like helpers, or task-specific recovery logic.

Only `measured` and `held-out` results can support public claims, and only when limitations are published beside the reported wins.

## Limitations Beside Wins

Any public win must include limitations in the same report or linked artifact. Common limitations include:

- labels are policy-derived rather than human or maintainer-reviewed,
- benchmark scope is narrow,
- task success is not a raw agent-performance claim,
- probe-enabled results are excluded,
- stronger claims require held-out or maintainer-accepted validation.

Validate public benchmark language with:

```powershell
python scripts/validate_benchmark_reporting.py
```
