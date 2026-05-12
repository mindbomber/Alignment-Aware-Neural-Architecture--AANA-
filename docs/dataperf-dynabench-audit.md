# DataPerf / Dynabench Audit Wrappers

`dataperf-dynabench-audit` adds a lower-priority MLCommons audit wrapper for
dataset quality and benchmark coverage evidence. It is useful for readiness
reviews, but it is less directly tied to regulated deployment than MedPerf and
Croissant.

This output is dataset and benchmark-readiness evidence only. It is not
regulated deployment approval, production certification, or dataset legal
certification.

## What It Produces

The report includes:

- dataset quality audit profile
- benchmark coverage summary
- evidence gaps
- drift risk
- risk-tier recommendation

## Inputs

Use a Croissant-shaped metadata file when possible:

```text
examples/croissant_metadata_sample.json
```

Use a DataPerf/Dynabench benchmark summary:

```text
examples/dataperf_dynabench_benchmark_summary.json
```

The benchmark summary should include tasks, splits, metrics, baselines,
adversarial coverage, drift fields, and whether the benchmark is regulated or
rights-impacting.

## CLI

Run the audit:

```powershell
python scripts/aana_cli.py dataperf-dynabench-audit `
  --metadata examples/croissant_metadata_sample.json `
  --benchmark examples/dataperf_dynabench_benchmark_summary.json `
  --report eval_outputs/dataperf_dynabench/audit-report.json `
  --json
```

Write the default profile:

```powershell
python scripts/aana_cli.py dataperf-dynabench-audit `
  --write-default-profile `
  --profile examples/dataperf_dynabench_audit_profile.json `
  --json
```

## Risk Tiers

The wrapper recommends:

- `standard`: complete metadata, adequate benchmark coverage, low drift
- `elevated`: moderate drift, low adversarial coverage, missing baseline, or
  dynamic collection review needed
- `high`: sensitive data without privacy policy, large drift, missing license,
  missing provenance, or regulated/rights-impacting domain

High risk means domain-owner review is required before using the benchmark as
deployment evidence.
