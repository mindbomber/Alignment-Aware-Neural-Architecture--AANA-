# AANA Design Partner Pilots

This folder defines controlled pilot bundles for running AANA with design partners before live production integration.

Run all pilot bundles:

```powershell
python scripts/run_design_partner_pilots.py --pilot all
```

Run one pilot bundle:

```powershell
python scripts/run_design_partner_pilots.py --pilot enterprise_support_ops
```

Each pilot writes:

- redacted audit JSONL
- audit metrics JSON
- dashboard payload JSON
- AIx drift report JSON
- audit integrity manifest
- reviewer report Markdown
- Workflow Contract batch JSON
- field-notes template
- partner feedback JSON template

The checked-in pilot bundles use synthetic or redacted-input assumptions. They do not represent real partner findings until a reviewer fills a `<pilot_id>.json` feedback file and passes it with `--feedback-dir`.
