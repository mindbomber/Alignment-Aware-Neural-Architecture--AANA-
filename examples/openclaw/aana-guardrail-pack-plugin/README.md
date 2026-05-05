# AANA Guardrail Pack Plugin

Marketplace slug: `aana-guardrail-pack`

This is the first AANA OpenClaw plugin package. It bundles the core AANA guardrail skills as one minimal-runtime pack for agents that need practical safety checks before they act.

The plugin behavior is intentionally instruction-only. It includes a tiny OpenClaw runtime entrypoint only so ClawHub can load the package as a native plugin. That entrypoint registers no tools, starts no services, installs no dependencies, writes no files, stores no memory, and creates no review payloads. Host agents can use the bundled skills as decision procedures, review checklists, and approval gates.

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
- Its runtime entrypoint does not register tools, channels, providers, services, memory, or background work.

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

All bundled skills include the shared AANA Runtime Result Handling rule: proceed only when `gate_decision` is `pass`, `recommended_action` is `accept`, and `aix.hard_blockers` is empty. If the result says `revise`, `ask`, `defer`, or `refuse`, the host agent must route to that behavior instead of continuing the original action.

See `docs/openclaw-skill-conformance.md`, `docs/openclaw-plugin-install-use.md`, and `examples/openclaw/high-risk-workflow-examples.json` in the repository for conformance checks, install/use guidance, and high-risk workflow rehearsals.

## Marketplace Boundary

- `instruction_only_behavior`: true
- `runtime_entrypoint`: `dist/index.js`
- `runtime_registers_capabilities`: false
- `bundled_code`: minimal inert runtime entrypoint only
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
- `dist/index.js`
- `skills/`
- each bundled skill's `manifest.json`
- each bundled skill's `SKILL.md`

The expected package contents are text-only Markdown and JSON files.
