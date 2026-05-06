# AANA Mechanistic Interoperability Design Brief

Status: milestone 1 concept mapping.

Source paper: [`papers/ATS_AANA_MI_NeurIPS_CameraReady.pdf`](../papers/ATS_AANA_MI_NeurIPS_CameraReady.pdf)

Contract schema: [`schemas/interoperability_contract.schema.json`](../schemas/interoperability_contract.schema.json)

First gate implementation: [`eval_pipeline/handoff_gate.py`](../eval_pipeline/handoff_gate.py)

Reusable MI boundary gate: [`eval_pipeline/mi_boundary_gate.py`](../eval_pipeline/mi_boundary_gate.py)

MI contract registry: [`eval_pipeline/mi_contract_registry.py`](../eval_pipeline/mi_contract_registry.py)

Schema versioning policy: [`docs/schema-versioning-policy.md`](schema-versioning-policy.md)

Evidence object model and validator: [`eval_pipeline/evidence.py`](../eval_pipeline/evidence.py)

Production evidence registry binding: [`eval_pipeline/evidence.py`](../eval_pipeline/evidence.py)

Human review queue stub: [`eval_pipeline/human_review_queue.py`](../eval_pipeline/human_review_queue.py)

Per-message handoff AIx: [`eval_pipeline/handoff_aix.py`](../eval_pipeline/handoff_aix.py)

Workflow/global AIx aggregation: [`eval_pipeline/workflow_aix.py`](../eval_pipeline/workflow_aix.py)

Connectivity-aware risk scaling: [`eval_pipeline/connectivity_risk.py`](../eval_pipeline/connectivity_risk.py)

Propagated-risk tracker: [`eval_pipeline/propagated_risk.py`](../eval_pipeline/propagated_risk.py)

Shared correction policy: [`eval_pipeline/shared_correction.py`](../eval_pipeline/shared_correction.py)

Correction execution loop: [`eval_pipeline/correction_execution.py`](../eval_pipeline/correction_execution.py)

Redacted MI audit JSONL: [`eval_pipeline/mi_audit.py`](../eval_pipeline/mi_audit.py)

MI audit integrity manifest: [`eval_pipeline/mi_audit_integrity.py`](../eval_pipeline/mi_audit_integrity.py)

MI benchmark suite: [`eval_pipeline/mi_benchmark.py`](../eval_pipeline/mi_benchmark.py)

Reproducible MI benchmark artifacts:
[`eval_outputs/mi_benchmark/mi_benchmark_workflows.json`](../eval_outputs/mi_benchmark/mi_benchmark_workflows.json),
[`eval_outputs/mi_benchmark/mi_benchmark_report.json`](../eval_outputs/mi_benchmark/mi_benchmark_report.json)

MI observability dashboard:
[`eval_outputs/mi_benchmark/mi_observability_dashboard.json`](../eval_outputs/mi_benchmark/mi_observability_dashboard.json)

Research/citation MI pilot: [`eval_pipeline/mi_pilot.py`](../eval_pipeline/mi_pilot.py)

Working MI pilot artifacts:
[`eval_outputs/mi_pilot/research_citation/pilot_result.json`](../eval_outputs/mi_pilot/research_citation/pilot_result.json),
[`eval_outputs/mi_pilot/research_citation/pilot_handoffs.json`](../eval_outputs/mi_pilot/research_citation/pilot_handoffs.json),
[`eval_outputs/mi_pilot/research_citation/mi_audit.jsonl`](../eval_outputs/mi_pilot/research_citation/mi_audit.jsonl),
[`eval_outputs/mi_pilot/research_citation/mi_dashboard.json`](../eval_outputs/mi_pilot/research_citation/mi_dashboard.json)

Production MI readiness gate: [`eval_pipeline/production_readiness.py`](../eval_pipeline/production_readiness.py)

Production MI release checklist: [`docs/production-mi-release-checklist.md`](production-mi-release-checklist.md)

Pilot production-readiness decision:
[`eval_outputs/mi_pilot/research_citation/production_mi_readiness.json`](../eval_outputs/mi_pilot/research_citation/production_mi_readiness.json)

CI MI contract validator: [`scripts/validate_mi_contracts.py`](../scripts/validate_mi_contracts.py)

