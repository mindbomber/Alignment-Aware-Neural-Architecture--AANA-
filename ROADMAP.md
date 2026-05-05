# Roadmap

This roadmap describes useful next steps for the public AANA evaluation pipeline. It is not a promise of specific release dates.

## Near term

- Add more unit tests for deterministic constraint tools.
- Add fixture-based tests for JSONL and CSV workflows.
- Improve beginner examples with one complete end-to-end no-API walkthrough.
- Add clearer failure messages when input files are missing.
- Review task schemas and document required versus optional fields.
- Follow the production-readiness track in `docs/production-readiness-plan.md` before using AANA for consequential workflows.

## Medium term

- Add optional linting and formatting checks.
- Separate reusable library code from command-line scripts.
- Add more plotting examples and interpretation notes.
- Add more originality-router tests and fixture data.
- Create small public benchmark snapshots with reviewed, non-sensitive outputs.

## Research directions

- Compare model-judge scores against human-reviewed samples.
- Measure how alignment scores change under stronger pressure prompts.
- Expand deterministic checks for budget, time, dietary, privacy, and manipulation constraints.
- Study when originality improves useful novelty and when it breaks viability.
- Explore clearer calibration metrics for abstention, uncertainty, and unsupported premises.

## Non-goals for now

- This repo is not a production safety system.
- This repo is not a certified benchmark.
- This repo should not include private prompts, API keys, or unreviewed sensitive outputs.
- This repo should stay easy to run with standard-library Python where practical.

## Production readiness

The production conversion plan lives in `docs/production-readiness-plan.md`. The local repository now includes a stable contract surface, a Python/CLI/HTTP integration path, optional POST authentication for the local bridge, request-size limits, and tests for those safeguards. Full production status still requires a target deployment, authenticated evidence sources, observability, domain-owner review, and human-escalation policy.
