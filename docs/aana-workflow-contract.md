# AANA Workflow Contract v0.1

The AANA Workflow Contract is the platform boundary for using AANA inside AI apps, agents, notebooks, and workflow tools.

It answers one question:

> Given a user request, a proposed AI output or action, verified evidence, and constraints, should this output pass, be revised, retrieve more information, ask, defer, or refuse?

This is different from prompt engineering, RAG, evals, or broad safety filters:

- Prompting asks the model to behave.
- RAG gives the model more context.
- Evals measure behavior after the fact.
- Safety filters block broad categories.
- AANA creates a correction and gate layer between generation and use.

## Minimal Python SDK

Install the repo locally:

```powershell
python -m pip install -e .
```

Then call AANA from Python:

```python
import aana

result = aana.check(
    adapter="research_summary",
    request="Write a concise research brief. Use only Source A and Source B. Label uncertainty.",
    candidate="AANA improves productivity by 40% for all teams [Source C].",
    evidence=[
        "Source A: AANA makes constraints explicit.",
        "Source B: Source coverage can be incomplete.",
    ],
    constraints=[
        "Do not invent citations.",
        "Do not add unsupported numbers.",
    ],
)

if result["gate_decision"] == "pass":
    print(result["output"])
else:
    print(result["recommended_action"])
```

The result includes:

- `gate_decision`: `pass`, `block`, `fail`, or `needs_adapter_implementation`
- `recommended_action`: `accept`, `revise`, `retrieve`, `ask`, `defer`, or `refuse`
- `candidate_gate`: whether the candidate was blocked
- `violations`: verifier findings against the candidate
- `output`: the accepted or repaired output
- `raw_result`: the underlying adapter and agent-check result

## Request Shape

Machine-readable example:

- [`examples/workflow_research_summary.json`](../examples/workflow_research_summary.json)

```json
{
  "contract_version": "0.1",
  "workflow_id": "demo-workflow-research-summary-001",
  "adapter": "research_summary",
  "request": "Write a concise research brief. Use only Source A and Source B.",
  "candidate": "AANA improves productivity by 40% for all teams [Source C].",
  "evidence": [
    "Source A: AANA makes constraints explicit.",
    "Source B: Source coverage can be incomplete."
  ],
  "constraints": [
    "Do not invent citations.",
    "Do not add unsupported numbers."
  ],
  "allowed_actions": ["accept", "revise", "retrieve", "ask", "defer", "refuse"]
}
```

## CLI

Validate a workflow request:

```powershell
python scripts/aana_cli.py validate-workflow --workflow examples/workflow_research_summary.json
```

Run the gate:

```powershell
python scripts/aana_cli.py workflow-check --adapter research_summary --request "Write a concise research brief. Use only Source A and Source B. Label uncertainty." --candidate "AANA improves productivity by 40% for all teams [Source C]." --evidence "Source A: AANA makes constraints explicit." --evidence "Source B: Source coverage can be incomplete." --constraint "Do not invent citations." --constraint "Do not add unsupported numbers."
```

Print schemas:

```powershell
python scripts/aana_cli.py workflow-schema
python scripts/aana_cli.py workflow-schema workflow_request
python scripts/aana_cli.py workflow-schema workflow_result
```

## HTTP Bridge

Start the local bridge:

```powershell
python scripts/aana_server.py --host 127.0.0.1 --port 8765
```

Workflow routes:

- `POST /validate-workflow`
- `POST /workflow-check`
- `GET /schemas/workflow-request.schema.json`
- `GET /schemas/workflow-result.schema.json`

PowerShell example:

```powershell
$workflow = Get-Content examples/workflow_research_summary.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/validate-workflow -Body $workflow -ContentType 'application/json'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/workflow-check -Body $workflow -ContentType 'application/json'
```

## Adapter Boundary

The contract is stable, but each adapter defines its own domain logic. For example:

- `research_summary`: citations, source boundaries, supported claims, uncertainty.
- `support_reply`: verified account facts, private data minimization, secure routing.
- `travel_planning`: budget, transport, ticket caps, lunch requirements.
- `meal_planning`: grocery budget, dietary exclusions, day coverage.

For a new domain, keep the same Workflow Contract and swap in a new adapter.

## Production Notes

The contract is intentionally small. A production integration should add:

- authenticated evidence and source IDs,
- retrieval provenance,
- audit logs for candidate, violations, repair, and final output,
- stricter domain verifiers,
- human review for high-impact or low-confidence decisions,
- deployment controls around the HTTP bridge.

Keep claims narrow: the Workflow Contract standardizes how apps call AANA. It does not prove that every adapter is production-safe without domain validation.
