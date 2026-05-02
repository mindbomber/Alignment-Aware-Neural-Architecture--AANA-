# OpenClaw Skill Review Notes

The OpenClaw guardrail skill in this repository is an instruction-only integration guide:

- Its package includes `SKILL.md`, `README.md`, and `manifest.json`.
- It does not bundle a Python helper, CLI, installer, dependency lockfile, or executable checker.
- It must not run shell commands, install packages, execute local scripts, infer checker paths, or write event files on its own.
- AANA checks should run only through a separately reviewed interface configured by the user or administrator.

## Provenance Boundary

For standalone skill installation, do not rely on a relative script path or a helper that is absent from the reviewed package. If a deployment wants live AANA checks, configure one reviewed interface outside the skill:

- an approved host tool,
- an in-memory API connector,
- a locally installed AANA package from a pinned release or inspected checkout,
- or a local HTTP bridge with reviewed schema, authentication, logging, and network controls.

If no trusted interface is configured, the skill should use manual review instead of trying to call AANA.

## Decision Boundary

AANA recommendations can ask the agent to accept, revise, retrieve, ask, defer, or refuse. This is intentional for higher-risk actions, but production integrations should treat those recommendations as policy decisions:

- explain the result to the user,
- log the gate decision when appropriate,
- route important refusals or deferrals to human review,
- never use the result to expand scope, access unrelated data, or continue outside the user's request.

## Data Boundary

Prefer in-memory review payloads over files. When files are required by a reviewed integration, keep them temporary, redacted, and scoped to the action being checked.

Do not include:

- API keys or bearer tokens,
- passwords,
- full payment numbers,
- unnecessary account records,
- unrelated private messages,
- full internal records when a yes/no or redacted summary is enough.

If audit records are kept, tell the user where they are stored and what sensitive fields they contain.
