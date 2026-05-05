# AANA Benefits Eligibility Boundary Skill

Use this skill when an agent drafts or reviews benefits, insurance, program intake, eligibility, missing-document, appeal, or case-status language.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, or execute a checker on its own.

## Core Principle

Do not present intake, claim, or case evidence as a final eligibility, coverage, approval, payment, denial, or appeal determination. AANA should preserve policy boundaries, jurisdiction labels, missing-document status, and human-review routing.

## When To Use

Use this skill before sending, saving, publishing, or escalating a candidate that discusses:

- benefits eligibility or coverage,
- required documents,
- jurisdiction or program rules,
- claim status,
- appeal or escalation paths,
- deadlines, obligations, payment, approval, or denial.

## Required Checks

- Evidence includes policy documents, claim or case file summary, and triage policy.
- Jurisdiction and program scope are labeled.
- Candidate avoids final legal, benefits, coverage, or payment determinations.
- Missing documents and uncertainty are explicit.
- Human review is required before final determination language.
- Private medical, financial, identity, or household data is redacted.

## Decision Rule

Accept only narrow, evidence-backed intake or status language. Revise unsupported promises. Ask for missing jurisdiction, policy, or document evidence. Defer final determinations to an authorized reviewer. Refuse unsafe publication or direct-action claims.

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
