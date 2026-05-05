# AANA Guardrail Pack Plugin

Marketplace slug: `aana-guardrail-pack`

This is the first AANA OpenClaw plugin package. It bundles the core AANA guardrail skills as one no-code pack for agents that need practical safety checks before they act.

The plugin is intentionally instruction-only. It does not install dependencies, run scripts, call services, write files, store memory, or create review payloads. Host agents can use the bundled skills as decision procedures, review checklists, and approval gates.

## Included Skills

- `aana-workflow-readiness-check`
- `aana-task-scope-guardrail`
- `aana-tool-use-gate`
- `aana-human-review-router`
- `aana-private-data-guardrail`
- `aana-file-operation-guardrail`
- `aana-data-export-guardrail`
- `aana-email-send-guardrail`
- `aana-message-send-guardrail`
- `aana-publication-check`
- `aana-evidence-first-answering`
- `aana-code-change-review`
- `aana-decision-log`

## What It Helps Agents Do

- Check whether a workflow has enough information, permission, tools, and evidence before starting.
- Stay inside the user's requested scope instead of expanding the task silently.
- Gate tool calls, file operations, exports, sends, posts, and other external actions.
- Protect private account, billing, payment, health, legal, personal, and business data.
- Separate known facts from assumptions, unsupported claims, and missing evidence.
- Review code changes, test claims, commits, and publishing actions before they affect users.
- Produce compact, redacted decision notes for important agent choices.

## What It Does Not Do

- It does not run local programs.
- It does not install packages.
- It does not call an AANA server.
- It does not write logs, memories, files, or event payloads.
- It does not replace user approval, expert review, or domain-specific policy.

## Safety Model

AANA treats alignment as a maintained process: generate a candidate action, check it against the relevant constraints, correct or ask when evidence is missing, and gate the result before action.

For OpenClaw agents, that means the plugin should be used before higher-risk steps such as:

- sending an email or chat message,
- exporting private data,
- deleting or overwriting files,
- publishing public content,
- making a code change or release claim,
- using a tool with external side effects,
- continuing work after the original task is complete.

## Marketplace Boundary

- `instruction_only`: true
- `bundled_code`: false
- `installs_dependencies`: false
- `executes_commands`: false
- `writes_files`: false
- `writes_event_files`: false
- `persists_memory`: false
- `calls_services`: false
- `network_access`: false
- `bundled_skill_count`: 13

## Local Review Checklist

Before enabling this plugin, inspect:

- `package.json`
- `openclaw.plugin.json`
- `skills/`
- each bundled skill's `manifest.json`
- each bundled skill's `SKILL.md`

The expected package contents are text-only Markdown and JSON files.
