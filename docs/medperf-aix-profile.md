# MedPerf Healthcare AIx Profile

`medperf-aix-profile` adds a strict healthcare audit profile for the MLCommons
MedPerf surface. It is designed for regulated medical AI evaluation workflows,
not production certification or clinical deployment approval.

## What It Checks

The profile requires healthcare-specific evaluation context:

- site
- dataset
- model
- clinical task
- evaluation owner
- privacy controls
- clinical owner signoff
- site approval
- IRB/ethics marker when applicable

The risk tier is fixed to `strict`. AIx tuning uses higher beta and strict
thresholds because medical claims, privacy failures, and site governance gaps
carry high impact.

## Hard Blockers

The validator blocks healthcare evaluation readiness when it finds:

- `missing_site_approval`
- `missing_privacy_boundary`
- `unsupported_medical_claim`
- `missing_clinical_owner_signoff`

Hard blockers prevent direct readiness even if numeric AIx tuning is otherwise
strong.

## CLI

Validate the default profile:

```powershell
python scripts/aana_cli.py medperf-aix-profile --json
```

Write the default profile:

```powershell
python scripts/aana_cli.py medperf-aix-profile `
  --write-default `
  --profile examples/medperf_aix_profile_healthcare.json `
  --json
```

Generate the healthcare-specific AIx Report section:

```powershell
python scripts/aana_cli.py medperf-aix-profile `
  --profile examples/medperf_aix_profile_healthcare.json `
  --report eval_outputs/medperf/medperf-aix-healthcare-section.json `
  --json
```

## Report Section

The generated section includes:

- MedPerf surface and strict risk tier
- site approval summary
- dataset provenance and PHI boundary
- model identity and version
- clinical task, intended use, and unsupported uses
- evaluation owner
- privacy controls
- IRB/ethics marker
- clinical owner signoff
- AIx tuning
- hard blockers and validation issues
- limitations and claim boundary

The section is meant to be embedded in an AIx Report. It deliberately states
that healthcare pilot readiness is not production certification, clinical
deployment approval, medical device clearance, or clinical advice.
