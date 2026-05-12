# MLCommons Endpoint Sidecar Pattern

AANA can sit beside MLCommons endpoint benchmarking as a sidecar or proxy. The
goal is to add runtime governance and AIx audit evidence without requiring
changes to the MLCommons endpoint runner.

This is runtime governance evidence only. It is not MLCommons benchmark
certification, production certification, or go-live approval for regulated
industries.

## Placement

```text
MLCommons endpoint runner
  -> AANA sidecar/proxy
  -> system-under-test endpoint
  -> AANA sidecar/proxy records redacted gate and impact metadata
  -> runner receives the endpoint response
```

Recommended modes:

- `observe`: capture benchmark metadata and latency/throughput impact fields.
- `shadow`: run AANA checks and record would-block/would-defer decisions without
  blocking the benchmark.
- `enforce`: fail closed for live endpoint deployment. Use this only after
  benchmark owners and deployment owners approve the policy.

## Endpoint Precheck Contract

The endpoint sidecar uses:

```text
aana.mlcommons_endpoint_precheck.v1
```

Required fields:

- `run_id`
- `endpoint_id`
- `request_id`
- `benchmark`
- `model`
- `input_fingerprint`
- `candidate_output_fingerprint`
- `evidence_refs`
- `runtime_mode`

The sidecar stores fingerprints, IDs, metrics, and governance metadata only. It
must not store raw prompts, raw completions, payloads, headers, credentials,
PHI, PII, or benchmark sample text.

## Benchmark Run Metadata

Capture redacted run metadata:

- `run_id`
- `benchmark_suite`
- `benchmark_version`
- `scenario`
- `sut_endpoint_id`
- `model_id`
- `started_at`
- `traffic_class`

Optional fields include hardware profile, region, dataset ID, operator, git SHA,
and runner version.

## Latency And Throughput Impact

Each sidecar run should report:

- baseline p50/p95 latency
- sidecar p50/p95 latency
- p95 overhead
- baseline requests per second
- sidecar requests per second
- throughput delta percent

These fields let MLCommons endpoint teams evaluate AANA’s runtime impact without
changing their benchmark runner.

## Fail-Closed Live Policy

For live endpoint deployment, direct forwarding requires:

```json
{
  "gate_decision": "pass",
  "recommended_action": "accept",
  "hard_blockers": 0,
  "aix_hard_blockers": 0,
  "contract_errors": 0
}
```

If the AANA bridge is unavailable, the endpoint sidecar must block or defer live
traffic. In shadow benchmark mode, it should record `would_block` or
`would_defer` without changing benchmark execution.

## CLI

Validate the checked-in contract:

```powershell
python scripts/aana_cli.py mlcommons-endpoint-sidecar --json
```

Write the default contract:

```powershell
python scripts/aana_cli.py mlcommons-endpoint-sidecar `
  --write-default `
  --contract examples/mlcommons_endpoint_sidecar_contract.json `
  --json
```

Write a readiness report:

```powershell
python scripts/aana_cli.py mlcommons-endpoint-sidecar `
  --contract examples/mlcommons_endpoint_sidecar_contract.json `
  --report eval_outputs/mlcommons_endpoints/sidecar-readiness-report.json `
  --json
```
