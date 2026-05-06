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
