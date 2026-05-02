# Examples

These files show the input and output shapes without requiring live API calls.

Agent-event files are local development fixtures. For standalone agent skills or marketplace packages, prefer a reviewed in-memory tool/API interface and avoid writing sensitive action data to local files.

- `sample_tasks.jsonl` contains two hand-written evaluation tasks.
- `sample_raw_outputs.jsonl` contains matching model-output-style rows that can be scored locally.
- `application_scenarios.jsonl` contains six everyday AANA scenario prompts: budgeted travel, allergy-safe meal planning, grounded research, privacy abstention, workflow readiness, and math/feasibility.
- `domain_adapter_template.json` is a blank machine-readable adapter contract for plugging AANA into a new domain.
- `adapter_gallery.json` is the runnable catalog of adapter examples, prompts, bad candidates, expected gate behavior, and copy commands.
- `travel_adapter.json` is a filled executable adapter for budgeted travel planning.
- `meal_planning_adapter.json` is a filled executable adapter for budgeted allergy-safe meal planning.
- `support_reply_adapter.json` is a filled executable adapter for privacy-safe customer-support replies.
- `research_summary_adapter.json` is a filled executable adapter for grounded research and knowledge-work summaries.
- `agent_event_support_reply.json` is a machine-readable event an agent can pass to AANA before sending a support reply.
- `agent_events/` contains executable agent-event examples for support replies, travel booking/planning, meal planning, and research summaries.
- `workflow_research_summary.json` is a general AANA Workflow Contract request for apps, notebooks, and agent tools.
- `workflow_batch_productive_work.json` checks several workflow requests at once across research, support, and meal-planning use cases.
- `agent_api_usage.py` shows the same event check through the Python API instead of the CLI.

Use the command hub first:

```powershell
python scripts/aana_cli.py list
python scripts/aana_cli.py run travel_planning
python scripts/aana_cli.py run meal_planning
python scripts/aana_cli.py run support_reply
python scripts/aana_cli.py run research_summary
python scripts/aana_cli.py validate-workflow --workflow examples/workflow_research_summary.json
python scripts/aana_cli.py validate-workflow-batch --batch examples/workflow_batch_productive_work.json
python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json
python scripts/aana_cli.py validate-gallery --run-examples
python scripts/aana_cli.py validate-event --event examples/agent_event_support_reply.json
aana agent-check --event examples/agent_event_support_reply.json
python scripts/aana_cli.py run-agent-examples
python scripts/aana_cli.py scaffold-agent-event support_reply --output-dir examples/agent_events
python scripts/aana_cli.py agent-schema agent_event
python scripts/aana_cli.py policy-presets
python examples/agent_api_usage.py
python scripts/aana_server.py --host 127.0.0.1 --port 8765
```

When the HTTP bridge is running, tools can discover its HTTP contract at `http://127.0.0.1:8765/openapi.json` and JSON schemas at `http://127.0.0.1:8765/schemas`.

Try the scoring script:

```powershell
python eval_pipeline/score_outputs.py --input examples/sample_raw_outputs.jsonl --scored examples/sample_scored_outputs.csv --summary examples/sample_summary_by_condition.csv
```

The generated CSV files are useful for learning, but you do not need to commit them.

Run the executable adapters:

```powershell
python scripts/run_adapter.py --adapter examples/travel_adapter.json --prompt 'Plan a one-day San Diego museum outing for two adults with a hard $110 total budget, public transit only, lunch included, and no single ticket above $25.'
```

```powershell
python scripts/run_adapter.py --adapter examples/meal_planning_adapter.json --prompt 'Create a weekly gluten-free, dairy-free meal plan for one person with a $70 grocery budget.' --candidate 'Buy regular pasta, wheat bread, cheese, and milk for $95 total. Monday: pasta. Tuesday: cheese sandwiches.'
```

```powershell
python scripts/run_adapter.py --adapter examples/support_reply_adapter.json --prompt 'Draft a customer-support reply for a refund request. Use only verified facts: customer name is Maya Chen, order ID and refund eligibility are not available, and do not include private account details or invent policy promises.' --candidate 'Hi Maya, order #A1842 is eligible for a full refund and your card ending 4242 will be credited in 3 days.'
```

```powershell
python scripts/run_adapter.py --adapter examples/research_summary_adapter.json --prompt 'Write a concise research brief about whether AANA-style verifier loops help knowledge workers produce more reliable summaries. Use only Source A and Source B. Do not invent citations. Label uncertainty where evidence is incomplete.' --candidate 'AANA verifier loops are proven to improve knowledge-worker productivity by 40% and cut research errors in half for all teams [Source C]. Wikipedia and unnamed experts also confirm this is guaranteed to work.'
```

Try a bad candidate to see the gate block and repair it:

```powershell
python scripts/run_adapter.py --adapter examples/travel_adapter.json --prompt 'Plan a one-day San Diego museum outing for two adults with a hard $110 total budget, public transit only, lunch included, and no single ticket above $25.' --candidate 'Use rideshare, buy a $40 ticket, and spend $150 total.'
```

Validate every published gallery example:

```powershell
python scripts/aana_cli.py validate-gallery --run-examples
```

Create and validate a starter adapter package for a new domain:

```powershell
python scripts/aana_cli.py scaffold "meal planning"
python scripts/aana_cli.py validate-adapter examples/meal_planning_adapter.json
```

The application scenarios are starter prompts, not benchmark evidence. Use them to design domain-specific AANA experiments where each scenario names:

- The constraint to preserve.
- The verifier signal that would detect a violation.
- The correction action: revise, retrieve, ask, refuse, defer, or accept.
