# AANA Starter Pilot Kits

These kits let pilot users run realistic AANA scenarios without private data.
Each kit contains:

- `manifest.json` - kit identity, entrypoints, output paths, and user workflow.
- `adapter_config.json` - adapter set, risk notes, and evidence requirements.
- `synthetic_data.json` - fake evidence records with source IDs and freshness metadata.
- `workflows.json` - workflow examples materialized from the adapter gallery plus synthetic evidence references.
- `expected_outcomes.json` - expected gate, action, AIx, and route behavior.

Run all kits:

```powershell
python scripts/pilots/run_starter_pilot_kit.py --kit all
```

Run one kit:

```powershell
python scripts/pilots/run_starter_pilot_kit.py --kit enterprise
python scripts/pilots/run_starter_pilot_kit.py --kit personal_productivity
python scripts/pilots/run_starter_pilot_kit.py --kit government_civic
```

Outputs are written under `eval_outputs/starter_pilot_kits/<kit-id>/`:

- `audit.jsonl`
- `metrics.json`
- `report.json`
- `report.md`
- `materialized_workflows.json`

The audit records are redacted and contain fingerprints, adapter IDs, gate
decisions, recommended actions, violation codes, and AIx summaries, not raw
private content.
