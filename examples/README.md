# Examples

These files show the input and output shapes without requiring live API calls.

- `sample_tasks.jsonl` contains two hand-written evaluation tasks.
- `sample_raw_outputs.jsonl` contains matching model-output-style rows that can be scored locally.
- `application_scenarios.jsonl` contains six everyday AANA scenario prompts: budgeted travel, allergy-safe meal planning, grounded research, privacy abstention, workflow readiness, and math/feasibility.

Try the scoring script:

```powershell
python eval_pipeline/score_outputs.py --input examples/sample_raw_outputs.jsonl --scored examples/sample_scored_outputs.csv --summary examples/sample_summary_by_condition.csv
```

The generated CSV files are useful for learning, but you do not need to commit them.

The application scenarios are starter prompts, not benchmark evidence. Use them to design domain-specific AANA experiments where each scenario names:

- The constraint to preserve.
- The verifier signal that would detect a violation.
- The correction action: revise, retrieve, ask, refuse, defer, or accept.
