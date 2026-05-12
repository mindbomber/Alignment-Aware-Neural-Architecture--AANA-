# AANA MLCommons AIx Integration

For a shorter follow-up packet intended for MLCommons conversations, see
`docs/aana-mlcommons-integration-brief.md`.

AANA can sit beside MLCommons benchmark infrastructure as the audit and
deployment-governance layer. MLCommons benchmark outputs describe how a system
performed against a benchmark. AANA converts that evidence into an AIx report:
component scores, hard blockers, evidence quality, remediation, human-review
requirements, monitoring, and a conservative deployment recommendation.

This is production-candidate evidence only. It is not production certification
or go-live approval for regulated industries.

## Priority Surfaces

| MLCommons surface | AANA role | Build status |
| --- | --- | --- |
| AILuminate | Import hazard-level risk benchmark results and generate AIx Reports. | `mlcommons-aix-report` CLI and FastAPI route |
| ModelBench / ModelGauge | Ingest hazard-scored result journals and produce deployment-facing audit reports. | `modelbench` source type |
| Inference Endpoints | Run AANA as a sidecar/proxy around endpoint benchmarking and pre-deployment tests. | deployment pattern defined |
| MedPerf | Add healthcare-specific governance reporting around federated medical AI evaluation. | regulated profile defined |
| Croissant / BioCroissant | Use dataset metadata as evidence registry input for provenance, license, and sensitive-field checks. | profile hook defined |
| MLCFlow / MLPerf Automations | Run benchmark, then run AANA AIx audit as an automation step. | CLI command available |
| Dynabench / DataPerf | Wrap dynamic benchmark and data-quality evidence into readiness reports. | `dataperf-dynabench-audit` CLI |

## CLI

Generate an AIx report from an AILuminate-style result artifact:

```powershell
python scripts/aana_cli.py mlcommons-aix-report `
  --results examples/mlcommons_ailuminate_results.json `
  --source-type ailuminate `
  --output-dir eval_outputs/mlcommons_aix/ailuminate `
  --json
```

Generate from a ModelBench-style journal sample:

```powershell
python scripts/aana_cli.py mlcommons-aix-report `
  --results examples/mlcommons_modelbench_journal_actual.jsonl `
  --source-type modelbench `
  --output-dir eval_outputs/mlcommons_aix/modelbench `
  --json
```

The importer also accepts ModelBench `journal.jsonl.zst` files. It reads the
actual public journal event shape where hazard scores are JSONL entries with:

```json
{
  "message": "hazard scored",
  "benchmark": "...",
  "sut": "...",
  "hazard": "prv",
  "hazard_key": "safe_hazard-1_1-prv",
  "score": 0.006,
  "reference": 0.02,
  "samples": 120,
  "numeric_grade": 4,
  "text_grade": "A"
}
```

For ModelBench, AANA treats `score` as the unsafe fraction documented by the
public runner and converts it into an AIx safety score with
`aix_hazard_score = 1 - score`.

The AILuminate public repo currently exposes prompt-set CSV artifacts with the
documented fields `Release_prompt_id`, `Prompt_text`, `Hazard`, `Persona`,
`Locale`, and `Prompt_hash`. AANA can import that CSV shape as coverage
metadata, but it reports `insufficient_evidence` until scored ModelBench or
AILuminate result evidence is supplied.

Write the default profile:

```powershell
python scripts/aana_cli.py mlcommons-aix-report --write-default-profile --profile examples/mlcommons_aix_profile.json
```

## FastAPI

The packaged runtime exposes:

```text
POST /mlcommons-aix-report
```

Example body:

```json
{
  "results_path": "examples/mlcommons_ailuminate_results.json",
  "source_type": "ailuminate",
  "profile_path": "examples/mlcommons_aix_profile.json",
  "output_dir": "eval_outputs/mlcommons_aix/fastapi"
}
```

The route requires the `mlcommons_aix_report` token scope.

## Endpoint Sidecar Pattern

For MLCommons endpoint benchmarking, AANA can run as a sidecar/proxy around the
system-under-test endpoint. This lets teams capture governance checks,
redacted endpoint precheck metadata, and latency/throughput impact without
modifying the MLCommons endpoint runner.

The contract lives at:

```text
examples/mlcommons_endpoint_sidecar_contract.json
```

Validate it with:

```powershell
python scripts/aana_cli.py mlcommons-endpoint-sidecar --json
```

The sidecar uses the `aana.mlcommons_endpoint_precheck.v1` contract and captures
benchmark run metadata, p50/p95 latency overhead, throughput delta, and
fail-closed live endpoint policy. See
`docs/mlcommons-endpoint-sidecar.md` for the full pattern.

## MLCFlow Automation Step

AANA can run as an MLCFlow-style automation step:

```text
run benchmark
  -> collect MLCommons artifact
  -> run AANA mlcommons-aix-report
  -> generate manifest
  -> fail if hard blockers exist
```

Use:

```powershell
python scripts/aana_cli.py mlcflow-aana-step `
  --results examples/mlcommons_modelbench_journal_actual.jsonl `
  --source-type modelbench `
  --json
```

The step writes an `aana-mlcflow-step-manifest.json` with artifact hashes,
deployment recommendation, AIx score, hard blockers, and fail reasons. See
`docs/mlcflow-aana-step.md`.

## DataPerf / Dynabench Audit Wrappers

AANA can also evaluate dataset quality and benchmark coverage evidence for
DataPerf/Dynabench-style workflows:

```powershell
python scripts/aana_cli.py dataperf-dynabench-audit `
  --metadata examples/croissant_metadata_sample.json `
  --benchmark examples/dataperf_dynabench_benchmark_summary.json `
  --json
```

The wrapper reports dataset quality, benchmark coverage, evidence gaps, drift
risk, and a risk-tier recommendation. See
`docs/dataperf-dynabench-audit.md`.

## Output Artifacts

Each run writes:

- `normalized-mlcommons-results.json`
- `mlcommons-aix-report.json`
- `mlcommons-aix-report.md`

The report includes:

- executive summary
- deployment recommendation
- overall AIx
- `P`, `B`, `C`, and `F` component scores
- mapped MLCommons hazards
- hard blockers
- evidence quality
- verifier coverage
- calibration confidence
- remediation plan
- human-review requirements
- monitoring plan
- limitations and production-certification boundary

## Regulated-Industry Positioning

For the MLCommons call, the strongest positioning is:

```text
MLCommons provides benchmark evidence.
AANA turns that evidence into audit-ready deployment governance.
```

The first customer-facing package should be:

```text
AANA AIx Audit for MLCommons-regulated AI evaluations
```

It should not claim that an MLCommons benchmark pass alone means a system is
production-ready. For regulated industries, AANA still requires live connectors,
domain-owner signoff, durable audit retention, security review, human-review
operations, incident response, and measured shadow-mode results.
