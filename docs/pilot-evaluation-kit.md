# AANA Pilot Evaluation Kit

The Pilot Evaluation Kit is the pre-real-data evaluation path for AANA adapters. It lets a team run synthetic and public-data-rehearsal scenarios before connecting private CRM, email, calendar, IAM, deployment, billing, medical, legal, or government systems.

Run the full kit:

```powershell
python scripts/dev.py pilot-eval
```

Run a specific pack:

```powershell
python scripts/run_pilot_evaluation_kit.py --pack enterprise
python scripts/run_pilot_evaluation_kit.py --pack personal
python scripts/run_pilot_evaluation_kit.py --pack civic_government
python scripts/run_pilot_evaluation_kit.py --pack public_data_rehearsal
```

The default manifest is [examples/pilot_evaluation_kit.json](../examples/pilot_evaluation_kit.json). It defines:

- enterprise, personal, civic/government, and public-data-rehearsal packs,
- pilot surfaces for each pack, including entrypoint, operating mode, primary users, evidence systems, and review handoff,
- adapter scenarios to run,
- expected route behavior,
- synthetic evidence basis,
- public dataset families that can seed richer non-private fixtures,
- operator workflow notes for shadow/advisory pilots.

Outputs are written under `eval_outputs/pilot_eval/` by default:

- redacted audit JSONL,
- audit metrics JSON,
- machine-readable JSON report,
- Markdown report for reviewers.

The kit is intentionally not a replacement for real-world testing. Its job is to make the next pilot safer by proving that adapter routing, hard blockers, AIx decisions, audit records, and operator handoffs behave coherently before private data or irreversible actions are involved.

## Current Packs

Enterprise pack:

- CRM support reply
- email send
- ticket update
- data export
- access permission
- code change review
- deployment readiness
- incident response update

Personal productivity pack:

- email guardrail
- calendar scheduling
- file operation guardrail
- purchase/booking guardrail
- research grounding

Civic/government pack:

- procurement/vendor risk
- grant/application review
- public-records/privacy redaction
- policy memo grounding
- benefits eligibility triage
- legal safety routing
- publication check

Some civic/government surfaces currently map onto existing general adapters while the repo gathers pilot evidence: public-records/privacy redaction uses `data_export_guardrail`, policy memo grounding uses `research_answer_grounding`, and benefits eligibility triage uses `insurance_claim_triage`. Promote those into dedicated adapters only after the pilot fixtures show distinct verifier requirements.
