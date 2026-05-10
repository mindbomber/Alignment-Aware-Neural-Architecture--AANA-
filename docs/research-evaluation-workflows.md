# AANA Research And Evaluation Workflows

This page holds the long-form research, benchmark, Hugging Face, pilot, and evidence workflow details that should not live in the README product entry point.

The public product claim remains: AANA is a pre-action control layer for AI agents: agents propose actions, AANA checks evidence/auth/risk, and tools execute only when the route is accept. Do not use the workflows below to claim AANA is proven as a raw agent-performance engine.

## Evidence Boundary

AANA evidence is separated into:

- `calibration`: used to tune thresholds, routes, or adapters.
- `heldout`: used for local held-out validation after tuning.
- `diagnostic`: useful engineering evidence, not a public superiority claim.
- `probe`: benchmark-fit or debugging evidence only.
- `external_reporting`: evidence prepared for public reporting or maintainer review.

See [public-claims-policy.md](public-claims-policy.md), [benchmark-reporting-policy.md](benchmark-reporting-policy.md), and [aana-production-candidate-evidence-pack.md](aana-production-candidate-evidence-pack.md).

## Current Diagnostic Evidence

The current evidence pack includes:

- Safety/adversarial prompt routing: deterministic AANA preserves safe allow but misses many harmful prompts; a diversified request-level verifier improves harmful-request recall while conservative calibration protects safe allow. AdvBench transfer remains weak, so this is not a content-moderation claim.
- Finance/high-risk QA: a controlled FinanceBench diagnostic shows supported filing answers are allowed and unsupported finance overclaims are routed to revise/defer. This is not official FinanceBench leaderboard evidence or investment-advice evaluation.
- Governance/compliance policy routing: a small diagnostic over Hugging Face policy-doc metadata plus repo-heldout policy cases shows citation, missing-evidence, private-data export, destructive-action, and human-review routing behavior. This is not legal, regulatory, or platform-policy certification.
- Integration validation v1: held-out tool-call cases show route parity, blocked-tool non-execution, decision-shape parity, audit completeness, and zero schema failures across CLI, Python SDK, TypeScript SDK, FastAPI, MCP, and middleware surfaces. This validates platform wiring, not raw agent task success.
- MSB / MCP Security Bench protocol submission: converted MSB task and attack templates show AANA v2 blocking converted MCP attack templates while preserving safe public-read allows. This is a protocol-level submission artifact, not a full MSB harness replay or leaderboard claim. See [aana-msb-mcp-security-bench.md](aana-msb-mcp-security-bench.md).
- MCP-Bench target: AANA should be evaluated as a paired control layer around the same base agent, not as a standalone model row. See [aana-mcp-bench-submission-plan.md](aana-mcp-bench-submission-plan.md).

Public evidence links:

