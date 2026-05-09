# AANA Production-Candidate Evidence Pack

## Executive Boundary

AANA is production-candidate as an audit/control/verification/correction layer.

AANA is not yet proven as a raw agent-performance engine.

Result label: `heldout`

This evidence pack is a claim boundary, not a marketing page. It records what the current AANA implementation supports, where it fails, which claims are blocked, and which evidence must exist before stronger public claims are made.

## Task List

- Define the exact production-candidate boundary language: completed.
- Link the current governance, dataset, and adapter evidence artifacts: completed.
- Document failures, false positives, latency limits, and unsupported domains: completed.
- Add a machine-readable manifest so the report can be validated: completed.
- Add a validator, development command, packaging script, and tests: completed.

## Evidence Included

Current evidence supports AANA as a control layer around model and agent behavior:

- Dataset governance: `examples/hf_dataset_validation_registry.json` records split-use isolation so calibration, held-out validation, and external reporting are not mixed.
- Benchmark reporting governance: `examples/benchmark_reporting_manifest.json` blocks diagnostic probe results from public performance claims.
- Benchmark-fit lint: `examples/benchmark_fit_lint_manifest.json` rejects known-answer literals from general AANA paths.
- Cross-domain family validation: `examples/cross_domain_adapter_family_validation.json` maps privacy/security, research/grounded QA, customer support, finance, ecommerce/retail, and agent tool-use/MCP families to external HF held-out validation requirements.
- HF dataset proof report: `examples/hf_dataset_proof_report.json` and `docs/hf-dataset-proof-report.md` tie public dataset-backed claims to measured false-positive control, unsafe recall, groundedness, and public/private read routing metrics.
- Privacy/PII adapter validation: `eval_outputs/privacy_pii_adapter_upgrade_results.json` measures PII recall, false positives, safe allow rate, redaction correctness, and route accuracy on fixture-level held-out cases.
- Grounded QA adapter validation: `eval_outputs/grounded_qa_adapter_upgrade_results.json` measures unsupported-claim recall, answerable safe allow rate, evidence coverage, over-refusal, and route accuracy on fixture-level held-out cases.
- Agent tool-use control validation: `eval_outputs/agent_tool_use_control_upgrade_results.json` measures unsafe-action recall, private-read/write gating, ask/defer/refuse quality, schema failure rate, safe allow rate, and route accuracy on fixture-level held-out cases.

These artifacts are useful engineering evidence. They do not prove broad autonomous task success, leaderboard superiority, or production safety for every domain.

## What The Evidence Supports

AANA is a credible production-candidate layer when used for:

- Pre-action audit and policy routing.
- Evidence sufficiency checks before answers or tool calls.
- Verification and correction around privacy, groundedness, and tool-use risk.
- Ask, defer, refuse, or revise routing when authorization or evidence is missing.
- Structured audit trails and release gates that keep public claims tied to measured artifacts.

The strongest current claim is about control quality, not raw agent competence.

## Failures

Known failures and incomplete areas:

- Tau2-style raw task completion remains mixed. Earlier full-domain and dry-run work showed that AANA can over-block or fail to recover enough planner state when paired with a weak base scaffold.
- Long benchmark runs have hit local timeout limits, so some all-domain results are incomplete or diagnostic only.
- Probe-enabled benchmark runs are explicitly excluded from public AANA claims because they may know task-specific recovery flows.
- Some validators currently use fixture-level held-out cases mapped to external datasets, not large human-reviewed external runs.
- Schema and evidence quality still matter. If the runtime emits weak tool metadata, missing evidence refs, or ambiguous authorization state, AANA may ask or defer instead of completing the action.
- The current lightweight deterministic verifiers can miss semantic variants that require stronger learned or model-judged classification.
- AANA does not replace a capable base planner. It can gate, correct, and recover, but it cannot guarantee that the underlying agent chooses the right task strategy.

## False Positives

Current false-positive risks:

- Public or low-risk reads may be delayed if a tool is misclassified as private or if the runtime omits category metadata.
- Safe answers can be deferred when supporting evidence is present but not referenced in the event payload.
- Privacy and groundedness adapters may over-route borderline cases when names, identifiers, claims, and citations appear in unusual formats.
- Conservative thresholds can protect unsafe-action recall while reducing safe allow rate.
- Domain adapters can be too cautious in finance, legal, medical, HR, pharma, and identity-bound workflows unless authorization and evidence state are explicit.

False positives are acceptable for high-risk control layers only when product UX includes clear ask/defer recovery. They are not acceptable as proof of raw agent-performance improvement.

## Latency

Latency is not yet a production SLA claim.

The current evidence pack validates correctness and governance, not p95 or p99 runtime performance under production traffic. AANA latency depends on:

- Schema validation and adapter execution.
- Evidence retrieval and citation checks.
- Optional learned/model-judged classifiers.
- Human-review or defer paths.
- Runtime integration overhead in LangChain, OpenAI Agents SDK, AutoGen, CrewAI, MCP, or custom tool-call middleware.

Before any latency claim, each target runtime needs measured p50, p95, p99, timeout rate, and recovery-path latency on representative traffic.

## Unsupported Domains

AANA is not yet proven for:

- Raw autonomous task performance as a standalone agent engine.
- Medical diagnosis or treatment decisions.
- Legal advice, legal strategy, or jurisdiction-specific legal determinations.
- Financial advice, trading, lending, underwriting, or irreversible financial transactions.
- Autonomous destructive actions such as deletes, payments, credential export, infrastructure teardown, or account closure without separate authorization controls.
- Tool families that do not emit the AANA pre-tool-call schema or equivalent metadata.
- Domains without registered datasets, held-out validation, evidence connectors, and human-review escalation.
- Broad multilingual safety beyond the currently validated privacy and PII coverage.
- Multimodal inputs, unless an adapter family has specific evidence and validation for that modality.

## Public Claim Rules

- Never merge diagnostic probe results into public AANA claims.
- Never tune and publicly report on the same split.
- Do not claim benchmark improvement unless a measured non-probe run confirms it.
- Do not claim production readiness for raw agent performance from control-layer evidence.
- Stronger adapter-family claims require external held-out or maintainer-accepted validation and a published limitations section.

## Next Evidence Needed

The next evidence layer should include:

- Larger external held-out runs with human-reviewed or maintainer-accepted labels.
- Base-agent versus base-agent-plus-AANA ablations that measure unsafe-action prevention, authorization compliance, groundedness, recovery quality, false positives, and task success impact.
- Runtime latency benchmarks for each supported middleware path.
- Domain-owner review for regulated domains.
- Official benchmark submissions only after the non-probe measured run is complete and honestly reported.
