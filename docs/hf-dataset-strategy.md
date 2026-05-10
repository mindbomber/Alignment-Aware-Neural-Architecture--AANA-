# Hugging Face Dataset Strategy

AANA should use Hugging Face datasets as calibration and validation evidence for the architecture's control layer, not as a way to fit public benchmarks. The strategic goal is to make adapter families more reliable at auditability, control, verification, correction, privacy, groundedness, and route quality.

## Primary Uses

- Calibrate thresholds for verifier scores, AIx routing, and adapter-specific ask/defer/refuse boundaries.
- Reduce false positives and over-refusals while preserving recall on unsafe, unsupported, private, or unauthorized actions.
- Test held-out generalization after adapter improvements.
- Prove adapter-family readiness with external held-out evidence before stronger public claims.

## Target Capabilities

- Privacy/PII recall and redaction routing.
- Grounded QA hallucination and unsupported-claim detection.
- Unsafe tool-call gating.
- Authorization-state detection.
- Public-read versus private-read classification.
- Ask, defer, and refuse route quality.

## Current Dataset Mapping

- Privacy/PII: PIIMB, OpenPII, and Nemotron-PII.
- Grounded QA: RAG-Grounded-QA and HaluBench-style schemas.
- Agent tool-use: Qwen tool trajectories, Hermes function calling, MCP-Atlas, and MCPHunt traces.

## Operating Rules

- Never use the same dataset/config/split for calibration and public claims.
- Never reuse the same dataset/config/split across calibration,
  heldout_validation, and external_reporting roles.
- Treat calibration splits as engineering data, not external proof.
- Treat held-out validation as adapter-family evidence only after the adapter is frozen for that run.
- Treat external-reporting splits as public claim evidence only when no tuning was performed on that split.
- Report false positives, safe allow rate, schema failures, and route accuracy alongside recall.
- `python scripts/hf/validate_hf_dataset_proof.py --require-existing-artifacts`
  fails CI when a public proof axis references a split registered for
  calibration or an unregistered split.

## Governance/Compliance TODO

Governance/compliance coverage is currently repo-heldout fixture based. The
tracked TODO in `examples/hf_dataset_validation_registry.json` requires a
Hugging Face dataset search for policy, auditability, risk-control, or
regulatory-decision datasets before stronger governance/compliance public
claims are made.

## Calibration Gate

`examples/hf_calibration_plan.json` is the calibration control plane. It requires separate calibration and reporting sources for privacy, grounded QA, tool-use, finance, legal, pharma, devops, and support. Each family must track the same five promotion metrics:

- `safe_allow_rate`
- `false_positive_rate`
- `unsafe_recall`
- `route_quality`
- `schema_failure_rate`

The validator blocks two failure modes:

- A family missing from calibration governance.
- Any dataset/config/split reused across calibration and reporting for that family.

Run it with:

```bash
python scripts/hf/validate_hf_calibration.py
```

This gate is intentionally conservative. A calibration split can reduce false positives and tune thresholds, but it cannot become public evidence for a stronger claim. Reporting splits stay held out until the adapter is frozen for that run.

## Next Execution Order

1. Privacy/PII: expand multilingual and regulated-domain recall, then tune false-positive control.
2. Grounded QA: calibrate unsupported-claim recall against answerable safe allow rate.
3. Agent tool-use: improve authorization-state and public/private read classification.
4. Cross-family validation: rerun each family on at least one external held-out split before updating public claims.
