# AANA Getting Started

This guide is for builders who want to see whether AANA can fit a real workflow, not just read the research framing.

The fastest path is:

1. Run the no-key sample.
2. Run the no-key travel adapter.
3. Pick one workflow from your own life or product.
4. Write its hard constraints as an adapter.
5. Add verifiers for the constraints that can be checked.
6. Decide what the system should do after failure: accept, revise, retrieve, ask, refuse, or defer.

## What You Can Do Without An API Key

You can test the local scoring and adapter flow without calling any model provider.

Run the sample scoring workflow:

```powershell
python scripts/dev.py sample
```

Run the first executable adapter:

```powershell
python scripts/run_adapter.py --adapter examples/travel_adapter.json --prompt 'Plan a one-day San Diego museum outing for two adults with a hard $110 total budget, public transit only, lunch included, and no single ticket above $25.'
```

Test a broken candidate and watch the gate repair it:

```powershell
python scripts/run_adapter.py --adapter examples/travel_adapter.json --prompt 'Plan a one-day San Diego museum outing for two adults with a hard $110 total budget, public transit only, lunch included, and no single ticket above $25.' --candidate 'Use rideshare, skip lunch, buy a $40 ticket, and spend $150 total.'
```

That is the current lowest-friction demo of AANA as a plug-in pattern: adapter JSON, deterministic checks, correction action, and a final gate result.

## What Requires An API Key

Live generation, verifier-model scoring, correction loops, and judge-model scoring require a model API key.

The checked-in scripts use the OpenAI Responses API shape by default. Configure it like this:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```text
OPENAI_API_KEY=your_openai_api_key_here
```

Run a tiny live evaluation:

```powershell
python eval_pipeline/run_evals.py --limit 1 --models gpt-5.4-nano
```

Start with `--limit 1` because live calls can cost money.

## Can I Use A Non-OpenAI API Key?

Today there are three tiers of support:

| Path | Status | What it means |
|---|---|---|
| No-key local tools | Supported | Sample scoring and deterministic adapters run without any model provider. |
| OpenAI Responses API | Supported | Live generator, verifier, corrector, and judge calls use `OPENAI_API_KEY`. |
| Responses-compatible endpoint | Configurable | If another provider or proxy exposes the same `/responses` request and response shape, set `AANA_API_KEY` and `AANA_BASE_URL` or `AANA_RESPONSES_URL`. |
| Native Anthropic, Gemini, local Ollama, etc. | Not implemented yet | These need provider-specific request/response adapters before they can run live model loops. |

Responses-compatible configuration:

```text
AANA_API_KEY=your_provider_or_proxy_key
AANA_BASE_URL=https://your-provider.example/v1
```

Or set the exact endpoint:

```text
AANA_API_KEY=your_provider_or_proxy_key
AANA_RESPONSES_URL=https://your-provider.example/v1/responses
```

This is not a guarantee that every provider works. The endpoint must accept the Responses-style payload used by the scripts and return compatible output text.

## How To Apply AANA To A Daily Workflow

Pick a workflow where a polished answer can still be wrong in a checkable way.

Good first domains:

- Travel plans with budgets, ticket caps, transit rules, dates, and required stops.
- Meal plans with allergens, grocery budgets, forbidden ingredients, and diet rules.
- Research summaries with allowed sources, citation requirements, and uncertainty labels.
- Support or intake workflows with required fields, permissions, escalation rules, and templates.
- Scheduling, study, fitness, or operations plans with hard time limits and completion requirements.

The key question is not "Can the model answer?" The better question is:

> What would make this answer unacceptable even if it sounds useful?

Turn each unacceptable condition into an adapter constraint.

## The Adapter Checklist

Use [`domain-adapter-template.md`](domain-adapter-template.md) and [`examples/domain_adapter_template.json`](../examples/domain_adapter_template.json).

For each domain, define:

| Adapter piece | What users should write |
|---|---|
| Domain | The workflow and what the assistant is allowed to do. |
| Failure modes | The ways a useful-looking answer can break reality, policy, safety, or task rules. |
| Constraints | The hard and soft boundaries that must survive pressure. |
| Verifiers | Code, retrieval, model judgment, or human review that can detect violations. |
| Grounding | Data sources needed to check the answer. |
| Correction policy | What happens after failure: revise, retrieve, ask, refuse, defer, accept. |
| Gate | What blocks the final answer. |
| Metrics | Capability, alignment, pass rate, over-refusal, latency, and caveats. |

## First Milestone For A New Domain

Do not start with a big benchmark. Start with one executable case.

1. Write one realistic high-pressure prompt.
2. Write one bad candidate answer that breaks the constraints.
3. Make the verifier catch the bad candidate.
4. Make the repair path produce a passing answer.
5. Save the prompt, candidate, verifier result, final answer, and caveats.
6. Only then expand to 5-10 prompts.

This is how AANA moves from a lab result to something users can plug into their own workflow.

## What To Tell Users

Use this framing when explaining AANA to non-specialists:

> AANA is a way to make AI answers pass through the checks your workflow already cares about. It does not make a model perfect. It makes the system name the constraints, check them, repair what can be repaired, and block or ask when a confident answer would be fake.

That is the accessibility goal: users should see their own daily constraints in the system, not just an abstract alignment theory.
