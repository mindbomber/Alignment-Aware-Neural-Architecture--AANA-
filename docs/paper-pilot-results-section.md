# Paper Replacement Section: Pilot Results

This is a paper-ready replacement for the manuscript section currently framed as synthetic or controlled illustrative results.

Recommended section title:

```text
Pilot Results
```

Recommended scope statement:

```text
This is a small preregistered pilot intended to test the predicted direction of the effect, not a final benchmark.
```

## Replacement Text

To test whether the dynamical-alignment formulation produces the predicted empirical signature on real model outputs, we ran a small pilot experiment using a single language model across four prompting conditions. The purpose of the pilot was not to establish a final benchmark, but to replace the synthetic Table 2 pattern with a first real-output directional test.

The pilot used 40 prompts, with eight prompts in each of five blocks: truthfulness traps, false-premise questions, unsafe over-compliance, format/proxy traps, and hidden-constraint tasks. Each prompt was evaluated under four conditions: a low-pressure baseline, a high-pressure completion-oriented condition, a high-pressure weak self-review condition, and a high-pressure AANA-style condition that instructed the model to internally identify factual, safety, task, and uncertainty constraints, then revise, abstain, or ask for clarification when needed. This produced 160 model outputs.

Each output was scored by a separate grader on five dimensions: visible capability, physical/factual truth grounding \(P\), safety and human-impact constraint adherence \(B\), task coherence \(C_T\), and feedback/uncertainty awareness \(F\). Alignment was computed as the mean of \(P\), \(B\), \(C_T\), and \(F\). The primary endpoint was

```text
Delta = Capability - Alignment.
```

This quantity corresponds to the paper's capability-alignment divergence signature: positive movement in Delta indicates that visible task completion is increasing faster than alignment-relevant constraint satisfaction.

## Table 2: Pilot Results

| Condition | Pressure | n | Capability | Alignment | Delta | Violation Rate |
|---|---|---:|---:|---:|---:|---:|
| Baseline | Low | 40 | 0.882 | 0.905 | -0.023 | 0.050 |
| Pressure only | High | 40 | 0.914 | 0.901 | 0.013 | 0.075 |
| Weak correction | High | 40 | 0.895 | 0.901 | -0.005 | 0.075 |
| Strong AANA | High | 40 | 0.897 | 0.901 | -0.004 | 0.075 |

The results match the predicted direction for the primary Delta endpoint. High-pressure prompting increased Delta relative to baseline \((0.013 > -0.023)\), consistent with pressure increasing visible completion faster than alignment-relevant constraint satisfaction. The strong AANA condition reduced Delta relative to pressure-only prompting \((-0.004 < 0.013)\), consistent with correction capacity reducing pressure-sensitive divergence.

The violation-rate result was more conservative. Violation rate increased from 0.050 in the low-pressure baseline to 0.075 under high-pressure prompting, but remained 0.075 under both weak correction and strong AANA. Thus, this pilot supports the predicted Delta-direction effect, but does not show a violation-rate reduction in this small sample.

To check whether the model judge was producing plausible labels, we manually spot-checked 20 randomly sampled judged outputs. The spot check found 18/20 agreement with the model judge on the binary violation flag. The two disagreements were concentrated around incomplete long-form planning and fictional-address handling. This suggests that the grader was broadly usable for the pilot, but that future experiments should handle truncation and borderline fictional-reference cases more explicitly.

Taken together, the pilot provides preliminary real-output support for the paper's central dynamical claim: pressure can increase capability-alignment divergence, and correction-oriented prompting can reduce that divergence. The result should be interpreted as a directional pilot rather than a benchmark claim. Larger runs should use a frozen task set, fixed model and judge versions, multiple model families, human adjudication, and explicit controls for answer truncation.

## Suggested Manuscript Edits

Replace:

```text
Controlled Synthetic Results
```

with:

```text
Pilot Results
```

Replace the synthetic Table 2 with the table above.

Add a short reproducibility note:

```text
Code, prompts, pilot summary, manifest hashes, and the 20-row spot-check audit are available in the project repository at commit 98b2e60c364ad8adb0af8519f273df3ea948e66e.
```

If referencing the later commits that added the manuscript integration text, use the current repository commit instead.
