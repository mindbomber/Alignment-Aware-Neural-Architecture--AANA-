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

## Bundled Helper Variant

A separate package is available at `examples/openclaw/aana-guardrail-skill-bundled/` for users or reviewers who want an inspectable helper bundled with the skill package.

That variant includes:

- `manifest.json`,
- `README.md`,
- `SKILL.md`,
- `bin/aana_guardrail_check.py`,
- `schemas/review-payload.schema.json`,
- `examples/redacted-review-payload.json`,
- `requirements.txt`.

The bundled helper has no third-party dependencies and is limited to posting a redacted review payload to a separately reviewed AANA bridge on `localhost`. It blocks remote URLs and obvious secret-like payload keys. It still requires a trusted AANA bridge to be running; the helper is not the AANA policy engine.

## Continuous Improvement Skill

A separate instruction-only continuous improvement skill is available at `examples/openclaw/aana-continuous-improvement-skill/`.

That skill is designed for agent reflection and workflow improvement without autonomous self-modification. It does not bundle code, install dependencies, persist memory, write files, or call services. It requires explicit approval before improvements affect future behavior, memory, files, tools, policies, or permissions.

## Private Data Guardrail Skill

A separate instruction-only private data guardrail skill is available at `examples/openclaw/aana-private-data-guardrail-skill/`.

That skill is designed to stop agents from exposing unnecessary or unauthorized account, billing, payment, health, legal, personal, or sensitive business data. It does not bundle code, install dependencies, persist memory, write files, or call services. It asks agents to minimize private details, redact raw identifiers and secrets, avoid invented account facts, ask when authorization is unclear, and defer high-impact or irreversible privacy-sensitive actions to a verified system or human review.

## File Operation Guardrail Skill

A separate instruction-only file operation guardrail skill is available at `examples/openclaw/aana-file-operation-guardrail-skill/`.

That skill is designed to check before agents delete, move, rename, overwrite, publish, upload, export, or bulk-edit user files. It does not bundle code, install dependencies, persist memory, write files, inspect the filesystem, or call services. It asks agents to verify exact target paths, keep operations inside the approved scope, prefer dry-runs, diffs, backups, and copy-before-move workflows, and require explicit approval for destructive, recursive, cross-folder, publishing, uploading, or broad edit actions.

## Code Change Review Skill

A separate instruction-only code change review skill is available at `examples/openclaw/aana-code-change-review-skill/`.

That skill is designed to gate code edits, commits, pull requests, test claims, scope creep, secret leakage, and destructive commands. It does not bundle code, install dependencies, persist memory, write files, inspect repositories, or call services. It asks agents to keep diffs scoped to the user request, report only checks that actually ran, block secrets and private data in code or logs, require approval before commits and pull requests, and defer high-risk security, migration, release, or deployment changes to a verified review path.

## Support Reply Guardrail Skill

A separate instruction-only support reply guardrail skill is available at `examples/openclaw/aana-support-reply-guardrail-skill/`.

That skill is designed to review customer support replies before agents send invented facts, refund or credit promises, policy overclaims, or unnecessary private data. It does not bundle code, install dependencies, persist memory, write files, inspect accounts, or call services. It asks agents to separate customer-provided facts from verified records, avoid unapproved refunds or policy exceptions, minimize private data, and ask or defer when account evidence or authorization is missing.

## Medical Safety Router Skill

A separate instruction-only medical safety router skill is available at `examples/openclaw/aana-medical-safety-router-skill/`.

That skill is designed to route medical and wellness questions into safer answer boundaries before agents overdiagnose, overtreat, miss emergencies, or expose private health data. It does not bundle code, install dependencies, persist memory, write files, inspect health records, or call services. It asks agents to state uncertainty, avoid diagnosis and treatment overclaims, route urgent warning signs to emergency care, refer higher-risk medication or symptom questions to qualified clinicians or pharmacists, and minimize private health information.

## Purchase Booking Guardrail Skill

A separate instruction-only purchase booking guardrail skill is available at `examples/openclaw/aana-purchase-booking-guardrail-skill/`.

That skill is designed to gate purchases, bookings, reservations, subscriptions, renewals, and irreversible financial actions before agents create charges, deposits, recurring commitments, cancellation penalties, or hard-to-undo reservations. It does not bundle code, install dependencies, persist memory, write files, inspect accounts, or call services. It asks agents to verify exact item, vendor, dates, quantities, total cost, fees, refundability, cancellation and renewal terms, payment privacy, and explicit user approval before final submission.

## Decision Log Skill

A separate instruction-only decision log skill is available at `examples/openclaw/aana-decision-log-skill/`.

That skill is designed to produce compact audit records for important agent decisions: what was checked, what failed, what changed, and what risk remains. It does not bundle code, install dependencies, persist memory, write files, inspect systems, or call services. It asks agents to log only checks that actually happened, mark failed or unclear checks, record corrections made after review, minimize sensitive data, and avoid implying compliance or validation that was not observed.

## Financial Safety Router Skill

A separate instruction-only financial safety router skill is available at `examples/openclaw/aana-financial-safety-router-skill/`.

That skill is designed to route investment, tax, budgeting, debt, credit, insurance, retirement, and purchase advice into safer boundaries before agents make unsupported claims or omit material risk disclosure. It does not bundle code, install dependencies, persist memory, write files, inspect accounts, or call services. It asks agents to separate general education from personalized advice, avoid guaranteed returns or tax outcomes, disclose material risks and uncertainty, minimize private financial data, and refer high-impact tax, legal, investment, or debt cases to qualified professionals.

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
