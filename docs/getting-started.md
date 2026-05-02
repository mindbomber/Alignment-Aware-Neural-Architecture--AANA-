# AANA Getting Started

This guide is for builders who want to see whether AANA can fit a real workflow, not just read the research framing.

The fastest path is:

1. Run the no-key sample.
2. List the runnable adapter gallery.
3. Run one gallery adapter.
4. Scaffold an adapter for one workflow from your own life or product.
5. Validate the adapter contract.
6. Replace the starter prompt and bad candidate with a real case.
7. Add verifiers for the constraints that can be checked.
8. Decide what the system should do after failure: accept, revise, retrieve, ask, refuse, or defer.

## Command Hub

Use `scripts/aana_cli.py` for the lowest-friction path:

```powershell
python scripts/aana_cli.py list
python scripts/aana_cli.py doctor
python scripts/aana_cli.py run travel_planning
python scripts/aana_cli.py run meal_planning
python scripts/aana_cli.py run support_reply
python scripts/aana_cli.py run research_summary
python scripts/aana_cli.py validate-workflow --workflow examples/workflow_research_summary.json
python scripts/aana_cli.py workflow-check --workflow examples/workflow_research_summary.json
python scripts/aana_cli.py validate-workflow-batch --batch examples/workflow_batch_productive_work.json
python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json
python scripts/aana_cli.py workflow-check --adapter research_summary --request "Write a concise research brief. Use only Source A and Source B. Label uncertainty." --candidate "AANA improves productivity by 40% for all teams [Source C]." --evidence "Source A: AANA makes constraints explicit." --evidence "Source B: Source coverage can be incomplete." --constraint "Do not invent citations." --constraint "Do not add unsupported numbers."
python scripts/aana_cli.py validate-gallery --run-examples
python scripts/aana_cli.py validate-event --event examples/agent_event_support_reply.json
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json
python scripts/aana_cli.py run-agent-examples
python scripts/aana_cli.py scaffold-agent-event support_reply --output-dir examples/agent_events
python scripts/aana_cli.py agent-schema agent_event
python scripts/aana_cli.py policy-presets
python scripts/aana_server.py --host 127.0.0.1 --port 8765
python scripts/aana_cli.py scaffold "insurance claim triage"
```

After local install, use the shorter command form:

```powershell
python -m pip install -e .
aana doctor
aana list
aana run-agent-examples
aana scaffold-agent-event support_reply --output-dir examples/agent_events
aana-server --host 127.0.0.1 --port 8765
```

The `doctor` command checks Python version, gallery health, executable adapter examples, agent event examples, schemas, and optional live provider configuration. Missing API keys are warnings because local demos do not need a provider account.

The older scripts still work directly, but the command hub is the easiest starting point.

The command hub wraps:

- `scripts/run_adapter.py`
- `scripts/validate_adapter.py`
- `scripts/validate_adapter_gallery.py`
- `scripts/new_adapter.py`

For AI-agent integrations, see [`agent-integration.md`](agent-integration.md).

For app, notebook, and workflow integrations, use the AANA Workflow Contract in [`aana-workflow-contract.md`](aana-workflow-contract.md). The shortest Python surface is:

```python
import aana

result = aana.check(
    adapter="research_summary",
    request="Write a concise research brief. Use only Source A and Source B. Label uncertainty.",
    candidate="AANA improves productivity by 40% for all teams [Source C].",
    evidence=["Source A: AANA makes constraints explicit.", "Source B: Source coverage can be incomplete."],
    constraints=["Do not invent citations.", "Do not add unsupported numbers."],
)

result_from_file = aana.check_file("examples/workflow_research_summary.json")
batch_result = aana.check_batch_file("examples/workflow_batch_productive_work.json")
```

If your agent can call Python directly, use `eval_pipeline.agent_api.check_event(event)` instead of spawning a process. The runnable example is [`../examples/agent_api_usage.py`](../examples/agent_api_usage.py).

Before an agent starts calling AANA, validate the event shape with `python scripts/aana_cli.py validate-event --event <event.json>`. This catches missing adapter IDs, missing prompts, malformed evidence lists, and unsupported actions before the workflow runs. To see the pattern across domains, run `python scripts/aana_cli.py run-agent-examples`; it checks the support, travel, meal-planning, and research-summary event pack under `examples/agent_events/`.

To create a new event without hand-writing JSON, run `python scripts/aana_cli.py scaffold-agent-event <adapter_id>`. Start with `support_reply`, `travel_planning`, `meal_planning`, or `research_summary`, then replace `candidate_action` and `available_evidence` with the real planned action and verified context from your agent.

If your agent framework prefers HTTP tools or webhooks, run the local bridge with `python scripts/aana_server.py`, POST the event JSON to `http://127.0.0.1:8765/validate-event`, then POST the same event to `http://127.0.0.1:8765/agent-check`. General app workflows can use `POST /validate-workflow`, `POST /workflow-check`, `POST /validate-workflow-batch`, and `POST /workflow-batch` with the workflow request shape.

The bridge also exposes `http://127.0.0.1:8765/openapi.json` and JSON Schema routes under `/schemas` for tools that can import machine-readable contracts. After `python -m pip install -e .`, you can start it with `aana-server`.

Direct script examples are below for users who want the underlying pieces.

## What You Can Do Without An API Key

You can test the local scoring and adapter flow without calling any model provider.

Run the sample scoring workflow:

```powershell
python scripts/dev.py sample
```

Run the executable travel adapter:

