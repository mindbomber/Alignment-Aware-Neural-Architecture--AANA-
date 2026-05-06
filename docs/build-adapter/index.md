# Build Adapter

Use this entry point when you want to add or harden a workflow-specific AANA guardrail.

## Adapter Path

Start from the [Product boundary](../product-boundary.md) when deciding whether a workflow belongs in the deployable runtime layer. The first deployable support boundary covers support replies, CRM support replies, refund/account-fact checks, support email-send checks, and customer-visible ticket updates.

1. Choose an existing catalog entry close to your workflow.
2. Define the domain, failure modes, constraints, evidence, verifiers, correction actions, and gate rules.
3. Declare AIx tuning and production-readiness metadata.
4. Add a gallery entry with expected behavior.
5. Validate the adapter and run gallery examples.

```powershell
python scripts/aana_cli.py scaffold "customer support reply"
python scripts/aana_cli.py validate-adapter examples/support_reply_adapter.json
python scripts/aana_cli.py validate-gallery --run-examples
python scripts/aana_cli.py aix-tuning
```

## What To Read Here

- [Domain adapter template](../domain-adapter-template.md): adapter contract and blank design template.
- [Adapter gallery](../adapter-gallery.md): product catalog and metadata expectations.
- [Adapter integration SDK](../adapter-integration-sdk.md): packaging adapters for runtime consumers.
- [Verifier module inventory](../verifier-module-inventory.md): internal verifier families, constraint maps, and stability gates.
- [Product boundary](../product-boundary.md): deployable runtime scope and first support-workflow boundary.
- [AANA Workflow Contract](../aana-workflow-contract.md): request/result boundary every adapter ultimately serves.
- [Contract freeze](../contract-freeze.md): compatibility expectations for public schemas.
- [Production readiness plan](../production-readiness-plan.md): hardening roadmap and external production boundary.

Keep the claim narrow: an adapter proves that a specific contract, verifier path, fixture set, and gate behavior work. Domain production readiness still depends on live evidence connectors, domain owner signoff, retained audit evidence, observability, and human review.
