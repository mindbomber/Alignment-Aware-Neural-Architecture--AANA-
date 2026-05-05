# AANA Public Records Privacy Skill

Use this skill when an agent drafts or reviews public-records, FOIA-style, privacy-redaction, records-release, exemption, retention, or response language.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, or execute a checker on its own.

## Core Principle

Public-records candidates must preserve request scope, classification, redaction, destination, authorization, jurisdiction/source-law, and retention/audit requirements. AANA reviews the proposed response; it does not release records.

## Required Checks

- Data classification, request scope, source-law, and access-grant evidence are present.
- Private data, exempt material, protected fields, and unrelated records are redacted.
- Destination and requester authorization are verified.
- Retention and audit policy are followed.
- Candidate avoids final release claims without records-officer approval.
- Reviewer-facing audit trail can explain the route without raw protected records.

## Decision Rule

Accept only redacted, scoped, approved response language. Revise overbroad release or privacy leaks. Ask for missing classification, source-law, scope, authorization, or retention evidence. Defer final release to human review. Refuse unsafe raw-record disclosure.

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
