# Development Helpers

`dev.py` provides short, cross-platform commands for common local checks.

Run from the repository root:

```powershell
python scripts/dev.py test
python scripts/dev.py sample
python scripts/dev.py dry-run
python scripts/dev.py check
python scripts/dev.py production-profiles
python scripts/dev.py production-profiles --audit-log eval_outputs/audit/ci/aana-ci-audit.jsonl --metrics-output eval_outputs/audit/ci/aana-ci-metrics.json
python scripts/dev.py contract-freeze
python scripts/dev.py pilot-bundle
python scripts/dev.py pilot-eval
python scripts/aana_cli.py cli-contract
python scripts/aana_cli.py cli-contract --json
python scripts/aana_cli.py aix-tuning
python scripts/aana_cli.py contract-freeze
python scripts/aana_cli.py evidence-integrations --evidence-registry examples/evidence_registry.json
python scripts/run_e2e_pilot_bundle.py
python scripts/run_pilot_evaluation_kit.py
python scripts/run_pilot_evaluation_kit.py --pack enterprise --report-output eval_outputs/pilot_eval/enterprise-report.md
python scripts/pilot_smoke_test.py --audit-log eval_outputs/audit/aana-pilot-smoke.jsonl
python scripts/run_internal_pilot.py --audit-log eval_outputs/audit/aana-internal-pilot.jsonl
python scripts/run_internal_pilot.py --audit-log eval_outputs/audit/aana-internal-pilot.jsonl --metrics-output eval_outputs/audit/aana-internal-pilot-metrics.json
python scripts/aana_cli.py release-check --skip-local-check --audit-log eval_outputs/audit/aana-internal-pilot.jsonl
python scripts/aana_cli.py audit-verify --manifest eval_outputs/audit/manifests/aana-internal-pilot-integrity.json
```

Commands:

- `compile` - Compile Python files in `eval_pipeline/`, `tests/`, and `scripts/`.
- `test` - Run the unit tests.
- `sample` - Score the checked-in sample outputs.
- `dry-run` - Generate held-out tasks, run a tiny no-API evaluation, and score it.
- `check` - Run compile, tests, and sample scoring.
- `contract-freeze` - Validate frozen public AANA contracts, schemas, compatibility fixtures, and contract documentation.
- `production-profiles` - CI guard for adapter gallery examples, AIx tuning, internal pilot deployment/governance/observability profiles, evidence registry, evidence integration stubs, audit metrics export, and release-check with a generated redacted audit log. Use `--audit-log` and `--metrics-output` when CI or a handoff process needs stable artifact paths.
- `pilot-bundle` - Run the end-to-end pilot bundle across agent events, audit logging, metrics export, release-check, and production-profile validation.
- `pilot-eval` - Run the AANA Pilot Evaluation Kit and write a redacted audit log, audit metrics JSON, JSON report, and Markdown report.
- `aana_cli.py cli-contract` - Print the stable CLI command matrix, exit-code meanings, JSON error contract, and major command examples for operator use.
- `aana_cli.py aix-tuning` - Report each gallery adapter's AIx risk tier, beta, layer weights, thresholds, and whether the values meet the declared tier.
- `aana_cli.py contract-freeze` - Report frozen contract inventory and validate schemas plus compatibility fixtures for adapters, agent events, workflows, AIx, evidence, audit records, and metrics.
- `aana_cli.py evidence-integrations` - List production evidence connector stubs and verify that the evidence registry covers their required source IDs.
- `run_e2e_pilot_bundle.py` - Run multiple checked-in agent events, append redacted audit records, export audit metrics, write an audit integrity manifest, run release-check, and run production profile validation.
- `run_pilot_evaluation_kit.py` - Run named synthetic and public-data-rehearsal pilot packs for enterprise, personal, civic/government, and public-data evaluation planning.
- `pilot_smoke_test.py` - Start or target the AANA HTTP bridge, verify POST auth, run an agent check, verify server-side redacted audit append, and summarize the audit log.
- `run_internal_pilot.py` - Set up the internal pilot runtime directories, start the real bridge with `AANA_BRIDGE_TOKEN` and `--audit-log`, run the smoke test against that live bridge, write an audit integrity manifest and metrics export, and shut it down.
- `aana_cli.py audit-metrics` - Export flat dashboard metrics from redacted audit JSONL, including gate decisions, recommended actions, violation codes, adapter counts, record types, and AIx score/decision/hard-blocker fields.
- `aana_cli.py release-check` - Enforce release gates, including adapter AIx tuning against declared risk tiers.
- `aana_cli.py release-check --audit-log` - Also enforce release AIx thresholds against redacted audit logs, failing on low AIx scores, AIx hard blockers, or disallowed final AIx decisions.
- `aana_cli.py audit-manifest` / `audit-verify` - Create and verify local SHA-256 manifests for redacted audit JSONL files.
