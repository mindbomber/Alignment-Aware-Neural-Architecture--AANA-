# Table 2 Pilot Results

This pilot replaces the synthetic Table 2 shape with real model outputs.

| Condition | Pressure | n | Capability | Alignment | Delta | Violation Rate |
|---|---|---:|---:|---:|---:|---:|
| baseline | low | 40 | 0.882 | 0.905 | -0.023 | 0.050 |
| pressure_only | high | 40 | 0.914 | 0.901 | 0.013 | 0.075 |
| weak_correction | high | 40 | 0.895 | 0.901 | -0.005 | 0.075 |
| strong_aana | high | 40 | 0.897 | 0.901 | -0.004 | 0.075 |

## Directional Tests

- Delta pressure-only > baseline: `0.013 > -0.023` -> `True`
- Delta strong AANA < pressure-only: `-0.004 < 0.013` -> `True`
- Violation rate strong AANA < pressure-only: `0.075 < 0.075` -> `False`

## Caveat

This is a small pilot intended to test the predicted direction of the effect, not a final benchmark.
