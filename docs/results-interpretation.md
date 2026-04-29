# Results Interpretation

The pipeline writes intermediate and final results to `eval_outputs/`. This folder is ignored by git because it can contain many generated rows and model outputs.

## Common output files

- Raw JSONL files, such as `raw_outputs.jsonl` or `aana_outputs.jsonl`, contain one model output per line.
- Judge JSONL files, such as `judge_scores.jsonl`, contain one judge result per line.
- Judged CSV files combine raw outputs with judge scores.
- Summary CSV files aggregate scores by model, pressure, correction condition, and task block.
- Plot files visualize summary trends.

## Core columns

Common raw-output columns:

- `id` - Task identifier.
- `block` - Evaluation category.
- `task_type` - Specific task type.
- `model` - Model or model-plus-condition label.
- `pressure` - `low` or `high`.
- `correction` - Evaluation condition, such as `baseline`, `weak`, `strong`, or an AANA variant.
- `prompt` - User prompt that was sent.
- `response_text` - Candidate answer.
- `api_error` - Error text if the model call failed.

Common judged-output columns:

- `judge_model` - Model used as the judge.
- `capability_score` - How useful, complete, correct, and task-fit the answer is.
- `alignment_score` - How well the answer preserves truthfulness, safety, constraints, abstention, and calibrated uncertainty.
- `gap_score` - `capability_score - alignment_score`.
- `decision` - `pass`, `partial`, or `fail`.
- `rationale` - Short judge explanation.

Originality judged outputs also include:

- `novelty_score` - Non-obviousness, fresh structure, useful framing, or distinctive design.
- `viable_originality_score` - Novelty that remains valid after alignment constraints are applied.

## Reading the scores

### Capability score

A high capability score means the answer is useful for the task. It may be complete, clear, correct, or operationally helpful.

A high capability score alone does not mean the answer is aligned. A persuasive answer that violates a budget, invents a citation, or guesses private information can still appear capable.

### Alignment score

A high alignment score means the answer preserved the important constraints.

For this repo, alignment includes:

- Truthfulness.
- Constraint preservation.
- Safety and non-manipulation.
- Appropriate refusal or abstention.
- Calibrated uncertainty.

### Gap score

`gap_score = capability_score - alignment_score`.

Interpretation:

- Near `0` - Capability and alignment are roughly balanced.
- Positive - The answer may look useful while losing alignment.
- Negative - The answer may be cautious or aligned but less capable.

Large positive gaps are especially interesting because they can reveal outputs that look good at first glance but break important constraints.

### Pass rate

Some summary scripts compute pass rate from judge decisions.

Pass rate is the fraction of rows marked `pass` in a group. It is easy to read but less detailed than the score columns.

## Comparing conditions

Useful comparisons:

- `baseline` vs `strong` - Does prompt-only correction improve alignment?
- `baseline` vs AANA loop - Does verifier-grounded correction improve results?
- Low pressure vs high pressure - Does alignment degrade under pressure?
- Tool-assisted vs non-tool-assisted - Do deterministic checks catch failures that a model misses?
- Originality AANA vs baseline - Does novelty improve without reducing constraint viability?

## Caveats

- Model judges can be inconsistent or wrong.
- Small sample sizes are noisy.
- Deterministic constraint tools cover known patterns, not every possible violation.
- Generated outputs should be reviewed before publication.
- Treat the results as research evidence, not a final certified benchmark.
