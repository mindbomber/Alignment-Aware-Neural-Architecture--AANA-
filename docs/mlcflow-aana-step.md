# MLCFlow AANA Automation Step

`mlcflow-aana-step` packages AANA as a workflow step for MLCommons automation.
It is designed to run after an MLCommons benchmark produces an artifact, then
turn that artifact into an AIx report and a machine-readable step manifest.

```text
run benchmark
  -> collect MLCommons artifact
  -> run AANA mlcommons-aix-report
  -> generate manifest with artifact hashes
  -> fail if hard blockers exist
```

This output is workflow evidence only. It is not MLCommons benchmark
certification, production certification, or go-live approval for regulated
industries.

## CLI

Run against a ModelBench journal artifact:

```powershell
python scripts/aana_cli.py mlcflow-aana-step `
  --results examples/mlcommons_modelbench_journal_actual.jsonl `
  --source-type modelbench `
  --output-dir eval_outputs/mlcflow_aana_step/modelbench `
  --json
```

Run an optional benchmark command first:

```powershell
python scripts/aana_cli.py mlcflow-aana-step `
  --benchmark-command "python path/to/benchmark.py --output out/results.json" `
  --results out/results.json `
  --source-type ailuminate `
  --output-dir eval_outputs/mlcflow_aana_step/ailuminate
```

## Manifest

The step writes:

```text
aana-mlcflow-step-manifest.json
```

The manifest includes:

- benchmark command result, when provided
- MLCommons input artifact path, SHA-256, and size
- normalized MLCommons artifact path, SHA-256, and size
- AIx report JSON path, SHA-256, and size
- AIx report Markdown path, SHA-256, and size
- deployment recommendation
- overall AIx
- hard blockers
- step status
- fail reasons

## Fail Policy

The step fails when:

- the optional benchmark command fails
- AANA cannot generate a valid MLCommons AIx report
- AIx hard blockers exist

If the report has `insufficient_evidence` but no hard blockers, the step returns
`warn`. That preserves workflow continuity while making the evidence gap visible.
