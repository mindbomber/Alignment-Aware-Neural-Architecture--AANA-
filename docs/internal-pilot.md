# AANA Internal Pilot

The internal pilot must start in shadow mode. AANA should observe support workflows, write redacted audit telemetry, and report what it would have blocked or revised while the agent continues through the existing path.

Do not start with full autonomous enforcement.

## Phase Sequence

1. Shadow mode: agent proceeds; AANA logs would-have-blocked and would-have-intervened decisions.
2. Advisory mode: AANA suggests `revise`, `ask`, `defer`, or `refuse`; a human decides whether the output proceeds.
3. Enforced mode for narrow support drafts: enforce only `support_reply`, `crm_support_reply`, and `ticket_update_checker`.
4. Enforced mode for email-send guardrail: enforce `email_send_guardrail` only after recipient, attachment, and human approval paths are tested.
5. Expanded support workflows: add adjacent support workflows only after calibration, connector approval, and owner signoff.

The rollout source of truth is `examples/production_deployment_internal_pilot.json` under `pilot_rollout`.

## Validation

```powershell
python scripts/validate_internal_pilot_plan.py
```

The validator fails if the default phase is not `shadow_mode`, if broad autonomous enforcement is enabled, or if the phase order skips shadow/advisory gates.

## Runner

The internal pilot runner reads the manifest default phase. With the current manifest, it starts the bridge with `--shadow-mode`.

```powershell
python scripts/run_internal_pilot.py --json
```

Use `--pilot-phase advisory_mode` or later phases only after the prior phase has exit evidence and owner signoff. Enforced phases remain narrow and support-scoped.

## Support Shadow Measurements

For the support runtime baseline, run the support shadow pilot against the canonical support Workflow Contract and Agent Event fixtures:

```powershell
python scripts/run_support_shadow_pilot.py
```

The runner is observe-only. It records would-block, would-revise, would-ask, would-defer, and would-refuse behavior without blocking the underlying workflow path. It writes:

- `eval_outputs/audit/support-shadow-internal-pilot.jsonl`
- `eval_outputs/pilots/support-shadow-internal-pilot-results.json`
- `eval_outputs/pilots/support-shadow-internal-pilot-metrics.json`
- `eval_outputs/pilots/support-shadow-internal-pilot-reviewer-report.md`

The measured result artifact is referenced from `examples/internal_pilot_measured_results_support.json` and can be attached to an environment-specific first-deployable baseline. This remains an internal-pilot measurement, not production certification.

## Support Advisory Measurements

After shadow metrics are reviewed and the support owner approves promotion to advisory mode, run:

```powershell
python scripts/run_support_advisory_pilot.py
```

Advisory mode lets AANA recommend `accept`, `revise`, `retrieve`, `ask`, `defer`, or `refuse`, but humans remain the decision authority. Reviewer decisions are loaded from `examples/support_advisory_reviewer_decisions.json` and are stored as redacted action/safety metadata, not raw support content.

The runner writes:

- `eval_outputs/audit/support-advisory-internal-pilot.jsonl`
- `eval_outputs/pilots/support-advisory-internal-pilot-results.json`
- `eval_outputs/pilots/support-advisory-internal-pilot-metrics.json`
- `eval_outputs/pilots/support-advisory-internal-pilot-reviewer-report.md`

The checked-in summary is `examples/internal_pilot_advisory_results_support.json`. It tracks reviewer agreement/disagreement, false blockers, missed unsafe cases, human decision load, latency, and support AIx calibration recommendations. Do not promote to enforced mode unless advisory review accepts the false-blocker rate, missed-unsafe rate, reviewer workload, and threshold-tuning result.

## Narrow Support Draft Enforcement

After advisory-mode review accepts the reviewer-agreement, false-blocker, missed-unsafe, workload, and calibration results, run the narrow enforced draft pilot:

```powershell
python scripts/run_support_enforced_draft_pilot.py
```

This phase enforces only:

- `support_reply`
- `crm_support_reply`
- `ticket_update_checker`

It explicitly excludes `email_send_guardrail`. Email send must remain outside enforcement until recipient verification, attachment metadata/DLP, explicit user approval, and bridge-failure fail-closed behavior for irreversible send are proven.

The runner writes:

- `eval_outputs/audit/support-enforced-draft-internal-pilot.jsonl`
- `eval_outputs/pilots/support-enforced-draft-internal-pilot-results.json`
- `eval_outputs/pilots/support-enforced-draft-internal-pilot-metrics.json`
- `eval_outputs/pilots/support-enforced-draft-internal-pilot-reviewer-report.md`

The checked-in summary is `examples/internal_pilot_enforced_draft_results_support.json`. Do not use this artifact to justify email-send enforcement.

## Email Send Enforcement

After narrow draft enforcement is accepted and irreversible-send controls are reviewed, run:

```powershell
python scripts/run_support_enforced_email_pilot.py
```

This phase enforces only:

- `email_send_guardrail`

It requires every enforced email-send check to prove:

- verified recipient metadata
- attachment metadata/DLP evidence
- explicit irreversible-send approval path
- fail-closed bridge outage behavior for irreversible support actions

The runner writes:

- `eval_outputs/audit/support-enforced-email-internal-pilot.jsonl`
- `eval_outputs/pilots/support-enforced-email-internal-pilot-results.json`
- `eval_outputs/pilots/support-enforced-email-internal-pilot-metrics.json`
- `eval_outputs/pilots/support-enforced-email-internal-pilot-reviewer-report.md`

The checked-in summary is `examples/internal_pilot_enforced_email_results_support.json`. This artifact proves the repo-local email-send enforcement boundary for approved internal fixtures only. It is not external production certification without live evidence connectors, deployment fail-closed validation, staffed human review, and support owner approval.