```powershell
python scripts/run_adapter.py --adapter examples/travel_adapter.json --prompt 'Plan a one-day San Diego museum outing for two adults with a hard $110 total budget, public transit only, lunch included, and no single ticket above $25.'
```

Then run the meal-planning adapter. This shows the same gate-and-repair pattern outside travel: a candidate plan breaks budget and dietary constraints, and the runner rewrites it into a gated answer.

```powershell
python scripts/run_adapter.py --adapter examples/meal_planning_adapter.json --prompt 'Create a weekly gluten-free, dairy-free meal plan for one person with a $70 grocery budget.' --candidate 'Buy regular pasta, wheat bread, cheese, and milk for $95 total. Monday: pasta. Tuesday: cheese sandwiches.'
```

Run the support-reply adapter to see a non-planning workflow: the candidate invents account facts and leaks private payment detail, while the gate rewrites toward secure verification.

```powershell
python scripts/run_adapter.py --adapter examples/support_reply_adapter.json --prompt 'Draft a customer-support reply for a refund request. Use only verified facts: customer name is Maya Chen, order ID and refund eligibility are not available, and do not include private account details or invent policy promises.' --candidate 'Hi Maya, order #A1842 is eligible for a full refund and your card ending 4242 will be credited in 3 days.'
```

Run the research-summary adapter to see AANA in a knowledge workflow: the candidate invents a citation, adds unsupported numbers, and erases uncertainty; the gate rewrites it into a source-bounded summary.

```powershell
python scripts/run_adapter.py --adapter examples/research_summary_adapter.json --prompt 'Write a concise research brief about whether AANA-style verifier loops help knowledge workers produce more reliable summaries. Use only Source A and Source B. Do not invent citations. Label uncertainty where evidence is incomplete.' --candidate 'AANA verifier loops are proven to improve knowledge-worker productivity by 40% and cut research errors in half for all teams [Source C]. Wikipedia and unnamed experts also confirm this is guaranteed to work.'
```

Validate the adapter gallery when you want to check every published plug-in example at once:

```powershell
python scripts/aana_cli.py validate-gallery --run-examples
```

Test a broken candidate and watch the gate repair it:

```powershell
python scripts/run_adapter.py --adapter examples/travel_adapter.json --prompt 'Plan a one-day San Diego museum outing for two adults with a hard $110 total budget, public transit only, lunch included, and no single ticket above $25.' --candidate 'Use rideshare, buy a $40 ticket, and spend $150 total.'
```

That is the current lowest-friction demo of AANA as a plug-in pattern: adapter JSON, deterministic checks, correction action, and a final gate result.

Scaffold your own adapter package:

```powershell
python scripts/aana_cli.py scaffold "meal planning"
```

Validate it:

```powershell
python scripts/aana_cli.py validate-adapter examples/meal_planning_adapter.json
```

The scaffold gives you an adapter JSON file, a starter prompt, a deliberately bad candidate, and a short adapter README. Validation checks required fields, constraint layers, verifier types, correction actions, gate rules, metrics, and obvious placeholder text.

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

Yes. The live-call layer now has a small provider interface. Today there are four tiers of support:

| Path | Status | What it means |
|---|---|---|
| No-key local tools | Supported | Sample scoring and deterministic adapters run without any model provider. |
| OpenAI Responses API | Supported | Set `AANA_PROVIDER=openai` and `OPENAI_API_KEY`. This is the default. |
| Responses-compatible endpoint | Configurable | Set `AANA_PROVIDER=openai`, then set `AANA_API_KEY` and `AANA_BASE_URL` or `AANA_RESPONSES_URL`. |
| Anthropic Messages API | Supported | Set `AANA_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`, then use an Anthropic model name. |
| Native Gemini, local Ollama, etc. | Not implemented yet | These need provider-specific request/response adapters before they can run live model loops. |

OpenAI setup:

```text
AANA_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
```

Responses-compatible configuration:

```text
AANA_PROVIDER=openai
AANA_API_KEY=your_provider_or_proxy_key
AANA_BASE_URL=https://your-provider.example/v1
```

Or set the exact endpoint:

```text
AANA_PROVIDER=openai
AANA_API_KEY=your_provider_or_proxy_key
AANA_RESPONSES_URL=https://your-provider.example/v1/responses
```

This is not a guarantee that every provider works. The endpoint must accept the Responses-style payload used by the scripts and return compatible output text.

Anthropic setup:

```text
AANA_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Then use an Anthropic model name in the same scripts:

```powershell
python eval_pipeline/run_evals.py --limit 1 --models claude-opus-4-1-20250805
```

Replace the model name with the current Anthropic model you want to test.

The Anthropic adapter uses the native Messages API shape: `system`, `messages`, `model`, and `max_tokens`.

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

1. Scaffold the adapter: `python scripts/aana_cli.py scaffold "your domain"`.
2. Validate it: `python scripts/aana_cli.py validate-adapter examples/your_domain_adapter.json`.
3. Write one realistic high-pressure prompt.
4. Write one bad candidate answer that breaks the constraints.
5. Make the verifier catch the bad candidate.
6. Make the repair path produce a passing answer.
7. Save the prompt, candidate, verifier result, final answer, and caveats.
8. Only then expand to 5-10 prompts.

This is how AANA moves from a lab result to something users can plug into their own workflow.

## What To Tell Users

Use this framing when explaining AANA to non-specialists:

> AANA is a way to make AI answers pass through the checks your workflow already cares about. It does not make a model perfect. It makes the system name the constraints, check them, repair what can be repaired, and block or ask when a confident answer would be fake.

That is the accessibility goal: users should see their own daily constraints in the system, not just an abstract alignment theory.