Release adapter MI integration: [`eval_pipeline/release_adapter_integration.py`](../eval_pipeline/release_adapter_integration.py)

Pre-execution hook: [`eval_pipeline/pre_execution_hook.py`](../eval_pipeline/pre_execution_hook.py)

## Purpose

This brief converts the paper's mechanistic interoperability framing into AANA platform terms. It is the concept layer for later implementation work on interoperability contracts, MI boundary gates, handoff-level AIx scoring, propagated-error tracking, and global workflow alignment.

The operational claim is:

> Mechanistic interoperability is not enough when agents can exchange syntactically valid messages that propagate factual error, unsafe instruction, hidden assumptions, or misclassified constraints.

For AANA, interoperability should mean more than schema compatibility. A handoff should be accepted only when the exchanged message is compatible with the recipient's constraints and the available evidence.

## Paper Concept To Platform Term

| Paper concept | Platform term | AANA surface |
| --- | --- | --- |
| Multi-agent system `S = {S_1, ..., S_N}` | Agent network or workflow graph | Agent Event Contract, Workflow Contract, batch workflow checks |
| Agent `S_i` | Agent, tool, connector, plugin, workflow step, or app component that proposes or consumes an answer/action | `agent`, `adapter_id`, `workflow_id`, connector manifest, domain adapter |
| Output `y_i(t)` | Candidate message, answer, action, tool payload, workflow output, or handoff content | `candidate_action`, `candidate_answer`, `draft_response`, `candidate`, `output` |
| Admissible input space `Y_j` | Recipient schema and accepted input shape | JSON schema, adapter request shape, tool API schema, allowed action list |
| Mechanistic interoperability | Schema-valid handoff | Contract validation before semantic checks |
| Constraint-coherent interoperability | Recipient-relative AANA pass | `gate_decision: pass`, `recommended_action: accept`, no AIx hard blockers |
| Recipient feasible region `F_j = K_P,j ∩ K_B,j ∩ K_C,j` | Recipient constraint profile | Adapter hard constraints, soft constraints, policy preset, evidence registry requirements |
| Influence weight `kappa_ji` | Handoff impact or blast-radius weight | Risk tier, beta, workflow criticality, irreversible-action marker |
| Effective misclassification `epsilon_i_eff` | Local risk plus propagated upstream uncertainty or violation | Candidate AIx, propagated assumption tags, violation ancestry |
| Shared correction mechanism | Network-level AANA gate and correction policy | MI boundary gate, batch workflow result, global workflow decision |
| `C_global >= D_global` | Correction capacity must scale with connectivity and risk | Connectivity-aware thresholds, stronger evidence requirements, defer/human-review routing |

## Platform Definitions

### Agent

An agent is any platform actor that can produce, transform, route, or execute a candidate answer/action. This includes:

- LLM agents and coding agents.
- Tool wrappers and runtime connectors.
- OpenClaw/Codex skills or plugins.
- Workflow steps in a batch contract.
- External apps that call the AANA HTTP bridge.

An agent does not need autonomy to matter for MI. If it can pass a message into another component that will trust or act on it, it participates in the agent network.

### Message

A message is the proposed content crossing a boundary. It may be:

- A natural-language answer.
- A draft email, chat message, support reply, memo, or summary.
- A tool call payload.
- A planned file operation, commit, deployment, booking, purchase, access change, or data export.
- A normalized evidence summary.
- A workflow result consumed by a downstream step.

For AANA, a message should be treated as a candidate until it passes the relevant gate. A schema-valid message is not automatically an aligned message.

### Handoff

A handoff is a directed edge from a sender to a recipient:

```text
sender -> recipient: message
```

Examples:

- Agent drafts an email -> email-send connector.
- Research agent produces a claim summary -> publication checker.
- Code agent prepares a diff -> CI/release checker.
- Support assistant proposes a refund promise -> CRM/support adapter.
- Calendar planner proposes a meeting time -> calendar connector.

Every consequential handoff should be reviewable as either an Agent Event or a Workflow Contract item. Low-risk internal transformations can remain implementation details, but anything sent, written, published, committed, deployed, shared, booked, purchased, exported, or permission-changing should cross an AANA gate.

### Recipient Constraint

A recipient constraint is a rule that must hold before the recipient can safely consume or execute the message. It is recipient-relative, not sender-relative:

