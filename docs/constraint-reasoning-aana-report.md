# Constraint-Reasoning AANA Comparison

This report compares constraint-reasoning results across prompt-only and AANA-style correction conditions.
All conditions are matched on the same 60 task IDs and both pressure levels when computing deltas against baseline.

## Sources

- `eval_outputs/heldout_v2/judged_outputs_v2.csv`
- `eval_outputs/schema_ablation/hybrid_gate_judged.csv`

Tracked evidence snapshots for GitHub review:

- `docs/evidence/constraint_reasoning_aana_summary.csv`
- `docs/evidence/constraint_reasoning_aana_paired_tests.csv`
- `docs/evidence/constraint_reasoning_aana_pressure_breakdown.csv`
- `docs/evidence/plots/`

The broader theoretical framing is in `papers/ATS_Dynamical_Alignment_arXiv.pdf`.

## Main Result

| Condition | n | Capability | Alignment | Pass rate | 95% pass CI | Fail rate | Pass delta vs baseline | 95% delta CI | Capability delta | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 120 | 0.662 | 0.751 | 0.458 | [0.372, 0.547] | 0.108 | 0.000 | [0.000, 0.000] | 0.000 | 1.000 |
| Strong prompt | 120 | 0.673 | 0.784 | 0.458 | [0.372, 0.547] | 0.075 | 0.000 | [-0.100, 0.100] | 0.011 | 1.000 |
| AANA loop | 120 | 0.816 | 0.880 | 0.733 | [0.648, 0.804] | 0.017 | 0.275 | [0.167, 0.383] | 0.154 | 0.000 |
| AANA tools structured | 120 | 0.922 | 0.973 | 0.983 | [0.941, 0.995] | 0.000 | 0.525 | [0.433, 0.617] | 0.260 | 0.000 |
| AANA hybrid gate | 120 | 0.908 | 0.974 | 0.983 | [0.941, 0.995] | 0.000 | 0.525 | [0.433, 0.608] | 0.246 | 0.000 |
| Hybrid gate direct | 120 | 0.918 | 0.977 | 1.000 | [0.969, 1.000] | 0.000 | 0.542 | [0.450, 0.633] | 0.256 | 0.000 |

## Pressure Split

| Pressure | Condition | Capability | Alignment | Pass rate | Fail rate |
|---|---|---:|---:|---:|---:|
| high | Baseline | 0.635 | 0.713 | 0.417 | 0.167 |
| low | Baseline | 0.689 | 0.789 | 0.500 | 0.050 |
| high | Strong prompt | 0.664 | 0.804 | 0.467 | 0.067 |
| low | Strong prompt | 0.682 | 0.764 | 0.450 | 0.083 |
| high | AANA loop | 0.805 | 0.894 | 0.800 | 0.017 |
| low | AANA loop | 0.827 | 0.866 | 0.667 | 0.017 |
| high | AANA tools structured | 0.915 | 0.971 | 0.983 | 0.000 |
| low | AANA tools structured | 0.928 | 0.975 | 0.983 | 0.000 |
| high | AANA hybrid gate | 0.897 | 0.974 | 0.967 | 0.000 |
| low | AANA hybrid gate | 0.919 | 0.973 | 1.000 | 0.000 |
| high | Hybrid gate direct | 0.914 | 0.976 | 1.000 | 0.000 |
| low | Hybrid gate direct | 0.923 | 0.977 | 1.000 | 0.000 |

## Interpretation

- `strong` prompt-only correction does not improve constraint pass rate over baseline.
- `aana_loop` improves pass rate substantially while also increasing capability.
- `aana_tools_structured`, `aana_tools_hybrid_gate`, and `hybrid_gate_direct` produce the strongest constraint-reasoning results: near-perfect or perfect pass rates, higher capability, higher alignment, and zero fail rate in this sample.
- The paired McNemar counts test pass/non-pass changes on the same task IDs; small p-values indicate the pass-rate change is unlikely to be explained by matched-task noise alone.

## Methods

- Pass-rate intervals use Wilson 95% confidence intervals.
- Delta intervals use a paired, pressure-stratified bootstrap with 10,000 iterations and fixed random seeds.
- McNemar p-values use an exact two-sided binomial test over discordant paired pass/non-pass outcomes.
- Capability and alignment are model-judge scores from the checked-in judged CSV files listed above.

## Caveats

- These are judged model outputs, not human-adjudicated labels.
- Hybrid-gate rows come from a schema-ablation run, but they use the same constraint task IDs and pressure split.
- A final publication-grade claim should rerun all conditions in one command with a frozen task file, model versions, judge model, and date-stamped manifest.

## Reproduction

```powershell
python eval_pipeline/compare_constraint_reasoning.py
python eval_pipeline/plot_results.py `
  --summary eval_outputs/constraint_reasoning_aana_evidence/plot_summary_by_condition.csv `
  --output-dir eval_outputs/constraint_reasoning_aana_evidence/plots
```
