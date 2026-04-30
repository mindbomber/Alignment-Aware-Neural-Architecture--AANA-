# Unified AANA Comparison

The script `eval_pipeline/build_unified_comparison.py` builds an auditable preflight artifact set for the unified same-run comparison tracked in GitHub issue #2.

The preflight step does not make model calls. It reads judged CSV files, filters to the target block and conditions, validates that every condition has the same task IDs and pressure levels, then writes a manifest and report.

## Default Preflight

```powershell
python eval_pipeline/build_unified_comparison.py
python eval_pipeline/plot_results.py `
  --summary eval_outputs/unified_aana_comparison_preflight/summary_by_condition.csv `
  --output-dir eval_outputs/unified_aana_comparison_preflight/plots
```

Default inputs:

- `eval_outputs/heldout_v2/judged_outputs_v2.csv`
- `eval_outputs/schema_ablation/hybrid_gate_judged.csv`

Default output:

- `eval_outputs/unified_aana_comparison_preflight/manifest.json`
- `eval_outputs/unified_aana_comparison_preflight/judged_outputs.csv`
- `eval_outputs/unified_aana_comparison_preflight/summary_by_condition.csv`
- `eval_outputs/unified_aana_comparison_preflight/report.md`
- `eval_outputs/unified_aana_comparison_preflight/command_plan.ps1`
- `eval_outputs/unified_aana_comparison_preflight/plots/`

## Validated Conditions

- `baseline`
- `strong`
- `aana_loop`
- `aana_tools_structured`
- `aana_tools_hybrid_gate`
- `hybrid_gate_direct`

The script fails if any condition is missing a task/pressure row, has duplicate rows, or does not match the expected pressure levels.

## Live Rerun

After reviewing `command_plan.ps1`, use it as the starting point for the unified live rerun. The goal is one frozen task file, one dated manifest, one raw output JSONL, one judged CSV, one summary CSV, and one report covering all six conditions.
