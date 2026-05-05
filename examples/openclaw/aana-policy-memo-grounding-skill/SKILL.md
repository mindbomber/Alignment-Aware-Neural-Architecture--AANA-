# AANA Policy Memo Grounding Skill

Use this skill when an agent drafts or reviews a policy memo, source-law summary, public-service brief, civic research answer, cited recommendation, or jurisdiction-bounded analysis.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, or execute a checker on its own.

## Core Principle

Policy memo candidates must keep citations, source boundaries, jurisdiction labels, uncertainty, and human-review limits visible. They must not upgrade source excerpts into broad legal, eligibility, compliance, or policy determinations.

## Required Checks

- Retrieved documents, citation index, and source registry are present.
- Jurisdiction and source-law boundaries are labeled.
- Every material claim is supported by an allowed source.
- Unsupported claims are revised, caveated, or removed.
- Uncertainty and source limits are stated.
- Legal-adjacent or final determination language routes to human review.

## Decision Rule

Accept only source-bounded, citation-backed memo language. Revise unsupported claims. Ask for missing sources, jurisdiction, or citation index. Defer legal interpretation, eligibility conclusions, or public-risk claims to authorized review.

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
