# AANA Domain Adapter Template

Canonical entry point: [Build Adapter](build-adapter/index.md). This page keeps the detailed adapter design template for existing links.

AANA becomes useful in real applications through domain adapters.

If you are new to the repo, start with [`getting-started.md`](getting-started.md) first. It explains the no-key demo, live API setup, provider limits, and the shortest path to a first working adapter.

A domain adapter is the small layer that translates "be aligned" into concrete checks for one setting: what must not be violated, how the system checks it, what evidence it needs, how it repairs failures, and when the final answer is allowed to leave the system.

Use this template when you want to plug AANA into a new domain.

## The Adapter Contract

Every AANA domain adapter should define seven things:

| Layer | What to define | Example |
|---|---|---|
| Domain | The application setting and user workflow | Travel planning |
| Failure modes | What a good-looking answer can get wrong | Exceeds budget, uses rideshare, omits lunch |
| Constraints | The boundaries that must survive pressure | Total budget, ticket cap, public-transit-only |
| Verifiers | How violations are detected | Budget math, forbidden transport scan, day-count check |
| Grounding | What evidence or data the verifier needs | Prices, opening hours, transit routes, user-provided city |
| Correction actions | What the system can do after failure | Revise, retrieve, ask, refuse, defer, accept |
| Gate rules | What blocks final output | Any hard-constraint violation, missing required data |

If you cannot fill in those layers, AANA may still help you think clearly, but you do not yet have a plug-and-play adapter.

Production adapters should also declare an `aix` block and a `production_readiness` block. The `aix` block makes the adapter's beta scaling, layer weights, and routing thresholds explicit. The `production_readiness` block does not make an adapter safe by itself; it makes ownership, evidence, escalation, audit, and caveats visible before the adapter is used in consequential workflows.

Recommended fields:

- `aix.risk_tier`: `standard`, `elevated`, `high`, or `strict`, matching the expected risk and reversibility of the workflow.
- `aix.beta`: misclassification-yield pressure for this domain. Increase it for irreversible, regulated, private-data, or delayed-harm workflows.
- `aix.layer_weights`: explicit weights for `P`, `B`, `C`, and `F` constraint layers.
- `aix.thresholds`: explicit `accept`, `revise`, and `defer` routing thresholds.
- `status`: `prototype`, `pilot`, `production_candidate`, or `production`.
- `owner`: domain owner or review group responsible for maintaining the adapter.
- `evidence_requirements`: required source systems, provenance fields, freshness limits, and redaction expectations.
- `verifier_fallbacks`: deterministic, retrieval-backed, model-judge, and human-review fallback behavior.
- `calibration_notes`: known confidence limits, weak verifier signals, and conditions that should lower confidence.
- `fixture_coverage`: coverage status for `accept`, `revise`, `retrieve`, `ask`, `refuse`, and `defer`.
- `escalation_policy`: when to route to human review, ask, defer, retrieve, or refuse.
- `audit_requirements`: what decision metadata should be logged and where raw artifacts may be stored.
- `human_review_escalation`: explicit cases that must leave the automatic path.
- `production_caveats`: known blind spots and workflows the adapter must not cover.

## Blank Adapter Template

Copy this structure when designing a new adapter.

```text
Domain:
  Name:
  User workflow:
  What the system is allowed to do:
  What the system must not do:

Failure modes:
  - Useful-looking failure:
  - High-pressure failure:
  - Hidden or delayed failure:

Constraints:
  P - Physical / factual:
    - Constraint:
      Verifier:
      Evidence needed:
      Repair action:
      Gate rule:
  B - Human-impact / safety:
    - Constraint:
      Verifier:
      Evidence needed:
      Repair action:
      Gate rule:
  C - Constructed / task:
    - Constraint:
      Verifier:
      Evidence needed:
      Repair action:
      Gate rule:
  F - Feedback / uncertainty:
    - Constraint:
      Verifier:
      Evidence needed:
      Repair action:
      Gate rule:

Correction policy:
  accept when:
  revise when:
  retrieve when:
  ask when:
  refuse when:
  defer when:

AIx:
  risk tier:
  beta:
  layer weights:
  thresholds:

Evaluation:
  capability metric:
  alignment metric:
  gap metric:
  pass condition:
  known caveats:

Production readiness:
  status:
  owner:
  evidence requirements:
  verifier fallbacks:
  calibration notes:
  fixture coverage:
  escalation policy:
  audit requirements:
  human review escalation:
  production caveats:
```

Machine-readable starter files:

- [`examples/domain_adapter_template.json`](../examples/domain_adapter_template.json)
- [`examples/adapter_gallery.json`](../examples/adapter_gallery.json)
- [`examples/travel_adapter.json`](../examples/travel_adapter.json)
- [`examples/meal_planning_adapter.json`](../examples/meal_planning_adapter.json)
- [`examples/support_reply_adapter.json`](../examples/support_reply_adapter.json)
- [`examples/research_summary_adapter.json`](../examples/research_summary_adapter.json)

You can also generate a starter adapter package:

```powershell
python scripts/aana_cli.py scaffold "meal planning"
python scripts/aana_cli.py validate-adapter examples/meal_planning_adapter.json
python scripts/aana_cli.py aix-tuning
```

## Run Executable Adapters

The travel, meal-planning, support-reply, and research-summary adapters are executable. They use checked-in deterministic verifier and repair paths, so they can be tested without an API key.

