# tau2 Diagnostic Probes

This folder quarantines tau2 probe planners that contain benchmark-specific literals or hand-discovered recovery flows.

The general tau2 scaffold remains in `examples/tau2/`. It may import this module only when both `--allow-benchmark-probes` and `AANA_ENABLE_DIAGNOSTIC_PROBES=1` are set.

Results from this folder are diagnostic only and must not be merged into public AANA claims.
