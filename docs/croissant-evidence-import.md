# Croissant Evidence Registry Import

`croissant-evidence-import` converts MLCommons Croissant dataset metadata into
an AANA evidence registry source. This gives regulated AI audits a structured
dataset-provenance input without copying raw dataset records into AANA.

The importer reads Croissant JSON metadata and extracts:

- dataset name, URL, version, and Croissant conformance marker
- creators and publishers
- license or `sdLicense`
- `citeAs`
- intended use or description
- distribution files
- record-set and field counts
- likely sensitive fields
- provenance and governance gaps

It writes:

- AANA evidence registry JSON
- Croissant import gap report JSON

## CLI

```powershell
python scripts/aana_cli.py croissant-evidence-import `
  --metadata examples/croissant_metadata_sample.json `
  --output-registry eval_outputs/croissant/evidence-registry.json `
  --report eval_outputs/croissant/croissant-evidence-report.json `
  --json
```

## Evidence Registry Output

The generated registry uses the normal AANA shape:

```json
{
  "registry_version": "0.1",
  "sources": [
    {
      "source_id": "croissant-synthetic-support-cases-2026-05",
      "owner": "AANA Synthetic Data Team",
      "enabled": true,
      "allowed_trust_tiers": ["verified", "approved_fixture", "repository_fixture"],
      "allowed_redaction_statuses": ["redacted", "public", "synthetic"],
      "max_age_hours": null,
      "metadata": {
        "source_type": "croissant_dataset",
        "dataset_name": "Synthetic Support Cases",
        "licenses": ["https://spdx.org/licenses/CC-BY-4.0.html"],
        "sensitive_fields": ["customer_email"]
      }
    }
  ]
}
```

## Gap Checks

The importer flags missing:

- dataset name
- creator
- license or `sdLicense`
- citation
- distribution
- intended use or description
- privacy policy when sensitive fields are detected

Errors disable the generated evidence source. Warnings keep the source enabled
but show what should be completed before regulated deployment review.

## Boundary

Croissant metadata supports dataset provenance evidence. It does not certify
dataset quality, legal compliance, consent, privacy controls, or production
readiness by itself. For regulated deployment, pair the imported registry with
AANA runtime audits, AIx Reports, domain-owner signoff, durable audit storage,
security review, and measured shadow-mode results.
