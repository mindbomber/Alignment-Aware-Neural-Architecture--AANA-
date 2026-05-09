# HF Dataset Proof Report

This report uses Hugging Face dataset-backed artifacts as evidence for AANA's control layer. It is not a benchmark hype page and does not claim raw agent-performance improvement.

## What This Proves

The current artifacts support narrow, measured claims about:

- false-positive control,
- unsafe/privacy/tool-use recall,
- grounded QA hallucination and unsupported-claim detection,
- private-read/write versus public-read routing.

## Current Measurements

| Proof axis | Artifact | Metric | Current result |
| --- | --- | --- | --- |
| False-positive control | `eval_outputs/privacy_pii_adapter_upgrade_results.json` | `false_positive_rate` | 0.000 |
| False-positive control | `eval_outputs/privacy_pii_adapter_upgrade_results.json` | `safe_allow_rate` | 1.000 |
| False-positive control | `eval_outputs/grounded_qa_adapter_upgrade_results.json` | `over_refusal_rate` | 0.000 |
| Unsafe recall | `eval_outputs/privacy_pii_adapter_upgrade_results.json` | `pii_recall` | 1.000 |
| Unsafe recall | `eval_outputs/agent_tool_use_control_upgrade_results.json` | `unsafe_action_recall` | 1.000 |
| Groundedness | `eval_outputs/grounded_qa_adapter_upgrade_results.json` | `unsupported_claim_recall` | 1.000 |
| Groundedness | `eval_outputs/grounded_qa_adapter_upgrade_results.json` | `answerable_safe_allow_rate` | 1.000 |
| Groundedness | `eval_outputs/grounded_qa_adapter_upgrade_results.json` | `citation_evidence_coverage` | 1.000 |
| Private/public read routing | `eval_outputs/agent_tool_use_control_upgrade_results.json` | `private_read_write_gating` | 1.000 |
| Private/public read routing | `eval_outputs/agent_tool_use_control_upgrade_results.json` | `ask_defer_refuse_quality` | 1.000 |
| Private/public read routing | `eval_outputs/agent_tool_use_control_upgrade_results.json` | `safe_allow_rate` | 1.000 |
| Private/public read routing | `eval_outputs/agent_tool_use_control_upgrade_results.json` | `schema_failure_rate` | 0.000 |

## Dataset Sources

- PIIMB, OpenPII, and Nemotron-PII for privacy/PII behavior.
- RAG-Grounded-QA and HaluBench-style schemas for grounded QA behavior.
- Qwen tool trajectories, Hermes function calling, MCP-Atlas, and MCPHunt-style traces for tool-use control behavior.

## Claim Boundary

These results support AANA as an audit/control/verification/correction layer. They do not prove that AANA is a standalone raw agent-performance engine.

Use comparative language carefully:

- It is acceptable to say the current HF-mapped validation artifacts show low false-positive/over-refusal rates, high unsafe recall, strong groundedness checks, and strong public/private read routing.
- Do not say AANA has lower or higher performance than another system unless a paired baseline artifact exists.
- Do not use these fixture-sized results as an official leaderboard claim.

## Limitations

- Current proof artifacts are HF-mapped fixture-sized validation suites, not full official leaderboard submissions.
- Some labels are policy-derived transformations of HF dataset schemas rather than human-reviewed benchmark-maintainer labels.
- Split isolation remains mandatory: never tune and publicly report on the same dataset/config/split.
- Larger held-out HF runs and maintainer-accepted protocols are still needed before stronger public claims.

