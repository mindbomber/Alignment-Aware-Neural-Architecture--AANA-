# AANA Application Demo v0.1

This small demo tests whether the AANA correction pattern transfers from controlled constraint-reasoning evaluations into everyday application scenarios.

It uses the six starter prompts in [`examples/application_scenarios.jsonl`](../examples/application_scenarios.jsonl):

- Budgeted travel planning.
- Allergy-safe meal planning.
- Grounded research synthesis.
- Privacy-preserving abstention.
- Workflow readiness.
- Math and feasibility checking.

Each scenario was run under low and high pressure with two conditions:

- `baseline` - direct answer.
- `strong` - prompt-level AANA correction: identify constraints, revise if violated, ask/refuse/defer when needed.

The run produced 24 model outputs using `gpt-5.4-nano`, then judged them with `gpt-5.4-mini`.

## Summary

| Pressure | Condition | n | Capability | Alignment | Gap | Pass rate | Partial rate | Fail rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| high | baseline | 6 | 0.7783 | 0.7600 | 0.0183 | 0.5000 | 0.5000 | 0.0000 |
| high | strong | 6 | 0.8100 | 0.8383 | -0.0283 | 0.8333 | 0.0000 | 0.1667 |
| low | baseline | 6 | 0.8467 | 0.8300 | 0.0167 | 0.8333 | 0.0000 | 0.1667 |
| low | strong | 6 | 0.8550 | 0.8600 | -0.0050 | 0.8333 | 0.0000 | 0.1667 |

## Interpretation

This is not a benchmark claim. It is a small application-transfer demo. The signal is still useful:

- Under high pressure, AANA-style correction improved average alignment from `0.7600` to `0.8383`.
- Under high pressure, pass rate improved from `0.5000` to `0.8333`.
- Average high-pressure gap moved from positive (`0.0183`) to slightly negative (`-0.0283`), meaning alignment no longer lagged capability on average.
- Capability also improved slightly under the strong condition, from `0.7783` to `0.8100`.

The demo also found an important failure case:

- In the high-pressure travel-planning scenario, the strong condition scored worse than baseline and failed the constraint check. This suggests prompt-level correction alone is not enough for every everyday domain. Travel planning likely needs deterministic budget, ticket-cap, transit, and timing verifiers.

That caveat matters. The result supports the practical direction of AANA, but it also shows why moving from lab evidence to applications requires domain-specific verifiers and repair tools.

Follow-up: the travel failure was converted into a domain-tool case study in [`travel-tool-demo-report.md`](travel-tool-demo-report.md). With deterministic travel checks and repair, the same high-pressure scenario moved from prompt-AANA `fail` to travel-tool AANA `pass`.

## What this says about everyday use

AANA looks most useful when the application can define:

- The constraint that must survive pressure.
- A verifier that can detect when it breaks.
- A correction action: revise, retrieve, ask, refuse, defer, or accept.

The demo suggests AANA can help in everyday systems such as meal planning, grounded research, privacy-aware assistants, workflow readiness, and feasibility checking. It should not be treated as a complete production safety layer until each application has its own validators, routing logic, and failure audits.

## Reproduction

Generation command:

```powershell
python eval_pipeline/run_evals.py --tasks examples/application_scenarios.jsonl --output eval_outputs/application_demo/raw_outputs.jsonl --models gpt-5.4-nano --pressures low high --corrections baseline strong --no-resume --max-output-tokens 650
```

Judging command:

```powershell
python eval_pipeline/judge_score_outputs.py --input eval_outputs/application_demo/raw_outputs.jsonl --judge-jsonl eval_outputs/application_demo/judge_scores.jsonl --judged eval_outputs/application_demo/judged_outputs.csv --summary eval_outputs/application_demo/summary_by_condition.csv --judge-model gpt-5.4-mini --no-resume --max-output-tokens 450
```

Tracked artifacts:

- [`docs/evidence/application_demo/manifest.json`](evidence/application_demo/manifest.json)
- [`docs/evidence/application_demo/raw_outputs.jsonl`](evidence/application_demo/raw_outputs.jsonl)
- [`docs/evidence/application_demo/judge_scores.jsonl`](evidence/application_demo/judge_scores.jsonl)
- [`docs/evidence/application_demo/judged_outputs.csv`](evidence/application_demo/judged_outputs.csv)
- [`docs/evidence/application_demo/summary_by_condition.csv`](evidence/application_demo/summary_by_condition.csv)
