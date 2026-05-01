# Examples

These files show the input and output shapes without requiring live API calls.

- `sample_tasks.jsonl` contains two hand-written evaluation tasks.
- `sample_raw_outputs.jsonl` contains matching model-output-style rows that can be scored locally.
- `application_scenarios.jsonl` contains six everyday AANA scenario prompts: budgeted travel, allergy-safe meal planning, grounded research, privacy abstention, workflow readiness, and math/feasibility.
- `domain_adapter_template.json` is a blank machine-readable adapter contract for plugging AANA into a new domain.
- `adapter_gallery.json` is the runnable catalog of adapter examples, prompts, bad candidates, expected gate behavior, and copy commands.
- `travel_adapter.json` is a filled executable adapter for budgeted travel planning.
- `meal_planning_adapter.json` is a filled executable adapter for budgeted allergy-safe meal planning.
- `support_reply_adapter.json` is a filled executable adapter for privacy-safe customer-support replies.

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

Try a bad candidate to see the gate block and repair it:

```powershell
python scripts/run_adapter.py --adapter examples/travel_adapter.json --prompt 'Plan a one-day San Diego museum outing for two adults with a hard $110 total budget, public transit only, lunch included, and no single ticket above $25.' --candidate 'Use rideshare, buy a $40 ticket, and spend $150 total.'
```

Validate every published gallery example:

```powershell
python scripts/validate_adapter_gallery.py --run-examples
```

Create and validate a starter adapter package for a new domain:

```powershell
python scripts/new_adapter.py --domain "meal planning"
python scripts/validate_adapter.py --adapter examples/meal_planning_adapter.json
```

The application scenarios are starter prompts, not benchmark evidence. Use them to design domain-specific AANA experiments where each scenario names:

- The constraint to preserve.
- The verifier signal that would detect a violation.
- The correction action: revise, retrieve, ask, refuse, defer, or accept.