- [AANA public artifact hub](https://huggingface.co/collections/mindbomber/aana-public-artifact-hub-69fecc99df04ae6ed6dbc6c4)
- [AANA peer-review evidence pack](https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack)
- [AANA Hugging Face Space](https://huggingface.co/spaces/mindbomber/aana-demo)
- [docs/evidence](evidence/README.md)

## Papers

Draft manuscripts:

- [papers/aana-framework.pdf](../papers/aana-framework.pdf)
- [papers/invisible-divergence-layered-alignment-dynamics.pdf](../papers/invisible-divergence-layered-alignment-dynamics.pdf)
- [papers/ATS_Dynamical_Alignment_arXiv.pdf](../papers/ATS_Dynamical_Alignment_arXiv.pdf)

These are early research manuscripts. They include theoretical framing, architecture design, evaluation protocol, and simulated or exploratory results. Treat them as research context, not as peer-reviewed benchmark claims.

## Earlier Constraint-Reasoning Findings

Earlier tracked findings are documented in:

- [constraint-reasoning-aana-report.md](constraint-reasoning-aana-report.md)
- [application-demo-report.md](application-demo-report.md)
- [travel-tool-demo-report.md](travel-tool-demo-report.md)
- [unified-aana-comparison.md](unified-aana-comparison.md)
- [pilot-table2-report.md](pilot-table2-report.md)
- [pilot-table2-spotcheck-audit.md](pilot-table2-spotcheck-audit.md)
- [paper-pilot-results-section.md](paper-pilot-results-section.md)

The evidence package includes source-file hashes, commit SHA, analysis commands, confidence-interval methods, and caveats in [evidence/manifest.json](evidence/manifest.json).

## Research Evaluation Quickstart

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

For live model loops, set an OpenAI-compatible endpoint:

```text
AANA_PROVIDER=openai
AANA_API_KEY=your_provider_or_proxy_key
AANA_BASE_URL=https://your-provider.example/v1
```

For Anthropic:

```text
AANA_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Generate held-out ATS/AANA tasks:

```powershell
python eval_pipeline/generate_heldout_tasks.py --output eval_outputs/heldout/heldout_ats_aana_tasks.jsonl
```

Run a dry run without API calls:

```powershell
python eval_pipeline/run_evals.py --limit 2 --dry-run
python eval_pipeline/score_outputs.py --input eval_outputs/raw_outputs.jsonl --scored eval_outputs/scored_outputs.csv --summary eval_outputs/summary_by_condition.csv
```

Run baseline, weak, and strong correction prompt evaluations:

```powershell
python eval_pipeline/run_evals.py --tasks eval_outputs/heldout/heldout_ats_aana_tasks.jsonl --output eval_outputs/raw_outputs.jsonl --limit 10
```

Run the AANA generator/verifier/corrector loop:

```powershell
python eval_pipeline/run_aana_evals.py --tasks eval_outputs/heldout/heldout_ats_aana_tasks.jsonl --output eval_outputs/aana_outputs.jsonl --limit 10
```

Judge outputs with an LLM judge:

```powershell
python eval_pipeline/judge_score_outputs.py --input eval_outputs/raw_outputs.jsonl --judge-jsonl eval_outputs/judge_scores.jsonl --judged eval_outputs/judged_outputs.csv --summary eval_outputs/judge_summary_by_condition.csv
```

Generate plots:

```powershell
python eval_pipeline/plot_results.py --summary eval_outputs/judge_summary_by_condition.csv --output-dir eval_outputs/judge_plots
```

Generate originality tasks and experiments:

```powershell
python eval_pipeline/generate_originality_tasks.py
python eval_pipeline/run_originality_evals.py --limit 4 --conditions baseline originality_aana
```

## Workflow Contract Research Examples

Validate and run Workflow Contract examples:

```powershell
python scripts/aana_cli.py validate-workflow --workflow examples/workflow_research_summary.json
python scripts/aana_cli.py workflow-check --workflow examples/workflow_research_summary.json
python scripts/aana_cli.py validate-workflow-batch --batch examples/workflow_batch_productive_work.json
python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json
```

Run executable agent-event examples:

```powershell
python scripts/aana_cli.py run-agent-examples
```

Scaffold an agent event:

```powershell
python scripts/aana_cli.py scaffold-agent-event support_reply --output-dir examples/agent_events
```

Validate the adapter gallery:

```powershell
python scripts/aana_cli.py validate-gallery --run-examples
```

## Pilot And Production-Boundary Workflows

Passing `pilot-certify`, `release-check`, or local tests does not certify production safety. These commands prove repo-local behavior and release hygiene only.

Define the line between demo, pilot, and production certification:

```powershell
python scripts/aana_cli.py production-certify --json --certification-policy examples/production_certification_template.json
```

Run synthetic starter pilot kits:

```powershell
python scripts/pilots/run_starter_pilot_kit.py --kit all
```

Run controlled design-partner pilot bundles:

```powershell
python scripts/pilots/run_design_partner_pilots.py --pilot all
```

Run shadow mode before enforcing behavior:

```powershell
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl --shadow-mode
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl
```

Related docs:

- [production-certification.md](production-certification.md)
- [starter-pilot-kits.md](starter-pilot-kits.md)
- [design-partner-pilots.md](design-partner-pilots.md)
- [shadow-mode.md](shadow-mode.md)
- [pilot-surface-certification.md](pilot-surface-certification.md)
- [pilot-evaluation-kit.md](pilot-evaluation-kit.md)

## Local Demos And Browser Tools

Run the local playground:

```powershell
python scripts/demos/run_playground.py
```

Then visit `http://localhost:8765/playground`.

Run everyday irreversible-action demos:

```powershell
python scripts/demos/run_local_demos.py
```

Then visit `http://localhost:8765/demos`.

Related docs:

- [web-playground.md](web-playground.md)
- [local-desktop-browser-demos.md](local-desktop-browser-demos.md)
- [docker-http-bridge.md](docker-http-bridge.md)

## GitHub, OpenClaw, And No-Code Integrations

GitHub Action:

```yaml
- uses: mindbomber/Alignment-Aware-Neural-Architecture--AANA-/.github/actions/aana-guardrails@main
  with:
    fail-on: candidate-block
```

See [github-action.md](github-action.md) and [../examples/github-actions/aana-guardrails.yml](../examples/github-actions/aana-guardrails.yml).

For OpenClaw-style agents, start with:

- [../examples/openclaw/aana-guardrail-pack-plugin](../examples/openclaw/aana-guardrail-pack-plugin)
- [../examples/openclaw/aana-runtime-connector-plugin](../examples/openclaw/aana-runtime-connector-plugin)
- [agent-integration.md](agent-integration.md)
- [openclaw-skill-review-notes.md](openclaw-skill-review-notes.md)

## Dev And CI Commands

Run unit tests:

```powershell
python -m unittest discover -s tests
```

Run helper checks:

```powershell
python scripts/dev.py check
python scripts/dev.py contract-freeze
python scripts/dev.py production-profiles
python scripts/dev.py pilot-bundle
python scripts/dev.py pilot-eval
```

Run the standard platform gate:

```powershell
python scripts/validate_aana_platform.py
```

`contract-freeze` validates frozen public contracts, schemas, compatibility fixtures, and docs for adapter JSON, Agent Event, Workflow, AIx, evidence, audit, and metrics surfaces.

`production-profiles` validates the adapter gallery, contract freeze, AIx tuning, deployment manifest, governance policy, observability policy, evidence registry, evidence integration stubs, audit metrics export, and release-check behavior.

`pilot-bundle` runs the broader local pilot path with multiple agent events, redacted audit logging, metrics export, audit integrity manifests, release-check, and production-profile validation.

`pilot-eval` runs the AANA Pilot Evaluation Kit for enterprise, personal, civic/government, and public-data pilot planning.
