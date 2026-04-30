# Table 2 Pilot Evidence

This folder contains tracked artifacts for the real-output Table 2 pilot.

Files:

- `pilot_tasks.jsonl` - The 40-prompt pilot task set.
- `table2_pilot_summary.csv` - The condition-level pilot table.
- `manual_spotcheck_sample.csv` - Twenty randomly sampled judged outputs for human review.
- `reviewer_spotcheck_audit.csv` - Filled reviewer spot-check decisions and notes for the 20 sampled rows.
- `manifest.json` - Commands, hashes, models, conditions, directional tests, and caveats.

The full raw and judged output files remain in local `eval_outputs/pilot_table2/` and are intentionally not tracked. Their hashes are recorded in `manifest.json`.

Reproduce locally:

```powershell
python eval_pipeline/generate_pilot_tasks.py
python eval_pipeline/run_pilot_conditions.py
python eval_pipeline/judge_pilot_outputs.py
python eval_pipeline/summarize_pilot_results.py
```