```text
F_recipient = K_P,recipient ∩ K_B,recipient ∩ K_C,recipient
```

Use the existing AANA layers:

- `K_P`: factual, physical, numerical, feasibility, provenance, evidence, system-state, and resource constraints.
- `K_B`: human-impact, safety, privacy, manipulation, consent, cognitive-load, welfare, and over-compliance constraints.
- `K_C`: task, policy, schema, role, authorization, domain, format, workflow, and business-rule constraints.
- `F`: feedback integrity, calibration, evidence freshness, source trust, and uncertainty labeling.

Recipient constraints should come from domain adapters, policy presets, connector manifests, evidence registry entries, and workflow metadata. They should not be inferred only from the sender's prompt.

### Evidence

Evidence is the grounding object used to decide whether a message should pass. AANA already supports structured evidence objects:

```json
{
  "source_id": "crm-record",
  "retrieved_at": "2026-05-05T00:00:00Z",
  "trust_tier": "verified",
  "redaction_status": "redacted",
  "text": "Refund eligibility is unknown."
}
```

For MI, evidence must also support handoff review:

- `source_id`: where the relevant fact came from.
- `retrieved_at`: freshness for the recipient's decision.
- `trust_tier`: whether the recipient should rely on it.
- `redaction_status`: whether it is safe to pass across this boundary.
- `citation_url` or `retrieval_url`: provenance link for the cited source or retrieval record.
- `metadata.integration_id`: connector family, when available.
- `metadata.source_mode`: live, approved production fixture, or repository fixture, when available.
- optional `supports`: message claims or fields supported by this evidence.
- optional `limits`: claims, actions, or assumptions this evidence does not support.

Missing, stale, untrusted, unredacted, or incompatible evidence should route to `retrieve`, `ask`, or `defer`, not direct `accept`.

### Correction

Correction is the platform's ability to keep a handoff inside the recipient feasible region. It includes:

- `revise`: repair unsupported wording, unsafe promises, bad formatting, invalid payloads, or overclaims.
- `retrieve`: fetch stronger, fresher, or more complete evidence.
- `ask`: request missing user/domain information.
- `refuse`: stop a prohibited or unsafe request.
- `defer`: route to human review, stronger authorization, or a domain-owned process.
- `accept`: pass only after the candidate and final output satisfy the gate.

MI correction is network-aware. A downstream gate should be able to identify that an upstream message carried an unsupported assumption and route correction back to the right boundary.

### Gate

A gate is the decision boundary applied before a message is consumed or acted on. In current AANA terms, a direct pass requires:

```text
gate_decision == "pass"
recommended_action == "accept"
aix.decision == "accept"
aix.hard_blockers is empty
```

For MI, a gate should evaluate:

- Sender and recipient identity.
- Message schema and allowed action.
- Recipient constraints.
- Available evidence and provenance.
- Candidate AIx and final AIx.
- Hard blockers and violation codes.
- Propagated assumptions from upstream handoffs.
- Propagated risk: hidden assumptions, unsupported claims, stale evidence, accepted violations, and downstream premise adoption.
- Risk tier, beta, and workflow connectivity.

The gate output should preserve the existing public decision vocabulary: `accept`, `revise`, `retrieve`, `ask`, `refuse`, or `defer`.

## AANA MI Boundary Model

The first platform model should treat each handoff as a small AANA event:

```text
handoff_event = {
  sender,
  recipient,
  message,
  recipient_constraints,
  evidence,
  allowed_actions,
  metadata
}
```

The gate loop is:

```text
1. Validate handoff shape.
2. Resolve recipient constraint profile.
3. Normalize and validate evidence.
4. Score candidate message with P/B/C/F verifiers.
5. Apply AIx beta and thresholds for risk/connectivity.
6. Select accept/revise/retrieve/ask/refuse/defer.
7. Emit redacted audit metadata.
8. Pass only accepted final output to the recipient.
```

This model can be implemented on top of the current Agent Event and Workflow Contract surfaces before introducing a dedicated MI contract.

## Connectivity-Aware Risk Scaling

The paper principle `C_global >= D_global` becomes a runtime rule: as workflow connectivity, downstream blast radius, or irreversibility rises, AANA must increase correction capacity and verifier strictness before allowing direct acceptance.

