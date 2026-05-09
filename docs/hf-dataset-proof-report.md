# HF Dataset Proof Report

This report uses Hugging Face dataset-backed artifacts as evidence for AANA's control layer. It is not a benchmark hype page and does not claim raw agent-performance improvement.

Result label: `heldout`

## What This Proves

The current artifacts support narrow, measured claims about:

- false-positive control,
- unsafe/privacy/tool-use recall,
- grounded QA hallucination and unsupported-claim detection,
- private-read/write versus public-read routing,
- noisy authorization/evidence robustness for agent tool calls,
- safety/adversarial prompt-routing tradeoffs, labeled diagnostic,
- high-risk finance QA evidence routing, labeled diagnostic,
- governance/compliance policy routing, labeled diagnostic,
- integration validation across CLI, SDK, FastAPI, MCP, and middleware surfaces.

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
| Agent tool-use diagnostic chain | `eval_outputs/aana_agent_tool_use_diagnostic_evidence_chain.json` | `tool_use_v2_unsafe_action_recall` | 1.000 |
| Agent tool-use diagnostic chain | `eval_outputs/aana_agent_tool_use_diagnostic_evidence_chain.json` | `read_routing_v2_public_read_allow_rate` | 1.000 |
| Agent tool-use diagnostic chain | `eval_outputs/aana_agent_tool_use_diagnostic_evidence_chain.json` | `read_routing_v2_private_read_escalation_rate` | 1.000 |
| Agent tool-use diagnostic chain | `eval_outputs/aana_agent_tool_use_diagnostic_evidence_chain.json` | `authorization_v2_missing_auth_recall` | 1.000 |
| Agent tool-use diagnostic chain | `eval_outputs/aana_agent_tool_use_diagnostic_evidence_chain.json` | `authorization_v2_stale_evidence_defer_rate` | 1.000 |
| Agent tool-use diagnostic chain | `eval_outputs/aana_agent_tool_use_diagnostic_evidence_chain.json` | `authorization_v2_over_block_rate` | 0.000 |
| Safety/adversarial prompt routing diagnostic | `eval_outputs/safety_adversarial_hf_experiment_results.json` | `harmful_request_recall` | 0.342 |
| Safety/adversarial prompt routing diagnostic | `eval_outputs/safety_adversarial_hf_experiment_results.json` | `safe_prompt_allow_rate` | 0.951 |
| Safety/adversarial prompt routing diagnostic | `eval_outputs/safety_adversarial_hf_experiment_results.json` | `false_refusal_rate` | 0.049 |
| Safety/adversarial prompt routing diagnostic | `eval_outputs/safety_adversarial_hf_experiment_results.json` | `recovery_suggestion_quality` | 1.000 |
| Finance high-risk QA diagnostic | `eval_outputs/finance_high_risk_qa_hf_experiment_results.json` | `unsupported_finance_claim_recall` | 1.000 |
| Finance high-risk QA diagnostic | `eval_outputs/finance_high_risk_qa_hf_experiment_results.json` | `supported_answer_safe_allow_rate` | 1.000 |
| Finance high-risk QA diagnostic | `eval_outputs/finance_high_risk_qa_hf_experiment_results.json` | `evidence_coverage` | 1.000 |
| Finance high-risk QA diagnostic | `eval_outputs/finance_high_risk_qa_hf_experiment_results.json` | `over_refusal_rate` | 0.000 |
| Governance/compliance policy-routing diagnostic | `eval_outputs/governance_compliance_hf_experiment_results.json` | `policy_citation_coverage` | 1.000 |
| Governance/compliance policy-routing diagnostic | `eval_outputs/governance_compliance_hf_experiment_results.json` | `risk_route_accuracy` | 1.000 |
| Governance/compliance policy-routing diagnostic | `eval_outputs/governance_compliance_hf_experiment_results.json` | `missing_evidence_recall` | 1.000 |
| Governance/compliance policy-routing diagnostic | `eval_outputs/governance_compliance_hf_experiment_results.json` | `human_review_escalation_recall` | 1.000 |
| Governance/compliance policy-routing diagnostic | `eval_outputs/governance_compliance_hf_experiment_results.json` | `safe_allow_rate` | 1.000 |
| Governance/compliance policy-routing diagnostic | `eval_outputs/governance_compliance_hf_experiment_results.json` | `over_refusal_rate` | 0.000 |
| Integration validation v1 held-out | `eval_outputs/integration_validation_v1_heldout_results.json` | `route_parity` | 1.000 |
| Integration validation v1 held-out | `eval_outputs/integration_validation_v1_heldout_results.json` | `blocked_tool_non_execution` | 1.000 |
| Integration validation v1 held-out | `eval_outputs/integration_validation_v1_heldout_results.json` | `decision_shape_parity` | 1.000 |
| Integration validation v1 held-out | `eval_outputs/integration_validation_v1_heldout_results.json` | `audit_log_completeness` | 1.000 |
| Integration validation v1 held-out | `eval_outputs/integration_validation_v1_heldout_results.json` | `schema_failure_rate` | 0.000 |

## Dataset Sources

- PIIMB, OpenPII, and Nemotron-PII for privacy/PII behavior.
- RAG-Grounded-QA and HaluBench-style schemas for grounded QA behavior.
- Qwen tool trajectories, Hermes function calling, MCP-Atlas, and MCPHunt-style traces for tool-use control behavior.
- The agent tool-use diagnostic chain report links the broad tool-use, public/private read routing, and authorization robustness artifacts in `docs/aana-agent-tool-use-diagnostic-evidence-chain.md`.
- ToxicChat, canbingol harmful-prompts, JailbreakBench behaviors, HarmBench, and AdvBench for safety/adversarial prompt-routing diagnostics. These are diagnostic control-layer results, not a content-moderation benchmark claim.
- FinanceBench for high-risk finance QA evidence routing diagnostics. The current artifact uses official supported answers plus controlled unsupported financial overclaim counterfactuals, so it is diagnostic rather than official FinanceBench leaderboard evidence.
- Hugging Face policy-doc metadata plus a small AANA repo-heldout policy case set for governance/compliance policy routing diagnostics. The current artifact tests source-boundary handling, missing evidence, human-review escalation, private-data export refusal, and destructive-action controls; it is not legal, regulatory, or platform-policy certification.
- AANA-generated held-out tool-call cases plus Hermes/MCP-Atlas/MCPHunt-style trace schemas for platform integration validation. The current artifact tests local runtime parity, blocked-tool non-execution, audit completeness, schema failure rate, and latency.

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
- The safety/adversarial prompt-routing result is intentionally diagnostic: deterministic AANA preserves safe allow but misses many harmful prompts; the diversified verifier improves recall while conservative calibration protects safe allow; AdvBench transfer remains weak.
- The FinanceBench high-risk QA result is intentionally diagnostic: it tests evidence-gated acceptance and unsupported finance-claim routing, not investment advice quality or official benchmark rank.
- The governance/compliance policy-routing result is intentionally diagnostic: it uses small repo-heldout labels and external policy-doc metadata as a source boundary, not independent human-reviewed compliance labels.
- The integration validation result is held-out platform validation. It proves local surface parity and execution blocking for the tested cases, not broad end-to-end agent task success.
