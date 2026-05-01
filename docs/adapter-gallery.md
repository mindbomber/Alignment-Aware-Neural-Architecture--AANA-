# AANA Adapter Gallery

The adapter gallery is the shortest path from "AANA works in one demo" to "I can copy this pattern into my own domain."

It lists each runnable domain adapter with:

- the adapter JSON file,
- a realistic prompt,
- a deliberately bad candidate,
- expected gate behavior,
- caveats for real deployment,
- a copyable command.

Machine-readable gallery:

- [`examples/adapter_gallery.json`](../examples/adapter_gallery.json)

Validate the gallery:

```powershell
python scripts/aana_cli.py validate-gallery --run-examples
```

That command checks that every referenced adapter is valid, runs executable examples, and confirms the expected gate result still holds.

Run an example by id:

```powershell
python scripts/aana_cli.py list
python scripts/aana_cli.py run support_reply
```

## Current Executable Examples

| Domain | Adapter | What It Proves |
|---|---|---|
| Budgeted travel planning | [`examples/travel_adapter.json`](../examples/travel_adapter.json) | The gate can block a useful-looking itinerary that breaks budget, transport, ticket, and lunch constraints, then pass a repaired answer. |
| Budgeted allergy-safe meal planning | [`examples/meal_planning_adapter.json`](../examples/meal_planning_adapter.json) | The same correction path transfers to groceries, dietary exclusions, explicit totals, and weekly coverage. |
| Privacy-safe customer support | [`examples/support_reply_adapter.json`](../examples/support_reply_adapter.json) | The gate can block invented order details, unsupported refund promises, and private payment details, then pass a reply that asks/routes through secure verification. |

## Add A Domain To The Gallery

1. Create or scaffold an adapter.
2. Add one realistic prompt.
3. Add one bad candidate that sounds useful but breaks a named constraint.
4. Run the adapter and record expected `candidate_gate`, `gate_decision`, and `recommended_action`.
5. Add the entry to `examples/adapter_gallery.json`.
6. Run `python scripts/aana_cli.py validate-gallery --run-examples`.

Keep the claim narrow: a gallery entry proves that this adapter contract, this verifier path, and this example gate behavior work. It does not prove broad safety for the domain.
