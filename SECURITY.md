# Security Policy

## Supported versions

This repository is early research code. Security fixes should target the default branch unless a maintained release branch is added later.

## Reporting a vulnerability

Please report security issues privately to the repository owner instead of opening a public issue when the report includes:

- API keys, tokens, or credential exposure.
- Private prompts, private datasets, or unpublished model outputs.
- A way to make the pipeline leak secrets or execute unintended commands.

## Secret handling

- Put local secrets in `.env`.
- Do not commit `.env`.
- Do not paste real API keys into `.env.example`, docs, issues, or pull requests.
- Review generated outputs before publishing because model responses can include sensitive or unwanted text.
