# Reviewer Start Here

AANA is a pre-action control layer for AI agents: agents propose actions, AANA checks evidence/auth/risk, and tools execute only when the route is `accept`.

Use this page when reviewing AANA as a maintainer, benchmark reviewer, standards contributor, or integration partner.

## What To Review

The claim under review is narrow:

- AANA makes consequential agent actions more auditable, safer, more grounded, and more controllable.
- AANA standardizes a pre-action contract before tool execution.
- AANA emits audit-safe decision records for every check.
- AANA is not claiming to be a better base agent or a proven raw agent-performance engine.

The core runtime pattern is:

```text
agent proposes -> AANA checks -> tool executes only if route == accept
```

## Ten-Minute Review Path

1. Try the hosted demo: <https://huggingface.co/spaces/mindbomber/aana-demo>
2. Read the contract: [Agent Action Contract v1](agent-action-contract-v1.md)
3. Inspect the static demo: [tool-call-demo/index.html](tool-call-demo/index.html)
4. Run the integration proof:

```powershell
python scripts/validation/validate_agent_integrations.py
```

5. Run the platform gate:

```powershell
aana-validate-platform
```

Expected integration result:

```text
pass -- passed=15/15
```

## What The Demo Shows

The demo is synthetic and cannot send, delete, buy, deploy, export, or change permissions. It shows the control-layer behavior:

- `accept` allows the synthetic executor to run.
- `ask`, `defer`, and `refuse` block execution.
- missing authorization or missing evidence becomes a blocker.
- a runtime recommendation of `accept` can be overridden.
- the decision includes route, AIx score, blockers, missing evidence, authorization state, and an audit-safe event.

## Evidence Boundary

AANA results are labeled before publication:

- `calibration`: used for tuning thresholds or route rules.
- `heldout`: held out from calibration and used for validation.
- `diagnostic`: useful engineering evidence, not official benchmark proof.
- `probe`: targeted debugging; not public claim evidence.
- `external_reporting`: prepared for maintainer review or public reporting.

Do not treat diagnostic or probe results as official leaderboard claims. Stronger claims require a benchmark-maintainer accepted protocol or independently reviewed labels.

## What To Challenge

Useful review feedback is concrete:

- a tool call AANA allowed but should have blocked,
- a safe public read AANA over-blocked,
- an authorization state the contract cannot represent cleanly,
- an evidence reference that leaks private data or lacks provenance,
- a middleware path where a non-`accept` route still executes,
- a benchmark where AANA should be tested as a control layer or wrapper,
- a case where the same decision shape is not preserved across CLI, SDK, API, MCP, or middleware.

## Key Links

- Public artifact hub: <https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4>
- Peer-review evidence pack: <https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack>
- Technical report: [AANA as a pre-action control layer](aana-pre-action-control-layer-technical-report.md)
- Maintainer review request: [maintainer-review-benchmark-submission-request.md](maintainer-review-benchmark-submission-request.md)
- Public claims policy: [public-claims-policy.md](public-claims-policy.md)
- Benchmark reporting policy: [benchmark-reporting-policy.md](benchmark-reporting-policy.md)
