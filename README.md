# Alignment-Aware Neural Architecture (AANA) Evaluation Pipeline

[![CI](https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/actions/workflows/ci.yml/badge.svg)](https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Status: Alpha Research](https://img.shields.io/badge/status-alpha%20research-orange.svg)](ROADMAP.md)

This repository contains a small Python evaluation pipeline for testing Alignment-Aware Neural Architecture (AANA) ideas. In plain language, it runs prompt-based stress tests against language models, compares baseline answers with AANA-style correction loops, scores the outputs, and generates CSV/SVG summaries that help show where capability and alignment diverge.

The project is meant for researchers, builders, and curious beginners who want a reproducible starting point for experimenting with verifier-grounded correction, constraint preservation, abstention, and originality in AI assistant outputs.

## What is in this repo?

- `eval_pipeline/` - Python scripts for generating tasks, running model calls, judging outputs, scoring outputs, analyzing failures, and plotting results.
- `docs/` - Beginner-oriented explanations of the architecture, evaluation design, and result files.
- `examples/` - Tiny example inputs and outputs that show the file formats without requiring API calls.
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

- `docs/architecture.md`
- `docs/evaluation-design.md`
- `docs/results-interpretation.md`

## Requirements

- Python 3.10 or newer.
- An OpenAI API key for scripts that call the Responses API.

The current pipeline only uses the Python standard library, so there is no required `pip install` step for the checked-in scripts.

## Quick start

1. Clone the repository.

```powershell
git clone https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-.git
cd Alignment-Aware-Neural-Architecture--AANA-
```

2. Create a local environment file.

```powershell
Copy-Item .env.example .env
```

Edit `.env` and replace `your_openai_api_key_here` with your real API key. Never commit `.env`.

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

## Repository status

This is an early public research codebase. Interfaces may change as the evaluation design evolves. Contributions that improve documentation, reproducibility, test coverage, or evaluation clarity are welcome.

## License

This project is released under the MIT License. See `LICENSE`.
