# OpenClaw Skill Review Notes

The OpenClaw guardrail skill in this repository is an instruction-only integration guide:

- Its package includes `SKILL.md`, `README.md`, and `manifest.json`.
- It does not bundle a Python helper, CLI, installer, dependency lockfile, or executable checker.
- It must not run shell commands, install packages, execute local scripts, infer checker paths, or write event files on its own.
- AANA checks should run only through a separately reviewed interface configured by the user or administrator.

## Guardrail Pack Plugin

A no-code OpenClaw plugin is available at `examples/openclaw/aana-guardrail-pack-plugin/`.

The plugin bundles 13 instruction-only AANA skills behind one `openclaw.plugin.json` manifest: workflow readiness, task scope, tool use, human review, private data, file operations, data export, email send, message send, publication, evidence-first answering, code-change review, and decision logging.

The plugin package is intentionally text-only. It does not bundle executable code, install dependencies, run scripts, call services, write files, write event files, persist memory, or require a local helper path. Host agents should treat the bundled skills as advisory or approval-gated procedures according to the plugin configuration and the user's installation policy.

## Runtime Connector Plugin

A separate OpenClaw runtime connector is available at `examples/openclaw/aana-runtime-connector-plugin/`.

Unlike the guardrail pack, the runtime connector registers optional OpenClaw tools. Those tools call a user-configured loopback AANA bridge for health checks, agent-event validation, agent-event gating, workflow validation, and workflow gating. The connector does not ship a Python helper, model provider, bridge server, background service, dependency installer, memory store, or policy engine.

The connector should be enabled only when the user or administrator has separately reviewed and started the AANA bridge. Review payloads should stay minimal and redacted, and tool access should remain opt-in for agents that need live gate decisions.

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

## Legal Safety Router Skill

A separate instruction-only legal safety router skill is available at `examples/openclaw/aana-legal-safety-router-skill/`.

That skill is designed to route legal, regulatory, compliance, contract, immigration, criminal, family, employment, housing, court, dispute, and rights-related questions into safer boundaries before agents provide unauthorized legal advice, omit jurisdiction caveats, or make unsupported legal claims. It does not bundle code, install dependencies, persist memory, write files, inspect records, or call services. It asks agents to separate general legal information from legal advice, ask or caveat when jurisdiction is missing, avoid invented laws, deadlines, rights, or outcomes, minimize private legal data, and refer high-impact or deadline-sensitive matters to qualified legal help.

## Evidence First Answering Skill

A separate instruction-only evidence first answering skill is available at `examples/openclaw/aana-evidence-first-answering-skill/`.

That skill is designed to force answer drafts to separate known facts, assumptions, missing evidence, and next retrieval steps before agents produce confident answers. It does not bundle code, install dependencies, persist memory, write files, retrieve evidence, or call services. It asks agents to classify important claims by evidence status, mark missing evidence explicitly, revise unsupported claims, ask or retrieve when evidence gaps block the answer, and defer high-risk conclusions that depend on unavailable evidence.

## Tool Use Gate Skill

A separate instruction-only tool use gate skill is available at `examples/openclaw/aana-tool-use-gate-skill/`.

That skill is designed to check whether tool calls are necessary, scoped, authorized, and safe before agents use capabilities that read, write, send, publish, delete, buy, book, deploy, or affect external state. It does not bundle code, install dependencies, persist memory, write files, inspect systems, or call services. It asks agents to define exact target scope, verify user authorization, minimize tool inputs and outputs, prefer read-only or preview steps before state changes, and defer or refuse unauthorized, destructive, financial, privileged, external-send, or high-impact tool use.

## Human Review Router Skill

A separate instruction-only human review router skill is available at `examples/openclaw/aana-human-review-router-skill/`.

That skill is designed to route uncertain, high-impact, irreversible, low-evidence, private, external, financial, legal, medical, production, and policy-sensitive actions to user, human, professional, or admin review before agents proceed. It does not bundle code, install dependencies, persist memory, write files, inspect systems, or call services. It asks agents to classify impact, evidence, authorization, and reversibility, define the reviewer decision needed, minimize sensitive review context, and not proceed until required review is complete.

## Task Scope Guardrail Skill

A separate instruction-only task scope guardrail skill is available at `examples/openclaw/aana-task-scope-guardrail-skill/`.

That skill is designed to keep agents inside the current user request, use only task-relevant data, ask before expanding scope, treat optional work as a suggestion, and stop once the request is complete. It does not bundle code, install dependencies, persist memory, write files, inspect systems, or call services. It asks agents to identify the current request, define the smallest useful completion target, classify the next action, check data relevance, verify authorization, and avoid continuing background work after completion.

