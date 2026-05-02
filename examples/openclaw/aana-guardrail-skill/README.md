# AANA Guardrail Skill Package

This OpenClaw-style package is intentionally instruction-only.

It contains:

- `SKILL.md`: the guardrail instructions.
- `manifest.json`: review metadata that declares the package boundaries.

It does not contain:

- a Python helper,
- an executable CLI,
- an installer,
- dependency files,
- local tool code,
- event-file templates.

## Security Boundary

Do not resolve or execute a checker from a relative workspace path. This package must not run shell commands, install dependencies, write event files, or infer local helper paths.

Live AANA checks require a separately reviewed interface configured by the user or administrator, such as an approved host tool, approved in-memory API connector, or separately reviewed local AANA installation.

If no trusted interface is configured, use manual review.

## Data Boundary

Use minimal redacted review payloads. Do not include API keys, bearer tokens, passwords, full payment numbers, unnecessary account records, or unrelated private messages.

Prefer in-memory review calls. This skill package should not create event files. If a deployment requires files, that file-handling workflow must be reviewed and configured outside this skill.
