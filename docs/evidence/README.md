# Evidence Snapshots

This folder contains reviewed evidence snapshots that are intentionally tracked
in Git. Local experiment outputs still belong in `eval_outputs/`, which remains
gitignored.

Files:

- `artifact_manifest.json` - Canonical reviewed-artifact policy. Each covered artifact declares its path or scoped glob, result label, source split, public-claim eligibility, and reproduction command.
- `constraint_reasoning_aana_summary.csv` - Aggregate condition-level metrics, confidence intervals, deltas, and McNemar p-values.
- `constraint_reasoning_aana_paired_tests.csv` - Paired pass/non-pass discordance counts against baseline.
- `constraint_reasoning_aana_pressure_breakdown.csv` - High-pressure and low-pressure splits by condition.
- `manifest.json` - Release tag, commit SHA, source file hashes, methods, caveats, and primary result.
- `plots/` - SVG visualizations generated from the plot-compatible summary.
- `peer_review/` - JSON/JSONL/Markdown evidence snapshots used by AANA
  peer-review, Hugging Face proof, production-candidate, and pilot reports.

These snapshots are intentionally separate from `eval_outputs/`, which is
gitignored because local experiment outputs can be large and may contain raw
model generations. Regenerate the constraint-reasoning snapshots with:

```powershell
python eval_pipeline/compare_constraint_reasoning.py
python eval_pipeline/plot_results.py `
  --summary eval_outputs/constraint_reasoning_aana_evidence/plot_summary_by_condition.csv `
  --output-dir eval_outputs/constraint_reasoning_aana_evidence/plots
```

Before committing, run:

```powershell
python scripts/validation/validate_no_tracked_eval_outputs.py
python scripts/validation/validate_evidence_artifacts.py
```
