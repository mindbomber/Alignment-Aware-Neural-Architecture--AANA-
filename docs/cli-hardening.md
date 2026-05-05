# AANA CLI Hardening

The AANA CLI is an operator-facing entry point for adapter checks, workflow checks, audit review, pilot runs, and release gates. This document freezes the current CLI contract for production-readiness work without claiming that every external deployment concern is solved inside the repository.

## Contract Version

Current CLI contract version: `0.1`

Print the machine-readable command matrix:

```powershell
python scripts/aana_cli.py cli-contract --json
```

Print the human-readable matrix:

```powershell
python scripts/aana_cli.py cli-contract
```

## Exit Codes

- `0` - command completed successfully.
- `1` - command ran and found validation, gate, release, or policy failures.
- `2` - command could not run because inputs, paths, JSON, or arguments were invalid.

Validation failures stay separate from usage failures. For example, an invalid Agent Event JSON schema returns `1`; a missing `--event` file returns `2`.

## JSON Error Contract

Commands that support `--json` return structured errors for preflight and runtime input failures:

```json
{
  "cli_contract_version": "0.1",
  "ok": false,
  "error": {
    "type": "CliError",
    "message": "event path does not exist: missing-event.json",
    "details": {
      "argument": "--event",
      "path": "missing-event.json"
    }
  },
  "exit_code": 2
}
```

Text mode prints the same failure to `stderr` with the `aana_cli failed:` prefix.

## Input Path Validation

The CLI preflights required read paths before command execution for commands that consume files or directories. Examples:

```powershell
python scripts/aana_cli.py validate-event --event examples/agent_event_support_reply.json
python scripts/aana_cli.py validate-workflow --workflow examples/workflow_research_summary.json
python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json
python scripts/aana_cli.py audit-verify --manifest eval_outputs/audit/manifests/aana-audit-integrity.json
```

Output paths such as `--audit-log`, `--output`, and scaffold `--output-dir` are not required to already exist unless the command itself defines that requirement.

## Dry Runs

Scaffold commands support dry-run mode so operators can inspect planned writes:

```powershell
python scripts/aana_cli.py scaffold "insurance claim triage" --output-dir examples --dry-run
python scripts/aana_cli.py scaffold-agent-event support_reply --dry-run
```

Dry-run output includes `dry_run: true` and the files that would be created. No files are written.

## Major Workflow Examples

Adapter and gallery checks:

```powershell
python scripts/aana_cli.py list
python scripts/aana_cli.py validate-gallery --run-examples
python scripts/aana_cli.py validate-adapter examples/support_reply_adapter.json
python scripts/aana_cli.py run support_reply
```

Agent and workflow checks:

```powershell
python scripts/aana_cli.py validate-event --event examples/agent_event_support_reply.json
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py workflow-check --workflow examples/workflow_research_summary_structured.json --evidence-registry examples/evidence_registry.json --require-structured-evidence
python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json --audit-log eval_outputs/audit/aana-audit.jsonl
```

Audit and metrics:

```powershell
python scripts/aana_cli.py audit-summary --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/aana-metrics.json
python scripts/aana_cli.py audit-manifest --audit-log eval_outputs/audit/aana-audit.jsonl --output eval_outputs/audit/manifests/aana-audit-integrity.json
python scripts/aana_cli.py audit-verify --manifest eval_outputs/audit/manifests/aana-audit-integrity.json
```

Production readiness:

```powershell
python scripts/aana_cli.py contract-freeze
python scripts/aana_cli.py aix-tuning
python scripts/aana_cli.py production-preflight --deployment-manifest examples/production_deployment_template.json --evidence-registry examples/evidence_registry.json
python scripts/aana_cli.py release-check --skip-local-check --deployment-manifest examples/production_deployment_template.json --governance-policy examples/human_governance_policy_template.json --evidence-registry examples/evidence_registry.json --observability-policy examples/observability_policy.json
```

## Compatibility Rules

- Additive command fields can ship in the same `0.1` contract when existing JSON keys and exit-code meanings remain unchanged.
- Removing a command, changing an exit-code meaning, renaming JSON keys, or changing a success/failure interpretation requires a CLI contract version bump.
- New commands should be added to `cli-contract`, documented with one example, and covered by at least one golden-output or behavior test.
- A command that writes files should provide `--dry-run` when the write is operator-initiated and predictable before execution.