| MI risk tier | Workflow condition | Accept threshold | Drift threshold | Beta | Required correction capacity |
| --- | --- | ---: | ---: | ---: | ---: |
| low | connectivity 0-1, reversible | 0.85 | 0.100 | 1.00 | 1 |
| elevated | connectivity 2-3 | 0.90 | 0.075 | 1.15 | 2 |
| high | connectivity 4-5 | 0.93 | 0.050 | 1.35 | 3 |
| strict | connectivity 6+, irreversible, or declared strict | 0.96 | 0.025 | 1.60 | 4 |

Runtime output should include `connectivity_risk` with the selected tier, inferred and declared tiers, maximum connectivity, total connectivity, reversibility flag, stricter thresholds, beta, observed correction capacity, required correction capacity, and capacity gap. If observed correction capacity is below the selected tier requirement, workflow AIx should route to `defer` and mark `insufficient_correction_capacity`.

## Shared Correction Layer

AANA MI correction is network-level. A downstream recipient should be able to trigger correction on the boundary that introduced the risk instead of only rejecting its own local input.

The shared correction policy emits correction intents:

| Trigger | Correction action | Target |
| --- | --- | --- |
| stale or missing evidence | `retrieve_evidence` | evidence source or handoff that needs grounding |
| unsupported claim or accepted violation | `revise_upstream_output` | upstream handoff producer |
| unknown assumption | `ask_clarification` | sender, user, domain owner, or evidence owner |
| insufficient correction capacity, strict irreversible workflow, or unresolved network risk | `defer_human_review` | workflow-level human review queue |

Policy output should include `shared_correction.actions[]` with `target_handoff_id`, `requested_by_handoff_id`, target and requesting agent IDs when available, reason, severity, source, network scope, and pending status. The policy plans correction; execution remains with workflow orchestration, retrieval connectors, upstream agents, or human review systems.

## Redacted MI Audit Logs

Each MI handoff decision should produce one JSONL audit row with redacted decision metadata only. The row must preserve sender, recipient, boundary type, gate decision, recommended action, AIx summary, handoff AIx summary, hard blockers, violation codes, and fingerprints. It must not store raw message payloads, raw message summaries, claims, assumptions, evidence text, or private records.

The JSONL row shape is:

```json
{
  "mi_audit_record_version": "0.1",
  "record_type": "mi_handoff_decision",
  "handoff_id": "support-agent-to-email-send-001",
  "sender": {"id": "support_agent", "type": "agent"},
  "recipient": {"id": "email_send_guardrail", "type": "adapter"},
  "gate_decision": "block",
  "recommended_action": "revise",
  "aix": {"score": 0.31, "decision": "refuse", "hard_blockers": []},
  "handoff_aix": {"score": 0.31, "decision": "refuse", "hard_blockers": []},
  "violation_codes": ["unsupported-refund-promise"],
  "fingerprints": {
    "message": "sha256...",
    "evidence": ["sha256..."],
    "audit_summary": "sha256..."
  }
}
```

The implementation emits `mi_audit_records[]` from `mi_boundary_batch(...)` and supports appending those rows to JSONL with `append_mi_audit_jsonl(...)`.

## MI Benchmark Suite

The benchmark suite uses deterministic handoff workflows where schema-valid messages can still propagate unsupported claims, unknown assumptions, boundary mismatches, missing evidence, or irreversible-capacity gaps.

It compares four modes:

| Mode | What it checks |
| --- | --- |
| `schema_only_interoperability` | Required MI handoff shape and endpoint/message/evidence container types. |
| `local_aana_gate` | Per-handoff recipient constraints, evidence presence, verifier scores, and local AIx. |
| `mi_boundary_gate` | Local AANA plus sender/recipient boundary compatibility. |
| `full_global_aana_gate` | Boundary gates plus workflow AIx, propagated-risk tracking, connectivity-aware risk scaling, shared correction, and MI audit rows. |

The reproducible fixture is `eval_outputs/mi_benchmark/mi_benchmark_workflows.json`; the generated comparison report is `eval_outputs/mi_benchmark/mi_benchmark_report.json`. The initial report demonstrates why MI needs the global layer: schema-only accepts all schema-valid propagation failures, local gates catch only local evidence failures, boundary gates catch boundary mismatch, and the full global gate catches propagated premise risk plus strict workflow correction-capacity gaps.

