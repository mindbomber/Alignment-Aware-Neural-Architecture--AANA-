# Alignment-Aware Neural Architecture (AANA) Evaluation Pipeline

[![CI](https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/actions/workflows/ci.yml/badge.svg)](https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Status: Alpha Research](https://img.shields.io/badge/status-alpha%20research-orange.svg)](ROADMAP.md)

🌐 Public project site: https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/

🚦 Try AANA in the browser: https://huggingface.co/spaces/mindbomber/aana-demo

![AANA repository social preview](assets/github-social-preview.png)

This repository contains a small Python evaluation pipeline for testing Alignment-Aware Neural Architecture (AANA) ideas. In plain language, it runs prompt-based stress tests against language models, compares baseline answers with AANA-style correction loops, scores the outputs, and generates CSV/SVG summaries that help show where capability and alignment diverge.

Public claim: AANA is an architecture for making agents more auditable, safer, more grounded, and more controllable.

The project is meant for researchers, builders, and curious beginners who want a reproducible starting point for experimenting with verifier-grounded correction, constraint preservation, abstention, and originality in AI assistant outputs.

Platform boundary: AANA is a runtime guardrail layer that sits between an agent and consequential outputs or actions. It receives a Workflow Contract or Agent Event, checks the candidate output/action against adapter-specific constraints, applies verifier-grounded correction policy, returns `accept`, `revise`, `retrieve`, `ask`, `defer`, or `refuse`, and emits audit-safe metadata. See [docs/product-boundary.md](docs/product-boundary.md).

Current evidence boundary: AANA is production-candidate as an audit/control/verification/correction layer. AANA is not yet proven as a raw agent-performance engine. See [docs/aana-production-candidate-evidence-pack.md](docs/aana-production-candidate-evidence-pack.md).

First deployable support boundary: draft support replies, CRM support replies, refund/account-fact checks, support email-send checks, and customer-visible ticket updates. Invoice/billing replies are an adjacent later adapter family.

Start with the path that matches what you are doing:

- **Try Demo**: [docs/try-demo/index.md](docs/try-demo/index.md)
- **Tool Call Gate Demo**: [docs/tool-call-demo/index.html](docs/tool-call-demo/index.html)
- **Head-to-Head Findings**: [docs/aana-head-to-head-findings.md](docs/aana-head-to-head-findings.md)
- **Technical Report**: [docs/aana-agent-action-technical-report.md](docs/aana-agent-action-technical-report.md)
- **Peer Review Evidence Pack**: [Hugging Face dataset](https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack)
- **Integrate Runtime**: [docs/integrate-runtime/index.md](docs/integrate-runtime/index.md)
- **Agent Tool Contract SDK**: [docs/aana-agent-contract-sdk.md](docs/aana-agent-contract-sdk.md)
- **Agent Framework Middleware**: [docs/agent-framework-middleware.md](docs/agent-framework-middleware.md)
- **OpenAI Agents Quickstart**: [docs/openai-agents-quickstart.md](docs/openai-agents-quickstart.md)
- **Agent Action Contract v1**: [docs/agent-action-contract-v1.md](docs/agent-action-contract-v1.md)
- **Agent Action Contract Quickstart**: [docs/agent-action-contract-quickstart.md](docs/agent-action-contract-quickstart.md)
- **Agent Action Contract Cases**: [examples/agent_action_contract_cases.json](examples/agent_action_contract_cases.json)
- **FastAPI Service**: [docs/fastapi-service.md](docs/fastapi-service.md)
- **Evidence Handling**: [docs/evidence-handling.md](docs/evidence-handling.md)
- **Auditability**: [docs/auditability.md](docs/auditability.md)
- **Security Threat Model**: [docs/aana-security-threat-model.md](docs/aana-security-threat-model.md)
- **Authorization State**: [docs/authorization-state.md](docs/authorization-state.md)
- **AANA Standard Publication Package**: [docs/aana-standard-publication.md](docs/aana-standard-publication.md)
- **Packaging Release Checklist**: [docs/packaging-release-checklist.md](docs/packaging-release-checklist.md)
- **Public Claims Policy**: [docs/public-claims-policy.md](docs/public-claims-policy.md)
- **HF Dataset Strategy**: [docs/hf-dataset-strategy.md](docs/hf-dataset-strategy.md)
- **HF Dataset Proof Report**: [docs/hf-dataset-proof-report.md](docs/hf-dataset-proof-report.md)
- **Build Adapter**: [docs/build-adapter/index.md](docs/build-adapter/index.md)

Try AANA without cloning the repo:

- [AANA Hugging Face Space](https://huggingface.co/spaces/mindbomber/aana-demo): enter a candidate answer/action, evidence, and constraints; get an AANA route, AIx score, hard blockers, suggested revision, and audit summary.
- [AANA peer-review evidence pack](https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack): measured privacy, grounded QA, tool-use, and integration validation artifacts with a reproduction script and reviewer-facing report.
- [AANA hosted synthetic demo](https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/demo/): precomputed examples only, requires no secrets, and cannot perform real sends, deletes, deploys, purchases, or exports.
- [AANA head-to-head findings](docs/aana-head-to-head-findings.md): a concise public summary of the agent-action comparisons against permissive agents, classifiers, prompt-only guards, LLM judges, and static contract gates.
- [AANA agent-action technical report](docs/aana-agent-action-technical-report.md): a short architecture report tying the results to `S = (f_theta, E_phi, R, Pi_psi, G)` and the current validity limits.

Production positioning: this repository can be demo-ready, pilot-ready, or production-candidate for controlled evaluation, but it is not production-certified by local tests alone. Production readiness requires live evidence connectors, domain owner signoff, audit retention, observability, human review path, security review, deployment manifest, incident response plan, and measured pilot results.

## Why this matters

Language models can produce answers that look capable while quietly violating important constraints: inventing unsupported facts, exceeding budgets, ignoring safety limits, guessing private information, or becoming manipulative under pressure. AANA experiments measure that failure mode directly by comparing capability and alignment scores across baseline, correction, verifier-loop, tool-assisted, and originality conditions.

## Where AANA is useful

AANA is strongest where failures are mechanically checkable. The point is not to make the model "more careful" by asking nicely. The point is to give the system a correction path that cannot hand-wave constraints away.

The intended direction is base agent plus AANA, not AANA as a replacement for the base agent. Strong models and planners handle raw task execution; AANA checks evidence, authorization, constraints, correction paths, and action routing around them.

Good fit examples:

- Planning assistants with hard budgets, time windows, route constraints, dietary exclusions, forbidden ingredients, or required formats.
- Research and analysis copilots that must distinguish supported facts from impossible claims, missing citations, private information, and unsupported certainty.
- Workflow agents that should only draft, route, summarize, or prepare actions after required fields, permissions, evidence, and escalation rules are checked.
- Safety, compliance, and policy-sensitive assistants where a helpful-looking answer can still fail if it violates an explicit boundary.
- Evaluation pipelines that need to measure when capability, persuasion, or completeness improves while constraint preservation gets worse.

Weaker fit examples:

- Mostly subjective taste, style, or preference tasks with no stable verifier.
- Open-ended brainstorming where there is no clear boundary, evidence source, or correction action.
- Domains where the important harm is delayed, hidden, or impossible to observe without stronger external instrumentation.

In practical terms, AANA is most useful when you can name the constraint, check whether it was violated, and define what the system should do next: revise, retrieve, ask, refuse, defer, or accept.

The docs are organized around three entry points: [Try Demo](docs/try-demo/index.md), [Integrate Runtime](docs/integrate-runtime/index.md), and [Build Adapter](docs/build-adapter/index.md). Deeper background remains available for [architecture](docs/architecture.md), [AANA vs frontier models](docs/aana-vs-sota-llms.md), [pilot evaluation](docs/pilot-evaluation-kit.md), and [production certification boundaries](docs/production-certification.md).

## Who this is for

- AI safety and alignment researchers studying correction loops and evaluation design.
- LLM evaluation builders who need reproducible prompt, scoring, and plotting workflows.
- Product engineers testing whether assistants preserve user constraints under pressure.
- Students and independent researchers learning how model-evaluation pipelines are structured.

## Main Agent-Integration Proof

Run the integration validator to prove the OpenAI-style tool wrapper, FastAPI
policy service, MCP tool surface, and controlled-agent eval harness all work:

```powershell
python scripts/validate_agent_integrations.py
```

Expected result:

```text
pass -- passed=4/4
- pass: openai_wrapped_tools_smoke
- pass: fastapi_policy_service_smoke
- pass: mcp_tool_smoke
- pass: controlled_agent_eval_harness
```

For the full walkthrough, see [docs/openai-agents-quickstart.md](docs/openai-agents-quickstart.md).

## Recommended Local Path

Use this path for platform onboarding:

```powershell
python -m pip install -e .
aana doctor
aana run travel_planning
aana workflow-check --workflow examples/workflow_research_summary.json --audit-log eval_outputs/audit/local-onboarding.jsonl
aana pre-tool-check --event examples/agent_tool_precheck_private_read.json
python scripts/aana_mcp_server.py --list-tools
python examples/chatgpt_app/aana_mcp_app.py
python evals/aana_controlled_agents/run_local.py
python scripts/validate_agent_integrations.py
aana evidence-pack --require-existing-artifacts
aana-server --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/aana-bridge.jsonl
aana audit-summary --audit-log eval_outputs/audit/local-onboarding.jsonl
```

This covers install, health checks, one catalog-backed gallery example, a Workflow Contract check, a pre-tool-call gate, the MCP-style `aana_pre_tool_check` surface, the OpenAI/FastAPI/MCP integration validator, the evidence pack, the HTTP bridge, and redacted audit inspection. The bridge exposes `http://127.0.0.1:8765/ready`, `http://127.0.0.1:8765/playground`, `http://127.0.0.1:8765/adapter-gallery`, `/workflow-check`, `/agent-check`, `/tool-precheck`, and `/openapi.json`.

Advanced research/eval workflows such as `python scripts/dev.py sample`, model-provider experiments, paper tables, and benchmark comparisons are separate from platform onboarding. Start with [docs/try-demo/index.md](docs/try-demo/index.md), then use [docs/evaluation-design.md](docs/evaluation-design.md) or [docs/pilot-evaluation-kit.md](docs/pilot-evaluation-kit.md) when you need research artifacts.

Benchmark reporting boundary: diagnostic probe results are engineering artifacts only and must not be merged into public AANA performance claims. See [docs/benchmark-reporting-policy.md](docs/benchmark-reporting-policy.md) and validate with `python scripts/validate_benchmark_reporting.py`.

Public claims boundary: keep the main claim to “AANA makes agents more auditable, safer, more grounded, and more controllable.” Do not claim AANA is proven as a raw agent-performance engine. Label results as measured, held-out, diagnostic, or probe-only, and publish limitations beside wins. See [docs/public-claims-policy.md](docs/public-claims-policy.md).

For OpenAI Agents SDK, FastAPI policy-service, MCP, and ChatGPT App prototype
integration, start with [docs/openai-agents-quickstart.md](docs/openai-agents-quickstart.md).

Adapter generalization gate: general adapters must use config-backed domain/tool hints, pass held-out validation, pass benchmark-fit linting, and keep diagnostic/probe results out of public claims. Validate the combined gate with `python scripts/validate_adapter_generalization.py --require-existing-artifacts`.

Publication gate: before publishing AANA as a Python package, TypeScript SDK, FastAPI service, Hugging Face model/dataset card, or Agent Action Contract standard, run `python scripts/validate_aana_standard_publication.py --require-existing-artifacts`. The manifest is [examples/aana_standard_publication_manifest.json](examples/aana_standard_publication_manifest.json).

Packaging gate: keep Python package, TypeScript SDK, FastAPI service, benchmark/eval tooling, docs, and cards separated with `python scripts/validate_packaging_hardening.py --require-existing-artifacts`. The current Python distribution remains `aana-eval-pipeline`; any future rename needs a documented migration window and compatibility plan.

## Result Shape

Expected summary shape:

| model | pressure | correction | block | n | capability_score | alignment_score | gap_score |
|---|---|---|---|---:|---:|---:|---:|
| example-model | low | baseline | constraint_reasoning | 1 | 1.0 | 0.8 | 0.2 |
| example-model | low | baseline | truthfulness | 1 | 1.0 | 1.0 | 0.0 |

The key signal is `gap_score = capability_score - alignment_score`. Positive gaps can reveal answers that look useful while losing important constraints.

Run a gallery adapter without memorizing the long prompt:

```powershell
python scripts/aana_cli.py doctor
python scripts/aana_cli.py run travel_planning
```

Try the other gallery adapters:

```powershell
python scripts/aana_cli.py run meal_planning
python scripts/aana_cli.py run support_reply
python scripts/aana_cli.py run research_summary
```

Those commands emit JSON gate results with per-constraint pass/fail status, the deterministic verifier report, the recommended action, and the final constraint-preserving answer.

Call the Workflow Contract directly from Python:

```python
import aana

result = aana.check(
    adapter="research_summary",
    request="Write a concise research brief. Use only Source A and Source B. Label uncertainty.",
    candidate="AANA improves productivity by 40% for all teams [Source C].",
    evidence=["Source A: AANA makes constraints explicit.", "Source B: Source coverage can be incomplete."],
    constraints=["Do not invent citations.", "Do not add unsupported numbers."],
)
```

For JSON request files:

```python
result = aana.check_file("examples/workflow_research_summary.json")
batch = aana.check_batch_file("examples/workflow_batch_productive_work.json")
```

Certify the local pilot surface before handing the repo to a new evaluator:

```powershell
python scripts/aana_cli.py pilot-certify
python scripts/aana_cli.py pilot-certify --json
```

The command prints a public readiness score across the CLI, Python API, HTTP bridge, adapters, evidence, audit/metrics, docs, contracts, and skills/plugins. Details are in [docs/pilot-surface-certification.md](docs/pilot-surface-certification.md).

Passing `pilot-certify`, `release-check`, or local tests does not certify production safety. Those checks prove repo-local behavior and release hygiene; live deployment still needs live evidence connectors, domain owner signoff, audit retention, observability, human review path, security review, deployment manifest, incident response plan, and measured pilot results.

Define the line between demo, pilot, and production certification:

```powershell
python scripts/aana_cli.py production-certify --json --certification-policy examples/production_certification_template.json
```

That command reports `repo_local_not_ready`, `external_evidence_required`, or `deployment_ready` depending on which boundary has been satisfied. See [docs/production-certification.md](docs/production-certification.md).

`production-certify` is a boundary checker, not a production guarantee. It separates repo-local readiness from deployment readiness and requires explicit external evidence for production claims: live connector manifests, shadow-mode logs, audit retention policy, observability, escalation policy, security review, deployment manifest, incident response plan, measured pilot results, and owner approval.

Or run the same platform contract from the CLI:

```powershell
python scripts/aana_cli.py validate-workflow --workflow examples/workflow_research_summary.json
python scripts/aana_cli.py workflow-check --workflow examples/workflow_research_summary.json
python scripts/aana_cli.py validate-workflow-batch --batch examples/workflow_batch_productive_work.json
python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json
python scripts/aana_cli.py workflow-check --adapter research_summary --request "Write a concise research brief. Use only Source A and Source B. Label uncertainty." --candidate "AANA improves productivity by 40% for all teams [Source C]." --evidence "Source A: AANA makes constraints explicit." --evidence "Source B: Source coverage can be incomplete." --constraint "Do not invent citations." --constraint "Do not add unsupported numbers."
```

Check an AI-agent event before the agent acts:

```powershell
aana validate-event --event examples/agent_event_support_reply.json
aana agent-check --event examples/agent_event_support_reply.json
aana pre-tool-check --event examples/agent_tool_precheck_private_read.json
aana evidence-pack --require-existing-artifacts
```

The agent and tool-check outputs include `architecture_decision`: route, AIx score, hard blockers, evidence refs used/missing, authorization state, correction/recovery suggestion, and audit-safe log metadata.

Wrap tools with AANA when integrating agents:

```python
guarded = aana.wrap_agent_tool(send_email)
```

The wrapper infers common reads/writes, gates every call, stores the latest
decision on `guarded.aana_last_gate`, and executes only when AANA returns
`accept`. Add metadata for confirmed writes, private reads, or domain-specific
evidence.

The integration pattern is `agent proposes -> AANA checks -> agent executes only if allowed`. See [docs/agent-framework-middleware.md](docs/agent-framework-middleware.md) and the runnable examples in [examples/integrations](examples/integrations).
For the smallest copy-paste example, use the [Agent Action Contract Quickstart](docs/agent-action-contract-quickstart.md).

Use event-file checks only from a trusted local AANA install or reviewed repository checkout. For standalone agent skills, prefer an approved in-memory tool/API connector, keep review payloads redacted, and do not ask the agent to infer or execute local script paths.

Run the executable agent-event examples across support, travel, meal-planning, and research-summary workflows:

```powershell
python scripts/aana_cli.py run-agent-examples
```

Create a starter event for your own agent workflow from an existing gallery adapter:

```powershell
python scripts/aana_cli.py scaffold-agent-event support_reply --output-dir examples/agent_events
```

Print the versioned agent schemas:

```powershell
python scripts/aana_cli.py agent-schema
```

Agents that can call Python directly can use `eval_pipeline.agent_api.check_event(event)` instead of shelling out. See [examples/agent_api_usage.py](examples/agent_api_usage.py).

List the starter policy presets for deciding where an agent should call AANA:

```powershell
python scripts/aana_cli.py policy-presets
```

Run a local HTTP bridge for agent frameworks that prefer tools, webhooks, or HTTP calls:

```powershell
python scripts/aana_server.py --host 127.0.0.1 --port 8765
```

Then POST the same event JSON to `http://127.0.0.1:8765/validate-event` and `http://127.0.0.1:8765/agent-check`.

The bridge also exposes `http://127.0.0.1:8765/openapi.json` and JSON Schema routes under `/schemas` for tools that can import a contract. If you install the repo locally with `python -m pip install -e .`, you can launch the bridge with `aana-server`.

For the packaged pilot runtime, run the Dockerized bridge:

```powershell
docker compose up --build
```

That starts `http://localhost:8765` with the adapter gallery, playground, family pack pages, internal pilot profiles, local token auth, and mounted redacted audit logs. Open `http://localhost:8765/adapter-gallery`, choose an adapter, click **Try this adapter**, then click **Run AANA Check** in the playground to inspect gate decision, recommended action, violations, AIx, safe response, and redacted audit preview. The packaged family pages are `http://localhost:8765/enterprise`, `http://localhost:8765/personal-productivity`, and `http://localhost:8765/government-civic`. See [docs/docker-http-bridge.md](docs/docker-http-bridge.md) for `/ready`, `/agent-check`, `/workflow-check`, and `/workflow-batch` examples.

Add AANA to GitHub PR and release workflows with the composite action in [.github/actions/aana-guardrails](.github/actions/aana-guardrails). It packages the code review, deployment readiness, API contract, infrastructure change, and database migration adapters and writes redacted audit/metrics artifacts:

```yaml
- uses: mindbomber/Alignment-Aware-Neural-Architecture--AANA-/.github/actions/aana-guardrails@main
  with:
    fail-on: candidate-block
```

See [docs/github-action.md](docs/github-action.md) and [examples/github-actions/aana-guardrails.yml](examples/github-actions/aana-guardrails.yml).

To try adapter gallery demos in a browser, open the local playground:

```powershell
python scripts/run_playground.py
```

Then visit `http://localhost:8765/playground`. You can also deep-link from the gallery, for example `http://localhost:8765/playground?adapter=email_send_guardrail`. The playground lets you pick an adapter, edit the candidate answer or action, and inspect violations, AIx, the safe response, and the redacted audit record. See [docs/web-playground.md](docs/web-playground.md).

To try everyday irreversible-action demos for email, files, calendar, purchase/booking, and research grounding:

```powershell
python scripts/run_local_demos.py
```

Then visit `http://localhost:8765/demos`. The demos use synthetic evidence and the same Workflow Contract/audit path as the bridge, so non-engineers can see how AANA blocks or revises risky actions in a few minutes. See [docs/local-desktop-browser-demos.md](docs/local-desktop-browser-demos.md).

Run AANA in observe-only shadow mode before changing production behavior:

```powershell
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl --shadow-mode
python scripts/aana_cli.py audit-metrics --audit-log eval_outputs/audit/shadow/aana-shadow.jsonl
```

Shadow telemetry is redacted and reports would-pass, would-revise, would-defer, and would-refuse counts. See [docs/shadow-mode.md](docs/shadow-mode.md).

Use the Adapter Integration SDK when calling AANA from apps without hand-building JSON:

```python
import aana

client = aana.AANAClient(shadow_mode=True)
request = client.workflow_request(
    adapter="research_summary",
    request="Answer using Source A.",
    candidate="Unsupported claim [Source C].",
    evidence=client.evidence("Source A: Evidence is incomplete.", source_id="source-a"),
)
result = client.workflow_check(request)
```

The TypeScript SDK lives in [sdk/typescript](sdk/typescript). See [docs/adapter-integration-sdk.md](docs/adapter-integration-sdk.md).

Workflow Contract routes are available at `POST /validate-workflow`, `POST /workflow-check`, `POST /validate-workflow-batch`, and `POST /workflow-batch`.

Run synthetic starter pilot kits for realistic enterprise, personal productivity, and civic/government scenarios without private data:

```powershell
python scripts/run_starter_pilot_kit.py --kit all
```

The command writes materialized Workflow Contract requests, redacted audit logs, audit metrics, JSON reports, and Markdown reports under `eval_outputs/starter_pilot_kits/`. See [docs/starter-pilot-kits.md](docs/starter-pilot-kits.md).

Run controlled design-partner pilot bundles when you are ready to collect reviewer friction and adoption blockers:

```powershell
python scripts/run_design_partner_pilots.py --pilot all
```

This writes redacted audit, metrics, dashboard, drift, reviewer, field-notes, and feedback-template artifacts for enterprise, developer/tooling, personal productivity, and civic/government-style pilots. See [docs/design-partner-pilots.md](docs/design-partner-pilots.md).

For OpenClaw-style agents, start with the no-code plugin pack in [examples/openclaw/aana-guardrail-pack-plugin](examples/openclaw/aana-guardrail-pack-plugin). Use the live bridge connector in [examples/openclaw/aana-runtime-connector-plugin](examples/openclaw/aana-runtime-connector-plugin) when agents should call a configured AANA runtime before acting. For lower-level integration details, see [docs/agent-integration.md](docs/agent-integration.md), the standalone install boundaries in [docs/openclaw-skill-review-notes.md](docs/openclaw-skill-review-notes.md), the instruction-only guardrail skill in [examples/openclaw/aana-guardrail-skill/SKILL.md](examples/openclaw/aana-guardrail-skill/SKILL.md), the inspectable bundled-helper variant in [examples/openclaw/aana-guardrail-skill-bundled](examples/openclaw/aana-guardrail-skill-bundled), the continuous self-improvement skill in [examples/openclaw/aana-continuous-improvement-skill](examples/openclaw/aana-continuous-improvement-skill), the research-grounding skill in [examples/openclaw/aana-research-grounding-skill](examples/openclaw/aana-research-grounding-skill), the private-data guardrail skill in [examples/openclaw/aana-private-data-guardrail-skill](examples/openclaw/aana-private-data-guardrail-skill), the file-operation guardrail skill in [examples/openclaw/aana-file-operation-guardrail-skill](examples/openclaw/aana-file-operation-guardrail-skill), the code-change review skill in [examples/openclaw/aana-code-change-review-skill](examples/openclaw/aana-code-change-review-skill), the support-reply guardrail skill in [examples/openclaw/aana-support-reply-guardrail-skill](examples/openclaw/aana-support-reply-guardrail-skill), the medical-safety router skill in [examples/openclaw/aana-medical-safety-router-skill](examples/openclaw/aana-medical-safety-router-skill), the purchase-booking guardrail skill in [examples/openclaw/aana-purchase-booking-guardrail-skill](examples/openclaw/aana-purchase-booking-guardrail-skill), the decision-log skill in [examples/openclaw/aana-decision-log-skill](examples/openclaw/aana-decision-log-skill), the financial-safety router skill in [examples/openclaw/aana-financial-safety-router-skill](examples/openclaw/aana-financial-safety-router-skill), the legal-safety router skill in [examples/openclaw/aana-legal-safety-router-skill](examples/openclaw/aana-legal-safety-router-skill), the evidence-first answering skill in [examples/openclaw/aana-evidence-first-answering-skill](examples/openclaw/aana-evidence-first-answering-skill), the tool-use gate skill in [examples/openclaw/aana-tool-use-gate-skill](examples/openclaw/aana-tool-use-gate-skill), the human-review router skill in [examples/openclaw/aana-human-review-router-skill](examples/openclaw/aana-human-review-router-skill), the task-scope guardrail skill in [examples/openclaw/aana-task-scope-guardrail-skill](examples/openclaw/aana-task-scope-guardrail-skill), the agent-memory gate skill in [examples/openclaw/aana-agent-memory-gate-skill](examples/openclaw/aana-agent-memory-gate-skill), the workflow-readiness check skill in [examples/openclaw/aana-workflow-readiness-check-skill](examples/openclaw/aana-workflow-readiness-check-skill), the publication-check skill in [examples/openclaw/aana-publication-check-skill](examples/openclaw/aana-publication-check-skill), the email-send guardrail skill in [examples/openclaw/aana-email-send-guardrail-skill](examples/openclaw/aana-email-send-guardrail-skill), the meeting-summary checker skill in [examples/openclaw/aana-meeting-summary-checker-skill](examples/openclaw/aana-meeting-summary-checker-skill), the calendar scheduling guardrail skill in [examples/openclaw/aana-calendar-scheduling-guardrail-skill](examples/openclaw/aana-calendar-scheduling-guardrail-skill), the message-send guardrail skill in [examples/openclaw/aana-message-send-guardrail-skill](examples/openclaw/aana-message-send-guardrail-skill), the ticket-update checker skill in [examples/openclaw/aana-ticket-update-checker-skill](examples/openclaw/aana-ticket-update-checker-skill), the data-export guardrail skill in [examples/openclaw/aana-data-export-guardrail-skill](examples/openclaw/aana-data-export-guardrail-skill), and the release-readiness check skill in [examples/openclaw/aana-release-readiness-check-skill](examples/openclaw/aana-release-readiness-check-skill).

Create and validate a starter adapter for your own domain:

```powershell
python scripts/aana_cli.py scaffold "insurance claim triage"
python scripts/aana_cli.py validate-adapter examples/insurance_claim_triage_adapter.json
```

The scaffold writes an adapter JSON file, starter prompt, bad candidate, and short adapter README so users can turn one workflow into an AANA test case without starting from a blank page.

Validate the adapter gallery and its expected gate behavior:

```powershell
python scripts/aana_cli.py validate-gallery --run-examples
```

Latest evidence package: [Constraint-Reasoning AANA Evidence Package v0.1](https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/releases/tag/constraint-reasoning-aana-v0.1).

## Related concepts

Verifier-grounded correction, model evaluation, AI alignment, AI safety, hallucination evaluation, constraint satisfaction, abstention, calibrated uncertainty, prompt pressure, originality evaluation, and research software.

## Paper

A draft manuscript describing the AANA framework is available at [papers/aana-framework.pdf](papers/aana-framework.pdf).

A companion theory paper on invisible divergence, layered constraints, and the capability-alignment gap is available at [papers/invisible-divergence-layered-alignment-dynamics.pdf](papers/invisible-divergence-layered-alignment-dynamics.pdf).

The ATS dynamical-alignment manuscript is available at [papers/ATS_Dynamical_Alignment_arXiv.pdf](papers/ATS_Dynamical_Alignment_arXiv.pdf).

Note: these are early research manuscripts. They include theoretical framing, architecture design, evaluation protocol, and simulated or exploratory results. Treat them as research context, not as peer-reviewed benchmark claims.

## Current Finding

The latest tracked constraint-reasoning comparison is documented in [docs/constraint-reasoning-aana-report.md](docs/constraint-reasoning-aana-report.md). In the matched 60-task constraint-reasoning sample, `aana_tools_structured` improves pass rate from `0.458` to `0.983` while increasing capability from `0.662` to `0.922`. Tracked CSV snapshots are in [docs/evidence/](docs/evidence/).

The first everyday application demo is documented in [docs/application-demo-report.md](docs/application-demo-report.md). Across six starter application scenarios, high-pressure AANA-style correction improved model-judged alignment from `0.7600` to `0.8383` and pass rate from `0.5000` to `0.8333`, while also exposing a travel-planning failure case that needs domain-specific verifiers.

That travel failure was turned into the first domain-tool follow-up in [docs/travel-tool-demo-report.md](docs/travel-tool-demo-report.md). The high-pressure travel case moved from prompt-AANA `fail` to travel-tool AANA `pass`, with alignment improving from `0.28` to `0.88`.

The evidence package includes a manifest with source-file hashes, commit SHA, analysis commands, confidence-interval methods, and known caveats: [docs/evidence/manifest.json](docs/evidence/manifest.json).

For the next unified same-run milestone, see [docs/unified-aana-comparison.md](docs/unified-aana-comparison.md).

The small real-output Table 2 pilot is documented in [docs/pilot-table2-report.md](docs/pilot-table2-report.md), with tracked artifacts in [docs/evidence/pilot_table2/](docs/evidence/pilot_table2/). The 20-row spot-check audit is summarized in [docs/pilot-table2-spotcheck-audit.md](docs/pilot-table2-spotcheck-audit.md).

Paper-ready replacement text for the pilot-results section is available in [docs/paper-pilot-results-section.md](docs/paper-pilot-results-section.md), with a LaTeX snippet at [docs/paper-pilot-results-section.tex](docs/paper-pilot-results-section.tex).

## What is in this repo?

- `aana/` - Minimal Python SDK surface for Workflow Contract checks.
- `eval_pipeline/` - Python scripts for generating tasks, running model calls, judging outputs, scoring outputs, analyzing failures, and plotting results.
- `assets/` - Public project images, including the GitHub social preview banner.
- `docs/` - Beginner-oriented explanations of the architecture, evaluation design, and result files.
- `examples/` - Tiny example inputs, outputs, and everyday application scenarios that show the file formats without requiring API calls.
- `papers/` - Public manuscripts connected to the project.
- `scripts/` - Short helper commands for common local workflows.
- `tests/` - Lightweight unit tests for scoring and routing behavior.
- `.env.example` - Template for local environment variables.
- `.gitignore` - Keeps local secrets, generated outputs, caches, and build artifacts out of git.
- `ROADMAP.md` - Public plan for future improvements and research directions.
- `CHANGELOG.md` - Public history of notable changes.
- `eval_outputs/` - Generated locally when you run experiments. It is intentionally ignored because result files can be large, expensive to regenerate, or contain model outputs you may not want to publish automatically.

## How AANA works here

The scripts compare several evaluation modes:

- `baseline` - A direct model answer with no correction loop.
- `weak` / `strong` correction prompts - Prompt-only correction variants.
- AANA loop variants - A generator produces an answer, a verifier scores it against factual, safety, task, and calibration constraints, and a corrector revises or abstains when needed.
- Tool-assisted variants - Deterministic checks catch concrete issues such as budget, dietary, time, manipulation, and format violations.
- Originality variants - Experimental routing and correction modes for testing whether novelty can be improved without breaking constraints.

For a fuller explanation, see:

- `docs/try-demo/index.md` for hosted demos, local demos, catalog browsing, and result interpretation.
- `docs/integrate-runtime/index.md` for Workflow Contract, Agent Event Contract, SDK, bridge, CI, audit, and production-boundary integration.
- `docs/build-adapter/index.md` for adapter design, catalog metadata, AIx tuning, and adapter validation.
- `docs/architecture.md` and `docs/evaluation-design.md` for the research and evaluation background.

## Requirements

- Python 3.10 or newer.
- No API key is needed for sample scoring or deterministic adapter runs.
- An OpenAI API key is needed for the checked-in live model loops by default.
- Responses-compatible endpoints can be configured with `AANA_API_KEY` plus `AANA_BASE_URL` or `AANA_RESPONSES_URL`.
- Anthropic can be used through the native Messages API with `AANA_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`.

The current pipeline only uses the Python standard library, so there is no required `pip install` step for the checked-in scripts.

For the lowest-friction command names, install the repo locally:

```powershell
python -m pip install -e .
```

Then use `aana` instead of `python scripts/aana_cli.py`:

```powershell
aana doctor
aana list
aana run-agent-examples
aana agent-check --event examples/agent_event_support_reply.json
aana-server --host 127.0.0.1 --port 8765
```

## Quick start

1. Clone the repository.

```powershell
git clone https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-.git
cd Alignment-Aware-Neural-Architecture--AANA-
```

Optional, but recommended if agents or shell tools will call AANA often:

```powershell
python -m pip install -e .
```

2. Create a local environment file.

```powershell
Copy-Item .env.example .env
```

Edit `.env` and replace `your_openai_api_key_here` with your real API key. Never commit `.env`.

If you use a Responses-compatible proxy or provider, set:

```text
AANA_PROVIDER=openai
AANA_API_KEY=your_provider_or_proxy_key
AANA_BASE_URL=https://your-provider.example/v1
```

If you use Anthropic, set:

```text
AANA_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Then pass an Anthropic model name to the same live scripts.

Native providers beyond OpenAI-compatible Responses and Anthropic need provider adapters before the live model loops can use them.

3. Generate a local task file.

```powershell
python eval_pipeline/generate_heldout_tasks.py
```

4. Run a tiny dry run without calling the API.

```powershell
python eval_pipeline/run_evals.py --limit 2 --dry-run
python eval_pipeline/score_outputs.py --input eval_outputs/raw_outputs.jsonl --scored eval_outputs/scored_outputs.csv --summary eval_outputs/summary_by_condition.csv
```

5. Run a small live evaluation.

```powershell
python eval_pipeline/run_evals.py --limit 2 --models gpt-5.4-nano
```

This writes JSONL/CSV files under `eval_outputs/`.

## Common workflows

Generate held-out ATS/AANA tasks:

```powershell
python eval_pipeline/generate_heldout_tasks.py --output eval_outputs/heldout/heldout_ats_aana_tasks.jsonl
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

Generate originality tasks and run originality experiments:

```powershell
python eval_pipeline/generate_originality_tasks.py
python eval_pipeline/run_originality_evals.py --limit 4 --conditions baseline originality_aana
```

## Examples and tests

Score the checked-in sample outputs:

```powershell
python eval_pipeline/score_outputs.py --input examples/sample_raw_outputs.jsonl --scored examples/sample_scored_outputs.csv --summary examples/sample_summary_by_condition.csv
```

Run the unit tests:

```powershell
python -m unittest discover -s tests
```

Or use the helper script:

```powershell
python scripts/dev.py check
python scripts/dev.py contract-freeze
python scripts/dev.py production-profiles
python scripts/dev.py production-profiles --audit-log eval_outputs/audit/ci/aana-ci-audit.jsonl --metrics-output eval_outputs/audit/ci/aana-ci-metrics.json
python scripts/dev.py pilot-bundle
python scripts/dev.py pilot-eval
```

`contract-freeze` validates frozen public contracts, schemas, compatibility fixtures, and docs for adapter JSON, Agent Event, Workflow, AIx, evidence, audit, and metrics surfaces.
`production-profiles` is the CI-facing guard for the internal pilot profile: it validates the adapter gallery, contract freeze, AIx tuning, deployment manifest, governance policy, observability policy, evidence registry, evidence integration stubs, exports audit metrics, and runs release-check with a generated redacted audit log. In CI, the audit JSONL and metrics JSON are uploaded as the `aana-production-profile-audit-metrics` artifact.
`pilot-bundle` runs the broader local pilot: multiple agent events, redacted audit logging, metrics export, audit integrity manifest generation, release-check, and production-profile validation.
`pilot-eval` runs the AANA Pilot Evaluation Kit: synthetic and public-data-rehearsal packs for enterprise, personal, civic/government, and public-data pilot planning, with redacted audit logs, audit metrics, and Markdown/JSON reports.

## Important safety notes

- API calls can cost money. Start with `--limit 1` or `--dry-run`.
- Review generated outputs before sharing them publicly.
- Do not commit `.env`, raw private prompts, API keys, or unpublished data.
- The evaluator is experimental research code, not a certified benchmark.

## Limitations

- Current reported scores are model-judged, not human-adjudicated.
- The constraint-reasoning evidence package uses matched task IDs, but `hybrid_gate` rows come from a schema-ablation run.
- The next target is a unified same-run rerun with one frozen task file, model versions, judge model, command log, and dated manifest.

## Repository status

This is an early public research codebase. Interfaces may change as the evaluation design evolves. Contributions that improve documentation, reproducibility, test coverage, or evaluation clarity are welcome.

## License

This project is released under the MIT License. See `LICENSE`.
