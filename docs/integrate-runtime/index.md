# Integrate Runtime

Use this entry point when an app, agent, CLI workflow, CI job, or service needs to call AANA through the stable public contracts.

## Primary Contracts

The product boundary is defined in [Product boundary](../product-boundary.md): AANA is a runtime guardrail layer between an agent and consequential outputs/actions, with support workflows as the first deployable vertical.

The stable public APIs are:

- [Workflow Contract](../aana-workflow-contract.md): request/result schema for app and workflow checks.
- [Agent Event Contract](../agent-integration.md): event/check schema for agents before they act.

Lower-level runner internals are implementation details. Public surfaces should route through the Workflow Contract or Agent Event Contract.

## Runtime Surfaces

- Python package: [Python runtime API](../python-runtime-api.md)
- Integration examples: [Integration recipes](../integration-recipes.md)
- Support agent recipe: [Use AANA with support agents](../recipes/use-aana-with-support-agents.md)
- HTTP bridge: [Docker HTTP bridge](../docker-http-bridge.md) and [HTTP bridge runbook](../http-bridge-runbook.md)
- Browser surface: [Web playground](../web-playground.md)
- CI surface: [GitHub Action](../github-action.md)
- SDK notes: [Adapter integration SDK](../adapter-integration-sdk.md)
- Evidence contracts: [Evidence integration contracts](../evidence-integration-contracts.md)
- Audit and metrics: [Audit/observability hardening](../audit-observability-hardening.md), [Metrics dashboard](../metrics-dashboard.md), and [Shadow mode](../shadow-mode.md)
- Product scope: [Product boundary](../product-boundary.md)

## Production Boundary

Runtime integration can prove contract compatibility and repo-local readiness. It does not certify production safety by itself. Before production claims, run the boundary checks in [Production certification](../production-certification.md) and provide explicit external evidence: connector manifests, shadow-mode logs, audit retention policy, escalation policy, and owner approval.
