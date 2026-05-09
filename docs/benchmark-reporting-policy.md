# Benchmark Reporting Policy

This policy keeps AANA benchmark communication honest.

## Scope Labels

Every benchmark report must use one of these labels:

- `public_general_result`: a default/general run with no benchmark probes, with explicit limitations and artifacts.
- `engineering_smoke_only`: a small regression or smoke run that can guide engineering but cannot support broad public claims.
- `diagnostic_probe_only`: a run that uses exact benchmark probes, task literals, hand-discovered recovery flows, or `--allow-benchmark-probes`.

## Hard Rule

Diagnostic probe results must never be merged into public AANA claims.

Probe runs can be used to debug a planner, identify missing verifier signals, or design a general adapter. They cannot be used to say AANA improved benchmark performance, reached a leaderboard score, or demonstrated generalization.

## Public Claim Requirements

A public benchmark claim must:

- Run without `--allow-benchmark-probes`.
- Treat the default tau2 workflow scope, `general_non_probe`, as the only valid
  scaffold path for generalization evidence.
- Exclude probe artifacts and probe metrics from all primary numbers.
- State the benchmark, data split, label source, model/base-agent, AANA mode, and scaffold version.
- Include limitations, especially whether labels are maintainer-provided, human-reviewed, benchmark-rubric-derived, or policy-derived by our scripts.
- Separate task success, safety/control metrics, schema failures, refusal/ask/defer counts, and recovery behavior.

## Required Language

Use:

- "Diagnostic probe run" for probe-enabled experiments.
- "Engineering smoke test" for small non-probe regression runs.
- "Measured general run" only when the default scaffold ran without probes.
- "Official submission" only when the benchmark maintainer or leaderboard accepted the result.

Avoid:

- "AANA scored X" when X includes probe-enabled runs.
- "AANA beats baseline" unless the compared runs used the same non-probe protocol.
- "official", "peer-reviewed", "leaderboard", or "production-ready" unless that exact external review or deployment condition happened.

## Validation

Run:

```bash
python scripts/validate_benchmark_reporting.py
```

The validator checks `examples/benchmark_reporting_manifest.json` and blocks any public claim that includes probe results, uses `--allow-benchmark-probes`, lacks limitations, or marks mixed/probe runs as public-claim eligible.

The tau2 scaffold also requires `AANA_ENABLE_DIAGNOSTIC_PROBES=1` before
`--allow-benchmark-probes` can run, so the normal workflow is non-probe by
default and by command-line contract.
