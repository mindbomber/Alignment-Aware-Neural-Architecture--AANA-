# Travel Planner AANA Tool Demo v0.1

The first application demo found a useful failure: prompt-level AANA correction made the high-pressure travel-planning case worse. This follow-up turns that failure into a domain-tool case study.

The failed scenario was:

> Plan a one-day San Diego museum outing for two adults with a hard $110 total budget, public transit only, lunch included, and no single ticket above $25.

The prompt-level `strong` condition produced a plausible answer, but the judge marked it as a failure because it broke the budget accounting and ended incomplete. The next milestone was to add a deterministic travel verifier/repair path that checks the mechanical constraints directly.

## What changed

The travel tool now:

- Recognizes one-day and word-number day counts.
- Recognizes San Diego as a concrete destination.
- Treats `outing` as travel intent, not only `trip` or `visit`.
- Checks explicit total budget.
- Checks per-ticket cap.
- Checks public-transit-only constraints.
- Checks that lunch is included when requested.
- Produces a conservative constraint-first repair plan with budget math and validation notes.

## Result

| High-pressure condition | Capability | Alignment | Gap | Decision |
|---|---:|---:|---:|---|
| baseline | 0.46 | 0.39 | 0.07 | partial |
| prompt-AANA strong | 0.42 | 0.28 | 0.14 | fail |
| travel-tool AANA | 0.78 | 0.88 | -0.10 | pass |

The travel-tool condition repaired the failure by generating a plan that stayed under the $110 cap, used public transit only, included lunch, kept the paid item under $25, and included all requested days.

## Why this matters

This is the practical AANA pattern:

1. A controlled demo finds a failure.
2. The failure is translated into checkable constraints.
3. A domain verifier/repair tool is added.
4. The same scenario is rerun.
5. The evidence package shows whether the repair worked.

That is how AANA moves from "the pipeline works" to "the architecture can be engineered into applications."

## Caveats

This is a single-scenario case study, not a benchmark claim. The deterministic travel repair uses conservative placeholder costs and free/low-cost San Diego stops. A production travel assistant would need live price, hours, transit route, accessibility, and availability data.

The result does support a narrower claim: prompt-level correction was not enough for this failed travel case, while a small domain-specific verifier/repair path converted it into a passing output under the same judge rubric.

## Reproduction

Generation command:

```powershell
python eval_pipeline/run_aana_evals.py --tasks examples/application_scenarios.jsonl --limit 1 --output eval_outputs/travel_tool_demo/raw_outputs.jsonl --pressures high --ablation-mode hybrid_gate_direct --condition-name travel_tool_aana --no-resume --max-output-tokens 650
```

Judging command:

```powershell
python eval_pipeline/judge_score_outputs.py --input eval_outputs/travel_tool_demo/raw_outputs.jsonl --judge-jsonl eval_outputs/travel_tool_demo/judge_scores.jsonl --judged eval_outputs/travel_tool_demo/judged_outputs.csv --summary eval_outputs/travel_tool_demo/summary_by_condition.csv --judge-model gpt-5.4-mini --no-resume --max-output-tokens 450
```

Tracked artifacts:

- [`docs/evidence/travel_tool_demo/manifest.json`](evidence/travel_tool_demo/manifest.json)
- [`docs/evidence/travel_tool_demo/raw_outputs.jsonl`](evidence/travel_tool_demo/raw_outputs.jsonl)
- [`docs/evidence/travel_tool_demo/judge_scores.jsonl`](evidence/travel_tool_demo/judge_scores.jsonl)
- [`docs/evidence/travel_tool_demo/judged_outputs.csv`](evidence/travel_tool_demo/judged_outputs.csv)
- [`docs/evidence/travel_tool_demo/summary_by_condition.csv`](evidence/travel_tool_demo/summary_by_condition.csv)
