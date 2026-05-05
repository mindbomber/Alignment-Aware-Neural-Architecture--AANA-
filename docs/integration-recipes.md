# AANA Integration Recipes

Canonical entry point: [Integrate Runtime](integrate-runtime/index.md). This page keeps the copyable recipe index for existing links.

These recipes are copyable starting points for using AANA around real workflows without hand-building contracts. Run commands from the repository root.

## Recipes

| Recipe | Use when | Working input |
| --- | --- | --- |
| [Use AANA with GitHub Actions](recipes/use-aana-with-github-actions.md) | Add PR and release guardrails to CI. | `examples/github-actions/aana-guardrails.yml` |
| [Use AANA with a local agent](recipes/use-aana-with-a-local-agent.md) | Put AANA around a local agent/tool call. | `examples/agent_event_support_reply.json` |
| [Use AANA with CRM support drafts](recipes/use-aana-with-crm-support-drafts.md) | Check customer support replies against account facts, policy, privacy, and tone. | `examples/workflow_crm_support_reply.json` |
| [Use AANA for deployment reviews](recipes/use-aana-for-deployment-reviews.md) | Review production release readiness before deploy. | `examples/workflow_deployment_readiness.json` |
| [Use AANA in shadow mode](recipes/use-aana-in-shadow-mode.md) | Observe would-block/would-revise behavior without changing production behavior. | `examples/workflow_batch_productive_work.json` |

## Common Result Rules

Proceed only when:

- `gate_decision` is `pass`;
- `recommended_action` is `accept`;
- `aix.decision` is `accept`;
- `aix.hard_blockers` is empty.

When AANA returns `revise`, `ask`, `retrieve`, `defer`, or `refuse`, route the workflow to that behavior instead of continuing the original action.

## Audit And Metrics

All recipes can write redacted audit logs. Audit records contain adapter IDs, gate decisions, recommended actions, AIx summaries, violation codes, and input fingerprints. They do not store raw prompts, candidates, evidence, safe responses, or outputs.

Useful follow-up commands:

```powershell
python scripts/aana_cli.py audit-summary --audit-log eval_outputs/audit/recipes/aana-recipe.jsonl
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/recipes/aana-recipe.jsonl --output eval_outputs/audit/recipes/aana-recipe-metrics.json
python scripts/aana_cli.py audit-validate --audit-log eval_outputs/audit/recipes/aana-recipe.jsonl
```
