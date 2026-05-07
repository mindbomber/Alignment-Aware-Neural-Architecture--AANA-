# AANA Head-to-Head Findings

AANA is a runtime architecture for agent action reliability. It is not a base
model, not just a classifier, not just a policy prompt, and not just an
LLM-as-judge safety check.

The core finding across the public head-to-head runs is:

> AANA improves agent action reliability by combining structured pre-tool-call
> contracts, verifier gates, and evidence-recovery loops. In these diagnostics,
> AANA preserves unsafe-action recall while recovering more safe actions than
> permissive agents, single classifiers, prompt-only guards, LLM judges, or
> static contract gates.

## What Was Tested

The head-to-head tests compare AANA against common agent safety baselines:

- **Permissive agent**: accepts every proposed tool call.
- **Single classifier**: a transferred learned action-risk classifier.
- **Prompt-only policy guardrail**: flattened policy/action/evidence text.
- **LLM-as-judge safety checker**: `gpt-4o-mini` judging flattened text.
- **Structured contract gate without recovery**: consumes the noisy contract
  event as emitted.
- **AANA with evidence recovery**: uses the contract, verifier gate, and a
  correction/evidence-recovery pass before final routing.

All runs below are architecture diagnostics, not production safety guarantees
or official leaderboard submissions.

## Summary Results

### Qwen External Agent Traces

Source dataset:
[`zake7749/Qwen-3.6-plus-agent-tool-calling-trajectory`](https://huggingface.co/datasets/zake7749/Qwen-3.6-plus-agent-tool-calling-trajectory)

Rows: `360` transformed external tool-call traces with moderate noisy-evidence
stressors.

| Architecture | Accuracy | Unsafe Recall | Safe Allow | False Positives | False Negatives |
| --- | ---: | ---: | ---: | ---: | ---: |
| Permissive agent | `50.00%` | `0.00%` | `100.00%` | `0` | `180` |
| Single classifier | `50.00%` | `100.00%` | `0.00%` | `180` | `0` |
| Prompt-only policy guardrail | `81.67%` | `96.67%` | `66.67%` | `60` | `6` |
| LLM-as-judge safety checker | `73.33%` | `100.00%` | `46.67%` | `96` | `0` |
| Structured contract gate without recovery | `92.78%` | `100.00%` | `85.56%` | `26` | `0` |
| AANA with evidence recovery | `100.00%` | `100.00%` | `100.00%` | `0` | `0` |

### Hermes Function-Calling Traces

Second source dataset:
[`NousResearch/hermes-function-calling-v1`](https://huggingface.co/datasets/NousResearch/hermes-function-calling-v1)

Rows: `360` transformed Hermes function-calling rows with moderate
noisy-evidence stressors.

| Architecture | Accuracy | Unsafe Recall | Safe Allow | False Positives | False Negatives |
| --- | ---: | ---: | ---: | ---: | ---: |
| Permissive agent | `50.00%` | `0.00%` | `100.00%` | `0` | `180` |
| Single classifier | `50.00%` | `100.00%` | `0.00%` | `180` | `0` |
| Prompt-only policy guardrail | `93.06%` | `97.22%` | `88.89%` | `20` | `5` |
| LLM-as-judge safety checker | `85.28%` | `99.44%` | `71.11%` | `52` | `1` |
| Structured contract gate without recovery | `92.22%` | `100.00%` | `84.44%` | `28` | `0` |
| AANA with evidence recovery | `100.00%` | `100.00%` | `100.00%` | `0` | `0` |

## What Failed

The failures are as important as the wins:

- **Permissive agents** allow unsafe actions by design.
- **Single classifiers** preserve recall under domain shift by blocking
  everything, which destroys safe allow.
- **Prompt-only guardrails** are useful, but flattening policy, authorization,
  evidence, and tool semantics still misses unsafe cases and over-blocks safe
  ones.
- **LLM-as-judge checkers** can be conservative, but they over-block safe calls
  when authorization evidence is noisy or implicit.
- **Static contract gates** are strong, but still over-block when evidence refs
  are dropped, stale, downgraded, or contradicted.

AANA's advantage appears when the system can recover or reconstruct missing
evidence before final routing.

## Evidence Tiers

Not all evidence is equally strong.

| Tier | Evidence Type | Current Examples | Interpretation |
| --- | --- | --- | --- |
| Tier 1 | Official or externally hosted benchmark submission | PIIMB Presidio + AANA | Strongest public ablation so far, but task-specific. |
| Tier 2 | Public dataset with reproducible transform and policy-derived labels | Qwen traces, Hermes traces | Good architecture diagnostics, not human-reviewed safety labels. |
| Tier 3 | Local synthetic or blind ablation sets | GAP/action-gate v2-v5, adapter calibration | Useful for development and failure analysis, weaker external validity. |

The Qwen and Hermes head-to-heads improve source diversity, but they do not
settle human-reviewed safety validity. The next stronger step is a benchmark
maintainer or independent annotators labeling a trace set.

## Public Artifacts

- Qwen permissive baseline:
  <https://huggingface.co/datasets/mindbomber/aana-head-to-head-permissive-vs-aana>
- Qwen single classifier:
  <https://huggingface.co/datasets/mindbomber/aana-head-to-head-single-classifier-vs-aana>
- Qwen prompt-only policy guardrail:
  <https://huggingface.co/datasets/mindbomber/aana-head-to-head-prompt-policy-vs-aana>
- Qwen LLM-as-judge:
  <https://huggingface.co/datasets/mindbomber/aana-head-to-head-llm-judge-vs-aana>
- Qwen contract recovery ablation:
  <https://huggingface.co/datasets/mindbomber/aana-head-to-head-contract-no-recovery-vs-aana>
- Hermes second-source head-to-head:
  <https://huggingface.co/datasets/mindbomber/aana-external-validity-hermes-head-to-head>
- AANA model card:
  <https://huggingface.co/mindbomber/aana>
- Try AANA:
  <https://huggingface.co/spaces/mindbomber/aana-demo>

## Bottom Line

The public results support a narrow, defensible claim:

> AANA is most useful for consequential agent actions where the runtime needs
> explicit tool category, authorization state, evidence references, verifier
> gates, and correction/recovery before execution.

They do not prove production safety, state-of-the-art performance, or general
alignment. They show a repeatable architecture pattern worth testing with
human-reviewed traces.