## Agent Memory Gate Skill

A separate instruction-only agent memory gate skill is available at `examples/openclaw/aana-agent-memory-gate-skill/`.

That skill is designed to require approval before storing, reusing, editing, importing, exporting, or deleting user memory. It does not bundle code, install dependencies, persist memory, write files, inspect systems, or call services. It asks agents to classify the memory operation, source, relevance, sensitivity, approval status, and lifecycle; avoid storing secrets or unnecessary sensitive data; use temporary context when memory is not needed; and never treat silence as approval for memory changes.

## Workflow Readiness Check Skill

A separate instruction-only workflow readiness check skill is available at `examples/openclaw/aana-workflow-readiness-check-skill/`.

That skill is designed to check whether an agent has enough information, permission, tools, evidence, and safe boundaries before starting a workflow. It does not bundle code, install dependencies, persist memory, write files, inspect systems, or call services. It asks agents to identify the workflow, intended outcome, completion criteria, required information, authorization, tool access, evidence state, risk level, and first safe step before starting.

## Publication Check Skill

A separate instruction-only publication check skill is available at `examples/openclaw/aana-publication-check-skill/`.

That skill is designed to check posts, blogs, reports, docs, website updates, release notes, marketplace listings, and other public-facing content before publication. It does not bundle code, install dependencies, persist memory, write files, inspect systems, or call services. It asks agents to check approval, material claim evidence, privacy redaction, third-party asset permissions, links, downloads, audience risk, and review needs before publishing.

## Email Send Guardrail Skill

A separate instruction-only email send guardrail skill is available at `examples/openclaw/aana-email-send-guardrail-skill/`.

That skill is designed to verify exact recipients, CC/BCC exposure, tone, private data, attachments, claims, promises, and explicit send approval before email is sent. It does not bundle code, install dependencies, persist memory, write files, inspect systems, send email, or call services. It asks agents to treat drafting as separate from sending, redact sensitive content, verify attachments, check unsupported commitments, and block unsafe or unauthorized email sends.

## Meeting Summary Checker Skill

A separate instruction-only meeting summary checker skill is available at `examples/openclaw/aana-meeting-summary-checker-skill/`.

That skill is designed to check meeting summaries, notes, action items, owners, dates, decisions, and attributed claims against transcript, notes, chat, agenda, calendar, or other available evidence. It does not bundle code, install dependencies, persist memory, write files, inspect systems, access transcripts, or call services. It asks agents to mark inferred or uncertain items, avoid invented commitments, redact private meeting content, and route high-impact notes to review before sharing.

## Calendar Scheduling Guardrail Skill

A separate instruction-only calendar scheduling guardrail skill is available at `examples/openclaw/aana-calendar-scheduling-guardrail-skill/`.

That skill is designed to check attendees, timezone, date, duration, recurrence, agenda, private notes, visibility, and approval before calendar changes. It does not bundle code, install dependencies, persist memory, write files, inspect systems, create events, or call services.

## Message Send Guardrail Skill

A separate instruction-only message send guardrail skill is available at `examples/openclaw/aana-message-send-guardrail-skill/`.

That skill is designed to check chat destinations, recipients, channel visibility, broadcast scope, tone, private data, attachments, claims, and approval before messages are posted. It does not bundle code, install dependencies, persist memory, write files, inspect systems, send messages, or call services.

## Ticket Update Checker Skill

A separate instruction-only ticket update checker skill is available at `examples/openclaw/aana-ticket-update-checker-skill/`.

That skill is designed to check support, issue, CRM, and task updates for exact ticket scope, evidence, owner/status changes, visibility, private data, and approval. It does not bundle code, install dependencies, persist memory, write files, inspect systems, update tickets, or call services.

## Data Export Guardrail Skill

A separate instruction-only data export guardrail skill is available at `examples/openclaw/aana-data-export-guardrail-skill/`.

That skill is designed to check export scope, destination, privacy, redaction, field minimization, and approval before files, records, datasets, logs, reports, or account data are exported or shared. It does not bundle code, install dependencies, persist memory, write files, inspect systems, export data, or call services.

## Release Readiness Check Skill

A separate instruction-only release readiness check skill is available at `examples/openclaw/aana-release-readiness-check-skill/`.

That skill is designed to check release targets, tags, changelogs, docs, artifacts, tests, approval, compatibility, rollback, and public claims before a release. It does not bundle code, install dependencies, persist memory, write files, inspect systems, create tags, publish releases, or call services.

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
