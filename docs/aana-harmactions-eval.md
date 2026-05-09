# AANA HarmActionsEval Benchmark

This note records a reproducible AANA benchmark run against the public
HarmActions dataset from
`Pro-GenAI/Agent-Action-Guard`, a GitHub benchmark suite for agent action and
tool-use safety.

## Scout Result

The benchmark scout searched these buckets:

- Mechanistic interpretability
- Model evaluation / LLM evals
- Robustness / adversarial prompts
- Agent control / tool-use reliability
- Alignment surveys and datasets
- Causal tracing / circuit discovery

High-fit candidates included:

| Bucket | Candidate | Fit |
| --- | --- | --- |
| Model evaluation / LLM evals | `openai/evals` | Broad eval registry; issue #1636 requests HarmActionsEval integration. |
| Agent control / tool-use reliability | `Pro-GenAI/Agent-Action-Guard` | Ships HarmActions and HarmActionsEval for unsafe tool-call behavior. |
| Agent control / tool-use reliability | `SalesforceAIResearch/MCP-Universe` | Agent tool-use benchmark framework. |
| Agent control / tool-use reliability | `Accenture/mcp-bench` | MCP tool-use benchmark. |
| Robustness / adversarial prompts | `usail-hkust/JailTrickBench` | Jailbreak benchmark suite. |
| Robustness / adversarial prompts | `wuyoscar/ISC-Bench` | Internal safety collapse benchmark. |

`Pro-GenAI/Agent-Action-Guard` was selected because HarmActionsEval directly
tests whether an agent executes harmful tool actions, which matches AANA's
runtime gate model.

## AANA Setup

The benchmark uses `examples/agent_action_safety_guardrail_adapter.json` and
`scripts/aana_harmactions_eval.py`.

The runner gives AANA only:

- original user request
- observed prompt
- tool name
- tool arguments

Benchmark labels are used only for scoring after the gate returns.

## Reproduce

Clone Agent Action Guard, then run:

```bash
python scripts/aana_harmactions_eval.py \
  --dataset eval_outputs/benchmark_scout/repos/Agent-Action-Guard/python/agent_action_guard/harmactions_dataset.json \
  --output eval_outputs/benchmark_scout/aana_harmactions_eval_results.json
```

## Measured Local Result

Dataset: 260 rows.

| Metric | Value |
| --- | ---: |
| Accuracy | 88.08% |
| Unsafe rows | 141 |
| Unsafe blocked | 111 |
| Unsafe block rate | 78.72% |
| Safe rows | 119 |
| Safe allowed | 118 |
| Safe allow rate | 99.16% |
| False negatives | 30 |
| False positives | 1 |

Violation counts:

| Violation | Count |
| --- | ---: |
| `harmful_or_illegal_tool_action` | 84 |
| `private_data_or_credential_risk` | 26 |
| `irreversible_external_effect_without_review` | 18 |
| `ambiguous_high_risk_action` | 3 |
| `user_intent_mismatch` | 3 |

## Caveats

This is a deterministic verifier-gate benchmark, not a production safety
guarantee. AANA makes the action gate, evidence boundary, correction route, and
audit surface explicit, but production use still requires live tool schemas,
authorization state, policy-specific evidence, calibrated thresholds, audit
logging, and human review paths for ambiguous or high-impact actions.
