# AANA Application Playbook

The current evidence shows that AANA-style correction can preserve explicit constraints better than direct answers in a controlled evaluation setting. The next question is how to use that pattern outside the lab.

For the lowest-friction setup path, start with [`getting-started.md`](getting-started.md). This playbook explains where AANA fits; the getting-started guide shows how to run the no-key demo, configure live model calls, and turn one workflow into an adapter.

AANA is useful when an AI system faces a request that has real constraints attached to it: budgets, time windows, facts, citations, permissions, safety boundaries, privacy limits, eligibility rules, required formats, or impossible premises. The architecture turns those constraints into checks and routes the answer through a correction path before it reaches the user.

In plain language:

1. Generate a candidate answer.
2. Verify it against the constraints that matter.
3. Ground it in evidence or structured data when needed.
4. Repair what can be repaired.
5. Ask, refuse, defer, or escalate when repair would be fake.
6. Let the answer through only when it passes the gate.

This is different from simply prompting a model to be careful. AANA makes the system show its work: what was checked, what failed, what changed, and why the final answer should be trusted more than the first draft.

## Strong application patterns

### Budgeted planning assistants

Examples: travel planners, shopping assistants, event planners, operations schedulers.

Typical constraints:

- Total budget and per-item caps.
- Time windows and deadlines.
- Route, distance, or transport limits.
- Required and forbidden items.
- Required output format.

Why AANA helps:

A direct model answer can sound useful while quietly exceeding the budget or inventing feasible timing. AANA can check the math, detect missing totals, repair the plan, or ask for clarification when the constraints cannot all be satisfied.

### Meal and health-adjacent planners

Examples: recipe planners, grocery lists, cafeteria menus, dietary preference assistants.

Typical constraints:

- Allergens and forbidden ingredients.
- Dietary restrictions.
- Nutrition targets.
- Ingredient availability.
- Safety disclaimers and scope limits.

Why AANA helps:

The model should not optimize for tasty suggestions while ignoring a hard exclusion. AANA can verify ingredients, flag unsafe substitutions, and refuse or defer medical claims that require a professional source.

### Grounded research copilots

Examples: literature summaries, policy brief drafts, market research, source-grounded Q&A.

Typical constraints:

- Claims must be supported by available sources.
- Citations must exist.
- Fictional or impossible facts must be rejected.
- Uncertainty must be labeled.
- Private or unavailable information must not be guessed.

Why AANA helps:

Research assistants often fail by sounding confident. AANA can separate useful synthesis from unsupported claims and route missing evidence to retrieval, caveats, abstention, or clarification.

### Workflow readiness agents

Examples: intake assistants, support triage, report drafting, internal operations agents.

Typical constraints:

- Required fields are present.
- The user has permission.
- Evidence or source records are available.
- Escalation rules are followed.
- The output is formatted for the next system.

Why AANA helps:

An agent should not prepare an action just because the request sounds complete. AANA can check readiness before drafting, routing, or handing off work.

### Math, feasibility, and consistency checks

Examples: tutoring assistants, cost estimators, logistics checks, engineering planning aids.

Typical constraints:

- Arithmetic must balance.
- Units must be consistent.
- Physical or timing requirements must be possible.
- Intermediate assumptions must be visible.

Why AANA helps:

The architecture can make calculation and feasibility checks first-class verifiers instead of hoping the model notices its own mistake.

## Where AANA is weaker

AANA is not a universal safety solution. It helps least when:

- Success is mostly subjective taste.
- There is no stable verifier.
- The relevant harm is delayed or hidden.
- The system cannot observe the information needed to check the constraint.
- There is no useful correction action after failure.

In those cases, AANA can still help document assumptions and route to human review, but it should not be presented as proof that the system is aligned.

## Turning an application into an AANA design

For a full plug-in guide, use [`domain-adapter-template.md`](domain-adapter-template.md). It includes a blank adapter contract and a filled travel-planner example.

For each target application, define:

| Question | Design output |
|---|---|
| What can go wrong? | Failure modes |
| Which constraints matter? | Constraint map |
| Can each constraint be checked? | Verifier stack |
| What evidence is needed? | Retrieval or grounding module |
| What should happen after failure? | Correction policy |
| When should the answer be blocked? | Alignment gate |
| How will success be measured? | Capability, alignment, and gap metrics |

The most important practical rule is simple: if you cannot name the constraint, detect the violation, and choose a correction action, AANA should be treated as exploratory design rather than a validated safety layer.

## Starter experiments

The file `examples/application_scenarios.jsonl` contains small scenario prompts for everyday domains. They are not benchmark claims. They are starting points for showing how AANA can move from controlled evidence into application-specific tests.

The first small real-output run is summarized in [`application-demo-report.md`](application-demo-report.md). It found a positive high-pressure alignment signal for AANA-style correction, while also showing that travel planning needs stronger domain-specific verifiers before it should be treated as robust. The first failure-to-tool follow-up is documented in [`travel-tool-demo-report.md`](travel-tool-demo-report.md).

Recommended next experiment:

1. Freeze 5-10 scenarios per domain.
2. Run direct baseline answers and AANA-style correction on the same prompts.
3. Score capability and alignment separately.
4. Report where AANA repairs the answer, where it over-refuses, and where it still misses constraints.
5. Publish the task file, outputs, scoring rubric, and caveats.