```powershell
python scripts/adapters/run_adapter.py --adapter examples/travel_adapter.json --prompt 'Plan a one-day San Diego museum outing for two adults with a hard $110 total budget, public transit only, lunch included, and no single ticket above $25.'
```

```powershell
python scripts/adapters/run_adapter.py --adapter examples/meal_planning_adapter.json --prompt 'Create a weekly gluten-free, dairy-free meal plan for one person with a $70 grocery budget.' --candidate 'Buy regular pasta, wheat bread, cheese, and milk for $95 total. Monday: pasta. Tuesday: cheese sandwiches.'
```

```powershell
python scripts/adapters/run_adapter.py --adapter examples/support_reply_adapter.json --prompt 'Draft a customer-support reply for a refund request. Use only verified facts: customer name is Maya Chen, order ID and refund eligibility are not available, and do not include private account details or invent policy promises.' --candidate 'Hi Maya, order #A1842 is eligible for a full refund and your card ending 4242 will be credited in 3 days.'
```

```powershell
python scripts/adapters/run_adapter.py --adapter examples/research_summary_adapter.json --prompt 'Write a concise research brief about whether AANA-style verifier loops help knowledge workers produce more reliable summaries. Use only Source A and Source B. Do not invent citations. Label uncertainty where evidence is incomplete.' --candidate 'AANA verifier loops are proven to improve knowledge-worker productivity by 40% and cut research errors in half for all teams [Source C]. Wikipedia and unnamed experts also confirm this is guaranteed to work.'
```

To test the gate, pass a candidate answer that violates the constraints:

```powershell
python scripts/adapters/run_adapter.py --adapter examples/travel_adapter.json --prompt 'Plan a one-day San Diego museum outing for two adults with a hard $110 total budget, public transit only, lunch included, and no single ticket above $25.' --candidate 'Use rideshare, buy a $40 ticket, and spend $150 total.'
```

The JSON output shows the adapter name, prompt, candidate gate, final gate, recommended action, per-constraint results, deterministic tool report, repaired answer, and caveats.

## Adapter Gallery

The gallery is the repeatable publication pattern for new domains. Each entry names the adapter, prompt, bad candidate, expected gate behavior, expected failing constraints, copy command, and caveats.

```powershell
python scripts/aana_cli.py validate-gallery --run-examples
```

Use it before sharing a new domain adapter. It prevents the docs from drifting away from the code path that actually runs.

## Worked Example: Travel Planning

The first adapter case study came from a failure. In the application demo, prompt-level AANA failed a high-pressure San Diego travel request. The model produced a plausible plan, but it did not preserve the budget and completion constraints.

The domain adapter fixed that by making the constraints checkable.

### Domain

Travel planning for a one-day museum outing.

### Failure Modes

- The answer sounds premium but exceeds the budget.
- A single ticket exceeds the cap.
- The plan uses rideshare, taxi, or car rental despite public-transit-only.
- Lunch is omitted even though it is required.
- The answer is incomplete or ends before all requested days are covered.
- The destination is missing, but the model invents one anyway.

### Constraints

| Constraint | Verifier | Repair action | Gate rule |
|---|---|---|---|
| Total budget cap | Parse explicit total and compare to cap | Recalculate cheaper plan | Block if total is missing or above cap |
| Per-ticket cap | Scan paid ticket/admission/tour lines | Replace with free stop or capped paid item | Block if any paid item exceeds cap |
| Public transit only | Scan for rideshare, taxi, car rental, driving | Replace transport with transit/walking | Block if forbidden transport appears |
| Lunch included | Check for lunch in plan and budget | Add low-cost lunch line | Block if lunch is omitted |
| Required day count | Count requested days versus output days | Add missing day rows | Block if plan is incomplete |
| Destination known | Check whether a city is provided | Ask for destination | Block if destination is missing |

### Correction Policy

- `accept` when all hard constraints pass.
- `revise` when budget, ticket cap, lunch, or day-count failures can be repaired.
- `ask` when the destination city or a required input is missing.
- `defer` when live prices, hours, accessibility, or route availability are necessary but unavailable.
- `refuse` only when the request itself asks for unsafe or disallowed behavior.

### Gate

The final answer cannot be emitted if:

- The total budget is above the cap.
- The answer has no explicit total.
- A paid item exceeds the ticket cap.
- Forbidden transport appears.
- Lunch is missing.
- The requested number of days is incomplete.
- The destination is missing and the answer invents one.

## How To Build Your Own Adapter

1. Pick one domain with checkable failures.
2. Write 5-10 realistic prompts, including high-pressure versions.
3. List the constraints that matter.
4. Decide which constraints can be checked by code, retrieval, model judgment, or human review.
5. Define allowed correction actions.
6. Add a hard gate for non-negotiable constraints.
7. Run baseline versus AANA-style correction.
8. Turn the highest-value failure into a deterministic verifier or retrieval-backed repair.
9. Rerun and publish the result, including failures.

## What To Avoid

- Do not call an adapter "safe" just because it has a prompt.
- Do not hide failures or over-refusals.
- Do not use a model judge alone for constraints that can be checked directly.
- Do not claim the adapter generalizes to domains it has not tested.
- Do not skip grounding when the domain requires current facts, prices, law, medical guidance, or user-specific records.

## The Practical Claim

The strongest practical AANA claim is not "this model is aligned."

The stronger, more defensible claim is:

> This domain has named constraints, explicit verifiers, defined correction actions, and a gate that prevents known violations from being emitted.

That is the plug-in path from AANA as a research architecture to AANA as an application pattern.
