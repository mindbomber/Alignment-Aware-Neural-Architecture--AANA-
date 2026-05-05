# AANA Public Statement Risk Skill

Use this skill when an agent drafts or reviews civic press statements, public updates, public website copy, public notices, incident updates, program announcements, or external communications.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, or execute a checker on its own.

## Core Principle

Public statements must be accurate, source-backed, privacy-safe, approved, and scoped to the communication authority. AANA should catch unsupported claims, legal or benefits promises, private data, public-risk wording, and missing approval before publication.

## Required Checks

- Draft, source list, and approval policy are present.
- Claims are supported and citations or source references match the draft.
- Private, protected, or internal-only data is redacted.
- Legal, benefits, procurement, incident, or public-risk statements route to human review.
- Dates, deadlines, status, and commitments are not overclaimed.
- Publication approval is explicit before any public release.

## Decision Rule

Accept only approved, sourced, privacy-safe public statements. Revise unsupported or overbroad claims. Ask for missing sources or approval. Defer legal, benefits, procurement, or high-impact statements to authorized review. Refuse publication that leaks protected data or misstates public facts.

## AANA Runtime Result Handling

When a configured AANA checker or bridge returns a result, treat it as an action gate, not as background advice:

- Proceed only when `gate_decision` is `pass`, `recommended_action` is `accept`, and `aix.hard_blockers` is empty.
- If `recommended_action` is `revise`, use the safe response or revise the plan, then recheck before acting.
- If `recommended_action` is `ask`, ask the user for the missing information before acting.
- If `recommended_action` is `defer`, route to stronger evidence, a domain owner, a review queue, or a human reviewer.
- If `recommended_action` is `refuse`, do not perform the unsafe part of the action.
- If `aix.decision` disagrees with `recommended_action`, follow the stricter route.
- Treat `candidate_aix` as the risk score for the proposed candidate before correction, not as permission to act.
- Never use a high numeric `aix.score` to override hard blockers, missing evidence, or a non-accept recommendation.

For audit needs, store only redacted decision metadata such as adapter id, `gate_decision`, `recommended_action`, AIx summary, hard blockers, violation codes, and fingerprints. Do not store raw prompts, candidates, private records, evidence, secrets, safe responses, or outputs from the skill.
