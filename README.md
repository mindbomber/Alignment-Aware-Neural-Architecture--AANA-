# Alignment-Aware Neural Architecture (AANA) Evaluation Pipeline

[![CI](https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/actions/workflows/ci.yml/badge.svg)](https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Status: Alpha Research](https://img.shields.io/badge/status-alpha%20research-orange.svg)](ROADMAP.md)

🌐 Public project site: https://mindbomber.github.io/Alignment-Aware-Neural-Architecture--AANA-/

![AANA repository social preview](assets/github-social-preview.png)

This repository contains a small Python evaluation pipeline for testing Alignment-Aware Neural Architecture (AANA) ideas. In plain language, it runs prompt-based stress tests against language models, compares baseline answers with AANA-style correction loops, scores the outputs, and generates CSV/SVG summaries that help show where capability and alignment diverge.

The project is meant for researchers, builders, and curious beginners who want a reproducible starting point for experimenting with verifier-grounded correction, constraint preservation, abstention, and originality in AI assistant outputs.

Start here if you want the lowest-friction path from idea to working demo: [docs/getting-started.md](docs/getting-started.md).

## Why this matters

Language models can produce answers that look capable while quietly violating important constraints: inventing unsupported facts, exceeding budgets, ignoring safety limits, guessing private information, or becoming manipulative under pressure. AANA experiments measure that failure mode directly by comparing capability and alignment scores across baseline, correction, verifier-loop, tool-assisted, and originality conditions.

## Where AANA is useful

AANA is strongest where failures are mechanically checkable. The point is not to make the model "more careful" by asking nicely. The point is to give the system a correction path that cannot hand-wave constraints away.

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

For the shortest practical path, see [docs/getting-started.md](docs/getting-started.md). For the platform boundary, see [docs/aana-workflow-contract.md](docs/aana-workflow-contract.md). For a broader productive-work path across research, analysis, writing, and knowledge workflows, see [docs/productive-workflows.md](docs/productive-workflows.md). For a more detailed bridge from lab evidence to everyday systems, see [docs/application-playbook.md](docs/application-playbook.md). To plug AANA into your own domain, start with [docs/domain-adapter-template.md](docs/domain-adapter-template.md), then copy [examples/domain_adapter_template.json](examples/domain_adapter_template.json). The executable example adapters are [examples/travel_adapter.json](examples/travel_adapter.json), [examples/meal_planning_adapter.json](examples/meal_planning_adapter.json), [examples/support_reply_adapter.json](examples/support_reply_adapter.json), and [examples/research_summary_adapter.json](examples/research_summary_adapter.json), all runnable through [scripts/run_adapter.py](scripts/run_adapter.py). The adapter gallery in [examples/adapter_gallery.json](examples/adapter_gallery.json) lists runnable domains, prompts, bad candidates, expected gate behavior, and copyable commands. Starter application prompts are in [examples/application_scenarios.jsonl](examples/application_scenarios.jsonl).

## Who this is for

- AI safety and alignment researchers studying correction loops and evaluation design.
- LLM evaluation builders who need reproducible prompt, scoring, and plotting workflows.
- Product engineers testing whether assistants preserve user constraints under pressure.
- Students and independent researchers learning how model-evaluation pipelines are structured.

## Try it in 60 seconds

Run the checked-in sample workflow. It uses no API key and makes no live model calls.

```powershell
python scripts/dev.py sample
```

List the runnable adapter examples:

```powershell
python scripts/aana_cli.py list
```

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
```

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

Workflow Contract routes are available at `POST /validate-workflow`, `POST /workflow-check`, `POST /validate-workflow-batch`, and `POST /workflow-batch`.

For OpenClaw-style agents, see [docs/agent-integration.md](docs/agent-integration.md), the standalone install boundaries in [docs/openclaw-skill-review-notes.md](docs/openclaw-skill-review-notes.md), the instruction-only guardrail skill in [examples/openclaw/aana-guardrail-skill/SKILL.md](examples/openclaw/aana-guardrail-skill/SKILL.md), the inspectable bundled-helper variant in [examples/openclaw/aana-guardrail-skill-bundled](examples/openclaw/aana-guardrail-skill-bundled), the continuous self-improvement skill in [examples/openclaw/aana-continuous-improvement-skill](examples/openclaw/aana-continuous-improvement-skill), the research-grounding skill in [examples/openclaw/aana-research-grounding-skill](examples/openclaw/aana-research-grounding-skill), the private-data guardrail skill in [examples/openclaw/aana-private-data-guardrail-skill](examples/openclaw/aana-private-data-guardrail-skill), the file-operation guardrail skill in [examples/openclaw/aana-file-operation-guardrail-skill](examples/openclaw/aana-file-operation-guardrail-skill), and the code-change review skill in [examples/openclaw/aana-code-change-review-skill](examples/openclaw/aana-code-change-review-skill).

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

- `docs/getting-started.md`
- `docs/architecture.md`
- `docs/evaluation-design.md`
- `docs/aana-workflow-contract.md`
- `docs/productive-workflows.md`
- `docs/application-playbook.md`
- `docs/domain-adapter-template.md`
- `docs/application-demo-report.md`
- `docs/travel-tool-demo-report.md`
- `docs/results-interpretation.md`
- `docs/unified-aana-comparison.md`

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
```

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