## Dashboard And Metrics

The MI observability dashboard summarizes full-global MI outcomes into dashboard-ready panels:

| Metric | Definition |
| --- | --- |
| handoff pass/fail rate | pass/block/fail counts from MI boundary gate decisions across benchmark handoffs |
| propagated error rate | workflows with propagated-risk entries divided by total workflows |
| correction success rate | expected-risk workflows detected by the global gate and routed to shared correction |
| false accept rate | expected-risk workflows not detected by the global gate |
| false refusal rate | clean workflows incorrectly detected by the global gate |
| global AIx drift | average/min workflow score delta, max drop, and drift-detected count |

The generated dashboard payload is `eval_outputs/mi_benchmark/mi_observability_dashboard.json`.

## Pilot Integration

The first working MI pilot applies the boundary gate, propagated-risk tracker, shared correction policy, audit logger, and dashboard metrics to the real repository workflow fixture at [`examples/workflow_research_summary_structured.json`](../examples/workflow_research_summary_structured.json).

This pilot uses the research/citation workflow because it exercises a high-value MI failure mode: one agent can turn a partly supported retrieval result into an overclaim, and a downstream publication step can accidentally treat that uncertain output as a premise. The pilot maps the fixture into three handoffs:

- `retrieval-to-research-agent`: tool-to-agent evidence transfer.
- `research-agent-to-citation-guard`: agent-to-agent claim review.
- `publication-agent-to-publication-check`: agent-to-tool publication readiness check.

The pilot deliberately includes an unsupported productivity claim and a downstream dependency on that claim. The expected platform behavior is `revise`, not `accept`: the downstream publication step should be routed back through shared correction to repair the upstream research summary before publication.

## Production Readiness Gate

High-risk actions must run MI before direct execution. A high-risk action includes any send, publish, deploy, booking, purchase, export, delete, permission change, code release, external connector call, or other consequential action that is hard to undo.

The production readiness gate blocks direct execution when:

- MI checks are missing.
- Any consequential handoff is missing evidence metadata.
- Local or global AIx hard blockers exist.
- Global AIx is below the active accept threshold for the workflow risk tier.
- Propagated assumptions, unsupported claims, stale evidence, or downstream premise links remain unresolved.

The release artifact is [`docs/production-mi-release-checklist.md`](production-mi-release-checklist.md). The callable gate is `production_mi_readiness_gate(...)`, which accepts a `mi_boundary_batch(...)` result or a pilot result containing `mi_batch` and returns `release_status`, `can_execute_directly`, `blockers`, `recommended_action`, and checklist rows.

## CI Contract Enforcement

MI contract drift should fail before release. The CI validator checks:

- `schemas/interoperability_contract.schema.json` against the Draft 2020-12 metaschema.
- `eval_outputs/mi_pilot/research_citation/pilot_handoffs.json` by validating every handoff against the interoperability schema.
- `eval_outputs/mi_pilot/research_citation/mi_audit.jsonl` with the redacted MI audit validator.
- `eval_outputs/mi_pilot/research_citation/mi_dashboard.json` for dashboard version, panels, workflow rows, and required metrics.
- `eval_outputs/mi_pilot/research_citation/production_mi_readiness.json` for readiness version, gate, status, checklist, blockers, global AIx, and propagated-risk summary.

Run it with:

```bash
python scripts/validate_mi_contracts.py
```

or, after installing the package:

```bash
aana-validate-mi-contracts
```

## Release Adapter Integration

The first high-risk adapter integration attaches `production_mi_readiness_gate(...)` to the `deployment_readiness` release adapter. This separates answer correctness from execution authorization: a deployment review can produce a safe recommendation while still blocking the actual production deployment action.

The integration adds these fields to deployment workflow results:

- `production_mi_batch`: the MI batch used for pre-execution readiness.
- `production_mi_readiness`: the production readiness decision.
- `direct_execution_allowed`: boolean execution authorization.
- `direct_execution_blockers`: blocker IDs that must be resolved before deployment.

Direct adapter runs without workflow evidence remain blocked even when the candidate text is clean. Workflow-contract runs can allow direct execution only when the deployment candidate passes the adapter, carries evidence, has no hard blockers, meets the high-risk global AIx threshold, and has no unresolved propagation.

