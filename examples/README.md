# Examples

These files show the input and output shapes without requiring live API calls.

- `sample_tasks.jsonl` contains two hand-written evaluation tasks.
- `sample_raw_outputs.jsonl` contains matching model-output-style rows that can be scored locally.

Try the scoring script:

```powershell
python eval_pipeline/score_outputs.py --input examples/sample_raw_outputs.jsonl --scored examples/sample_scored_outputs.csv --summary examples/sample_summary_by_condition.csv
```

The generated CSV files are useful for learning, but you do not need to commit them.
