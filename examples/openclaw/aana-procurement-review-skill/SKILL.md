# AANA Procurement Review Skill

Use this skill when an agent drafts or reviews procurement, vendor-risk, purchasing, contract, quote, security-review, onboarding, or payment-adjacent recommendations.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, or execute a checker on its own.

## Core Principle

Procurement candidates must separate review guidance from purchase, contract, onboarding, or payment execution. Vendor identity, quote terms, price, data sharing, DPA/security review, and approval authority must be evidence-backed.

## Required Checks

- Vendor identity and quote are verified.
- Price, term, renewal, refundability, and contract terms are not guessed.
- Data sharing and security review status are explicit.
- Required procurement, legal, privacy, security, and budget approvals are present or requested.
- Candidate avoids unauthorized purchase, contract-signing, onboarding, or payment language.
- Confidential contract, tax, banking, and vendor-private data is redacted.

## Decision Rule

Accept only evidence-backed procurement review language. Revise unsupported claims. Ask for missing quote, vendor, DPA/security, or approval evidence. Defer high-risk or approval-dependent recommendations to human review. Refuse direct irreversible procurement actions.

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