## Mapping To Existing Contracts

### Agent Event Contract

Use the Agent Event Contract when a single agent is about to perform or delegate a consequential action.

Initial MI field mapping:

| MI field | Agent Event field |
| --- | --- |
| sender | `agent` |
| recipient | `adapter_id` or `metadata.recipient` |
| message | `candidate_action`, `candidate_answer`, or `draft_response` |
| recipient constraints | adapter constraints plus `metadata.policy_preset` |
| evidence | `available_evidence` |
| action vocabulary | `allowed_actions` |
| gate output | `gate_decision`, `recommended_action`, `aix`, `candidate_aix`, `violations`, `audit_summary` |

### Workflow Contract

Use the Workflow Contract when checking a complete app/workflow step or batch of steps.

Initial MI field mapping:

| MI field | Workflow field |
| --- | --- |
| sender | `metadata.sender`, future `handoff.sender` |
| recipient | `adapter`, `workflow_id`, or future `handoff.recipient` |
| message | `candidate` |
| recipient constraints | `constraints` plus adapter/domain constraints |
| evidence | `evidence` |
| action vocabulary | `allowed_actions` |
| gate output | `gate_decision`, `recommended_action`, `aix`, `candidate_aix`, `violations`, `audit_summary` |

Batch workflows are the natural place to compute early `global_aix`, because each item can expose local decisions while the batch result can track aggregate drift.

## Design Rules

1. Treat schema validity as necessary but insufficient.
2. Evaluate every consequential handoff against the recipient's constraints, not only the sender's intent.
3. Require structured evidence for high-risk or cross-system handoffs.
4. Preserve uncertainty and unsupported assumptions as metadata instead of letting them become hidden premises.
5. Use stricter thresholds when connectivity, irreversibility, privacy risk, or downstream blast radius increases.
6. Keep AIx as a decision surface and hard blockers as hard gates.
7. Store only redacted decision metadata in MI audit logs.
8. Route to `retrieve`, `ask`, or `defer` when the system lacks the evidence or authority to decide.
9. Avoid presenting MI gates as a perfect alignment guarantee; they make correction capacity explicit and inspectable.

## Candidate Handoff Metadata

The canonical milestone 2 schema is [`schemas/interoperability_contract.schema.json`](../schemas/interoperability_contract.schema.json). The example below shows the same shape in compact form:

```json
{
  "mi_version": "0.1-draft",
  "handoff_id": "support-agent-to-email-send-001",
  "sender": {
    "id": "support_agent",
    "type": "agent"
  },
  "recipient": {
    "id": "email_send_guardrail",
    "type": "adapter"
  },
  "message": {
    "kind": "candidate_action",
    "summary": "Draft email would promise a full refund."
  },
  "recipient_constraints": {
    "K_P": ["Refund eligibility must be supported by verified account evidence."],
    "K_B": ["Do not mislead the customer or expose private account details."],
    "K_C": ["Do not send refund promises without policy eligibility."]
  },
  "evidence": [
    {
      "source_id": "crm-record",
      "retrieved_at": "2026-05-05T00:00:00Z",
      "trust_tier": "verified",
      "redaction_status": "redacted",
      "text": "Refund eligibility is unknown."
    }
  ],
  "allowed_actions": ["accept", "revise", "retrieve", "ask", "defer", "refuse"],
  "metadata": {
    "risk_tier": "high",
    "connectivity": 2,
    "irreversible_action": false,
    "requires_redacted_audit": true
  }
}
```

## Open Questions For Milestone 2

- Should MI get a dedicated `interoperability_contract.schema.json`, or should v1 extend Agent Event and Workflow Contract metadata first?
- Which handoffs require structured evidence by default?
- How should `global_aix` aggregate local candidate/final AIx without hiding hard blockers?
- What is the minimal propagated-assumption format needed to trace upstream unsupported claims?
- Which connector families should be first-class MI recipients in the pilot: support/email, code/release, files, research, or calendar?

## Milestone 1 Completion Criteria

- Paper MI terms are mapped into AANA platform vocabulary.
- Agent, message, handoff, recipient constraint, evidence, correction, and gate are defined.
- Existing Agent Event and Workflow Contract surfaces are identified as the first implementation path.
- The next milestone can start from this brief to define a structured interoperability contract.
