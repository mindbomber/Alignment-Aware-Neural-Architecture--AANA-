---
license: mit
tags:
  - agent-control
  - evaluation
  - auditability
  - safety
  - hallucination-detection
  - pii
pretty_name: AANA Control-Layer Evidence Pack
---

# AANA Control-Layer Evidence Pack

This dataset card template describes public AANA validation artifacts used to evaluate AANA as an audit/control/verification/correction layer.

AANA is an architecture for making agents more auditable, safer, more grounded, and more controllable.

## Intended Use

The evidence pack is for:

- Calibration analysis.
- Held-out validation.
- External reporting of measured AANA behavior.
- Reproducible audit/control-layer comparisons.

It is not for training and reporting on the same split. Never use the same split for tuning and public claims.

## Dataset Families

- Privacy and PII routing.
- Grounded QA and hallucination checks.
- Agent tool-use and MCP-style tool calls.
- Cross-domain action gating.
- Customer support, finance, ecommerce/retail, research, and security adapter validation.

## Expected Metrics

- Unsafe-action recall.
- Private-read/write gating quality.
- Unsupported-claim recall.
- PII recall and redaction correctness.
- False positive rate.
- Safe allow rate.
- Ask/defer/refuse route quality.
- Schema failure rate.

## Split Isolation

Public reports must identify whether each split was used for:

- `calibration`
- `heldout_validation`
- `external_reporting`

The same split must not be used for both adapter tuning and public performance claims.

## Current Evidence Boundary

AANA is production-candidate as an audit/control/verification/correction layer.

AANA is not yet proven as a raw agent-performance engine. This dataset card should not be used to imply that AANA alone outperforms base planners on raw task success.

## Related Artifacts

- Public artifact hub: `https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4`
- Public peer-review evidence pack: `https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack`
- Dataset registry: `examples/hf_dataset_validation_registry.json`
- HF dataset proof report: `docs/hf-dataset-proof-report.md`
- Production-candidate evidence pack: `docs/aana-production-candidate-evidence-pack.md`
- Agent Action Contract v1: `docs/agent-action-contract-v1.md`
