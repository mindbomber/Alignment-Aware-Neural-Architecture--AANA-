# Support Domain Owner Signoff

Support guardrails cannot move beyond shadow/advisory use on repo-local tests alone. Support leadership, support policy owners, and privacy or audit owners must approve the operating boundary before enforced support phases.

The signoff template is `examples/support_domain_owner_signoff_template.json`.

Required approval areas:

- refund policy interpretation
- verification requirements
- escalation paths
- safe response language
- human review triggers
- audit retention
- customer-facing language boundaries
- allowed automation scope

The checked-in template is intentionally `pending_external_approval`. That is valid for demo and shadow-mode validation. Before enforced support drafts, email-send enforcement, or expanded support workflows, run the validator with `--require-approved` against an environment-specific signoff artifact:

```powershell
python scripts/validate_support_domain_signoff.py --signoff path/to/support-domain-signoff.json --require-approved
```

This repository does not certify that support leadership has approved the policy. It only defines the required signoff shape and gates the presence of every required approval area.
