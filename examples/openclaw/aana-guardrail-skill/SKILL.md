# AANA Guardrail Skill For OpenClaw-Style Agents

Use this skill when a user asks the agent to produce or prepare an action that may violate hard constraints, depend on missing evidence, expose private information, or require a safe correction path.

This skill is an integration guide. It does not include the AANA checker implementation by itself. Treat AANA decisions as advisory unless the user has configured a trusted, inspectable AANA checker outside this skill.

## Submission Note

This package intentionally contains only guardrail instructions and review metadata. See `manifest.json` for the machine-readable package boundary. It does not bundle a helper script, Python CLI, installer, dependency lockfile, or executable checker. Do not resolve or execute any local checker based on a path mentioned by another workspace file. AANA checks may be used only through a separately reviewed interface configured by the user or administrator.

## Dependency Boundary

The checker is an external AANA package, service, or approved tool configured outside this skill. This skill must not install packages, run shell commands, execute scripts, infer file paths, or write event files on its own.

Before use, the user or administrator should configure one trusted AANA interface and make it explicit to the agent. Acceptable interfaces are approved host tools or API connectors whose implementation, permissions, and data handling have been reviewed outside this skill.

If the user cannot identify the trusted interface, do not call a checker. Use manual review instead.

## When To Call AANA

Call AANA before:

- sending customer-support replies, emails, or messages,
- using private account, billing, payment, or personal data,
- making refund, eligibility, booking, purchase, or policy promises,
- editing, deleting, moving, or publishing user files,
- committing or publishing code,
- answering from incomplete evidence, citations, or source notes,
- doing anything the user cannot easily undo.

## Before Calling AANA

Do not run local code automatically. Do not infer a checker path from the workspace. Do not execute scripts by filename.

Before invoking AANA, confirm all of the following:

- The user explicitly approves using the configured AANA interface for this task.
- The interface is trusted and inspectable.
- The checker implementation and policy are appropriate for the selected adapter.
- The review payload contains only the minimum information needed for the check.
- The user understands that the result can redirect the action to accept, revise, ask, defer, or refuse.

If the trusted interface is unavailable, stop and ask the user how to proceed.

## Preferred Call Pattern

Prefer an approved in-memory tool or API call that accepts a minimal review payload and returns an AANA result object. Do not create local event files from this skill.

If the only available integration requires files, stop and ask the user or administrator to provide a reviewed file-handling workflow outside this skill.

## Review Payload

Do not include secrets, API keys, full payment numbers, access tokens, unnecessary account records, or private data that is not required to evaluate the planned action. Prefer summaries and redacted identifiers over raw sensitive values.

Prefer fields like:

- "customer_id_present": true
- "refund_eligibility": "unknown"
- "payment_detail": "redacted"
- "candidate_summary": "support reply would promise a refund"
- "evidence_summary": "refund eligibility is unavailable"

Avoid:

- full card numbers,
- API keys or bearer tokens,
- account passwords,
- private messages unrelated to the candidate action,
- full internal records when a yes/no or redacted summary is enough.

Do not store review payloads unless the user explicitly asks for an audit record. If an audit record is required, store only redacted summaries and tell the user where the record is kept.

## Decision Rule

- Read `aix` when present. Treat `aix.decision` as the score-derived route for the final gated output and `candidate_aix.decision` as the score-derived route for the proposed candidate.
- Never proceed when `aix.hard_blockers` is non-empty, even if the numeric score is high.
- If `gate_decision` is `pass` and `recommended_action` is `accept`, proceed.
- If `recommended_action` is `revise`, use `safe_response` or revise the plan before acting.
- If `recommended_action` is `ask`, ask the user for the missing information.
- If `recommended_action` is `defer`, route to a stronger tool, human review, or verified system.
- If `recommended_action` is `refuse`, pause the candidate action, explain the reason, and ask for user or human review when the decision affects important work.
- If the checker is unavailable, untrusted, or cannot be inspected, do not treat its output as authoritative; ask the user how to proceed or use manual review.
- Never use the AANA result to expand task scope, access unrelated data, or continue outside the user's request.

## Default Adapter Mapping

- Customer support, refunds, private account details: `support_reply`
- Travel or booking plans: `travel_planning`
- Food, grocery, allergy, dietary plans: `meal_planning`
- Research briefs, cited summaries, knowledge synthesis: `research_summary`

If no adapter fits, ask the user whether they want to create a new adapter. Adapter creation writes local files and should happen only after explicit approval.
