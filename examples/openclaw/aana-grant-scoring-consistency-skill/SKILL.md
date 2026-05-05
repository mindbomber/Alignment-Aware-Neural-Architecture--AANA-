# AANA Grant Scoring Consistency Skill

Use this skill when an agent drafts or reviews grant/application screening, eligibility notes, rubric scoring, reviewer feedback, award recommendations, missing-document messages, or deadline language.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, or execute a checker on its own.

## Core Principle

Grant and application candidates must stay inside the published program rules, submitted documents, and rubric. They must not create unsupported eligibility, score, award, denial, or deadline claims.

## Required Checks

- Program rules and deadline evidence are present.
- Submitted-document completeness is verified.
- Rubric criteria are applied consistently and only to job/program-relevant evidence.
- Candidate distinguishes screening notes from final award or denial decisions.
- Missing documents, uncertainty, or reviewer conflicts route to ask or human review.
- Applicant private data and reviewer-only notes are minimized.

## Decision Rule

Accept only evidence-backed screening or rubric-consistency language. Revise unsupported score or eligibility claims. Ask for missing application documents or program rules. Defer final award, denial, exception, or appeal language to authorized review.

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
