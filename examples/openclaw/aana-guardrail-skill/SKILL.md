# AANA Guardrail Skill For OpenClaw-Style Agents

Use this skill when a user asks the agent to produce or execute an action that may violate hard constraints, depend on missing evidence, expose private information, or require a safe correction path.

This skill is an integration guide. It does not include the AANA checker implementation by itself. Treat AANA decisions as advisory unless the user has installed AANA from a trusted source and the checker path has been inspected.

## External Dependency

The checker is the AANA Python package, not this skill file. Install it separately from a pinned, trusted source before use:

```powershell
python -m pip install "git+https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-.git@<trusted-commit-or-release>"
aana doctor
```

If the user cannot provide a trusted commit, release, or local checkout for inspection, do not run the checker.

## When To Call AANA

Call AANA before:

- sending customer-support replies, emails, or messages,
- using private account, billing, payment, or personal data,
- making refund, eligibility, booking, purchase, or policy promises,
- editing, deleting, moving, or publishing user files,
- committing or publishing code,
- answering from incomplete evidence, citations, or source notes,
- doing anything the user cannot easily undo.

## Before Running Local Code

Do not run a local AANA command automatically.

Before invoking AANA, confirm all of the following:

- The user explicitly approves running the local checker for this task.
- AANA is installed from a trusted, inspectable source, preferably this repository: `https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-`.
- The command resolves to the reviewed AANA package, not an unrelated local script elsewhere in the workspace.
- `aana doctor` or the equivalent checked command reports a healthy local installation.
- The event file contains only the minimum information needed for the check.

Prefer the installed console command:

```powershell
aana agent-check --event .aana/agent_event.json
```

If the package is not installed, stop and ask the user to install or inspect the full AANA repository first. Do not execute a Python checker script from this skill package.

## Event Shape

Store temporary event files under a controlled local folder such as `.aana/`. Do not include secrets, API keys, full payment numbers, access tokens, unnecessary account records, or private data that is not required to evaluate the candidate action.

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

After the check, delete temporary event files unless the user asks to keep them for audit or debugging:

```powershell
Remove-Item -LiteralPath .aana\agent_event.json
```

## Decision Rule

- If `gate_decision` is `pass` and `recommended_action` is `accept`, proceed.
- If `recommended_action` is `revise`, use `safe_response` or revise the plan before acting.
- If `recommended_action` is `ask`, ask the user for the missing information.
- If `recommended_action` is `defer`, route to a stronger tool, human review, or verified system.
- If `recommended_action` is `refuse`, do not execute the candidate action.
- If the checker is unavailable, untrusted, or cannot be inspected, do not treat its output as authoritative; ask the user how to proceed or use manual review.

## Default Adapter Mapping

- Customer support, refunds, private account details: `support_reply`
- Travel or booking plans: `travel_planning`
- Food, grocery, allergy, dietary plans: `meal_planning`
- Research briefs, cited summaries, knowledge synthesis: `research_summary`

If no adapter fits, scaffold one:

```powershell
aana scaffold "new workflow name"
```

Only run scaffolding after user approval, because it writes local files.
