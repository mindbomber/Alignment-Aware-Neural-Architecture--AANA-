# AANA + MLCommons Integration Brief

## Purpose

AANA can complement MLCommons benchmark work by turning benchmark artifacts into
deployment-facing governance evidence. MLCommons evaluates model and system
behavior. AANA consumes those artifacts, maps them into AIx audit signals, and
produces runtime governance outputs: component scores, hard blockers, evidence
gaps, remediation actions, human-review requirements, monitoring signals, and a
conservative deployment-readiness recommendation.

This brief is intended for MLCommons follow-up conversations. It does not claim
that AANA is an MLCommons certification product or that an MLCommons benchmark
pass is sufficient for regulated deployment.

## Proposed Collaboration

The near-term collaboration should be narrow and artifact-driven:

1. Confirm the most useful MLCommons output artifact shape for AANA to ingest.
2. Add that artifact shape as a compatibility fixture in AANA.
3. Validate AANA's importer against the real schema.
4. Generate an AIx Report from the artifact.
5. Review whether the report is useful to MLCommons users evaluating regulated
   or high-risk AI systems.

The first requested input from MLCommons is one representative AILuminate or
ModelBench output artifact, with any private data removed.

## What AANA Adds

AANA adds the governance layer around benchmark evidence:

- Normalized AIx score and component scores for `P`, `B`, `C`, and `F`.
- Hazard and violation mapping into deployment-facing risk categories.
- Hard-blocker detection for issues that should prevent direct deployment.
- Evidence quality and coverage checks.
- Human-review and remediation guidance.
- Redacted audit artifacts suitable for compliance review.
- Runtime sidecar patterns for pre-deployment and shadow-mode evaluation.

In short:

```text
MLCommons provides benchmark evidence.
AANA turns that evidence into audit-ready deployment governance.
```

## Current AANA Support

| MLCommons surface | AANA integration | Current status |
| --- | --- | --- |
| AILuminate | Import scored hazard results and generate AIx Reports. | `mlcommons-aix-report` CLI and FastAPI route |
| ModelBench / ModelGauge | Ingest hazard-scored result journals and produce deployment-facing audit reports. | JSON, JSONL, and JSONL Zstandard journal support |
| MLCommons Inference Endpoints | Run AANA as a sidecar/proxy around endpoint benchmark or pre-deployment tests. | Endpoint precheck contract and sidecar docs |
| MedPerf | Apply a strict healthcare AIx profile around federated medical AI evaluation evidence. | Healthcare profile and report section |
| Croissant / BioCroissant | Convert dataset metadata into AANA evidence registry entries. | Croissant evidence importer |
| DataPerf / Dynabench | Wrap dataset quality and benchmark coverage evidence into audit signals. | Audit wrapper CLI |
| MLCFlow / MLPerf Automations | Run AANA as a workflow step after benchmark execution. | Automation-step CLI and manifest |

## Example Workflow

```text
Run MLCommons benchmark
  -> collect AILuminate or ModelBench output artifact
  -> run AANA mlcommons-aix-report
  -> normalize benchmark evidence
  -> compute AIx score and component scores
  -> detect hard blockers and evidence gaps
  -> generate JSON + Markdown AIx Report
  -> optionally fail a workflow step when hard blockers exist
```

Example command:

```powershell
python scripts/aana_cli.py mlcommons-aix-report `
  --results examples/mlcommons_modelbench_journal_actual.jsonl `
  --source-type modelbench `
  --output-dir eval_outputs/mlcommons_aix/modelbench `
  --json
```

## Buyer-Facing Output

The generated AIx Report includes:

- executive summary
- deployment recommendation
- overall AIx score
- `P`, `B`, `C`, and `F` component scores
- mapped MLCommons hazards
- hard blockers
- evidence quality
- verifier coverage
- calibration confidence
- remediation plan
- human-review requirements
- monitoring plan
- limitations and claim boundary
- audit metadata

Recommendation labels remain conservative:

- `pilot_ready`
- `pilot_ready_with_controls`
- `not_pilot_ready`
- `insufficient_evidence`

Every report states that pilot readiness is not production certification.

## Regulated-Industry Fit

AANA is most useful where benchmark results need to become reviewable deployment
evidence for regulated or high-risk workflows:

- healthcare and medical AI evaluation
- financial services operations
- insurance claims and underwriting support
- employment or HR decision support
- legal, compliance, and government workflows
- customer support systems that can expose private data or take irreversible
  account actions

For regulated deployment, benchmark evidence is necessary but not sufficient.
AANA still expects live connector evidence, domain-owner signoff, durable audit
retention, security review, human-review operations, incident response, and
measured shadow-mode results.

## What We Need From MLCommons

The most useful next artifact is:

```text
One representative AILuminate or ModelBench output file that reflects the actual
schema users receive after a benchmark run. Synthetic, redacted, or minimal data
is fine as long as the field names, nesting, hazard identifiers, score semantics,
and metadata match the real output shape.
```

Useful fields include:

- benchmark name and version
- system-under-test identifier
- model or endpoint metadata
- hazard identifiers and names
- per-hazard scores or grades
- sample counts
- references or thresholds
- timestamps or run metadata
- any result status or pass/fail fields
- output format description if the file is compressed, streamed, or journaled

## Proposed Ask

Suggested message:

```text
We have built an AANA AIx importer for AILuminate and ModelBench-style artifacts
that generates deployment-facing audit reports with AIx scores, hard blockers,
evidence gaps, remediation guidance, and conservative pilot-readiness labels.

Could you share one representative redacted or synthetic output artifact from an
AILuminate or ModelBench run so we can tighten compatibility around the actual
schema? We are not asking for private benchmark data. We only need the real file
shape, field names, score semantics, and metadata structure.

Our goal is to make AANA consume MLCommons benchmark evidence cleanly and return
regulated-deployment governance artifacts without claiming MLCommons
certification or production approval.
```

## Claim Boundary

AANA should be positioned as an audit and runtime governance layer around
MLCommons evidence, not as a replacement for MLCommons benchmarks or as an
official MLCommons certification.

Acceptable claim:

```text
AANA consumes MLCommons benchmark artifacts and produces deployment-facing AIx
audit reports, hard-blocker checks, evidence-gap analysis, and runtime
governance recommendations.
```

Avoid:

```text
AANA certifies MLCommons benchmark compliance.
AANA proves regulated deployment readiness from benchmark results alone.
AANA replaces AILuminate, ModelBench, MedPerf, or other MLCommons evaluations.
```

## Repo References

- Full integration docs: `docs/mlcommons-aix-integration.md`
- Endpoint sidecar pattern: `docs/mlcommons-endpoint-sidecar.md`
- Croissant evidence importer: `docs/croissant-evidence-import.md`
- MedPerf healthcare profile: `docs/medperf-aix-profile.md`
- MLCFlow automation step: `docs/mlcflow-aana-step.md`
- DataPerf/Dynabench audit wrapper: `docs/dataperf-dynabench-audit.md`
- CLI entry point: `scripts/aana_cli.py`
- Core MLCommons importer: `eval_pipeline/mlcommons_aix.py`
