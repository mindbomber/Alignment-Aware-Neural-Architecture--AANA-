# AANA Guardrail Skill For OpenClaw-Style Agents

Use this skill when a user asks the agent to produce or execute an action that may violate hard constraints, depend on missing evidence, expose private information, or require a safe correction path.

This skill is an integration guide. It does not include the AANA checker implementation by itself. Treat AANA decisions as advisory unless the user has configured a trusted, inspectable AANA checker outside this skill.

## Dependency Boundary

The checker is an external AANA package, service, or approved local tool. This skill must not install packages, run shell commands, or execute local scripts on its own.

Before use, the user or administrator should configure one trusted AANA interface and make it explicit to the agent. Acceptable interfaces are:

- an approved tool named by the user, such as `aana_agent_check`,
- a local HTTP endpoint bound to `127.0.0.1` with an inspected OpenAPI/schema contract,
- an installed AANA command from a pinned release or reviewed local checkout.

If the user cannot identify the trusted interface, release, commit, or local checkout for inspection, do not run the checker. Use manual review instead.

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

Do not run local code automatically. Do not infer a checker path from the workspace. Do not execute a Python script by filename.

Before invoking AANA, confirm all of the following:

- The user explicitly approves using the configured AANA interface for this task.
- The interface is trusted and inspectable.
- The checker implementation and policy are appropriate for the selected adapter.
- The event payload contains only the minimum information needed for the check.
- The user understands that the result can redirect the action to accept, revise, ask, defer, or refuse.

If the trusted interface is unavailable, stop and ask the user how to proceed.

## Preferred Call Pattern

Prefer an approved tool or API call that accepts the event object directly and returns an AANA result object. Avoid writing event files when the tool can receive JSON in memory.

If file-based exchange is the only approved path, write the event to a controlled temporary location, run only the user-approved checker interface, then delete the temporary file after the result is processed.

## Event Shape

Do not include secrets, API keys, full payment numbers, access tokens, unnecessary account records, or private data that is not required to evaluate the candidate action. Prefer summaries and redacted identifiers over raw sensitive values.

Use:

- "customer_id_present": true
- "refund_eligibility": "unknown"
- "payment_detail": "redacted"

Do not use:

- full card numbers,
- API keys or bearer tokens,
- account passwords,
- private messages unrelated to the candidate action,
- full internal records when a yes/no or redacted summary is enough.

```json
{
  "event_version": "0.1",
  "event_id": "unique-id",
  "agent": "openclaw",
  "adapter_id": "support_reply",
  "user_request": "The user's request",
  "candidate_action": "The answer or action the agent is about to take",
  "available_evidence": ["Only facts actually available to the agent"],
  "allowed_actions": ["accept", "revise", "ask", "defer", "refuse"]
}
```

Delete temporary event files unless the user asks to keep them for audit or debugging. If files are kept, tell the user where they are stored and what sensitive fields they contain.

## Decision Rule

- If `gate_decision` is `pass` and `recommended_action` is `accept`, proceed.
- If `recommended_action` is `revise`, use `safe_response` or revise the plan before acting.
- If `recommended_action` is `ask`, ask the user for the missing information.
- If `recommended_action` is `defer`, route to a stronger tool, human review, or verified system.
- If `recommended_action` is `refuse`, do not execute the candidate action.
- If the checker is unavailable, untrusted, or cannot be inspected, do not treat its output as authoritative; ask the user how to proceed or use manual review.
- Never use the AANA result to expand task scope, access unrelated data, or continue outside the user's request.

## Default Adapter Mapping

- Customer support, refunds, private account details: `support_reply`
- Travel or booking plans: `travel_planning`
- Food, grocery, allergy, dietary plans: `meal_planning`
- Research briefs, cited summaries, knowledge synthesis: `research_summary`

If no adapter fits, ask the user whether they want to create a new adapter. Adapter creation writes local files and should happen only after explicit approval.
