# AANA Workflow Contract v0.1

Canonical entry point: [Integrate Runtime](integrate-runtime/index.md). Treat this contract as the stable integration boundary for workflow checks.

The AANA Workflow Contract is the platform boundary for using AANA inside AI apps, agents, notebooks, and workflow tools.

It is one of the two primary public APIs for the platform, alongside the Agent Event Contract. Runtime internals such as adapter runner helpers, verifier functions, and repair-policy branches are not public integration points; they exist to serve this contract and may change behind the contract boundary.

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

Prerequisite: Python 3.10+ is supported; Python 3.12 is recommended for local onboarding. Install `uv` from [docs.astral.sh/uv](https://docs.astral.sh/uv/) or use the `pip` fallback below.

```powershell
uv venv --python 3.12 .venv
uv pip install --python .\.venv\Scripts\python.exe -e ".[api]"
.\.venv\Scripts\Activate.ps1
```

Fallback for an active environment with `pip` available:

```powershell
python -m pip install -e ".[api]"
```

For new programmatic integrations, use the typed runtime API:

```python
import eval_pipeline

result = eval_pipeline.check(
    adapter="research_summary",
    request="Write a concise research brief. Use only Source A and Source B. Label uncertainty.",
    candidate="AANA improves productivity by 40% for all teams [Source C].",
    evidence=["Source A: AANA makes constraints explicit."],
    constraints=["Do not invent citations."],
)

print(result.api_version, result.contract_version, result.recommended_action)
```

See [`python-runtime-api.md`](python-runtime-api.md) for typed result objects, public exceptions, and version rules.

The compatibility `aana` package keeps the original dictionary-returning helper functions:

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

if (
    result["gate_decision"] == "pass"
    and result["recommended_action"] == "accept"
    and result["aix"]["decision"] == "accept"
):
    print(result["output"])
else:
    print(result["recommended_action"])
```

You can also pass a full contract request or load one from disk:

```python
request = aana.WorkflowRequest(
    adapter="research_summary",
    request="Write a concise research brief. Use only Source A and Source B.",
    candidate="AANA improves productivity by 40% for all teams [Source C].",
    evidence=["Source A: AANA makes constraints explicit."],
    constraints=["Do not invent citations."],
)

result = aana.check_request(request)
same_result = aana.check_file("examples/workflow_research_summary.json")
result_object = aana.result_object(result)

if result_object.passed:
    print(result_object.output)
```

For productive apps and agents, batch checks are often the better integration point. A research workspace, CRM, or coding agent may need to check several proposed outputs before it publishes, sends, writes, or commits:

```python
batch = aana.check_batch_file("examples/workflow_batch_productive_work.json")
batch_result = aana.batch_result_object(batch)

print(batch_result.summary)
for item in batch_result.results:
    print(item.workflow_id, item.recommended_action)
```

Batch behavior is stable:

- top-level batch contract errors fail before execution,
- each valid item receives a `workflow_id`, generated from `batch_id` when omitted,
- adapter/runtime failures are isolated to the failed item,
- failed items return a Workflow Result with `gate_decision: "fail"`, `candidate_gate: "block"`, a `workflow_item_error` violation, and an AIx hard blocker,
- failed items never recommend direct `accept`; AANA chooses the safest available fallback action and uses `defer` when the caller allowed only `accept`.

The result includes:

- `gate_decision`: `pass`, `block`, `fail`, or `needs_adapter_implementation`
- `recommended_action`: `accept`, `revise`, `retrieve`, `ask`, `defer`, or `refuse`
- `candidate_gate`: whether the candidate was blocked
- `aix`: final output Alignment Index with `score`, `components`, `beta`, `thresholds`, `decision`, and `hard_blockers`
- `candidate_aix`: candidate Alignment Index when a candidate was supplied
- `violations`: verifier findings against the candidate
- `output`: the accepted or repaired output
- `audit_summary`: redacted decision metadata safe for logs and dashboards
- `raw_result`: the underlying adapter and agent-check result

AIx is an additional decision surface, not a gate replacement. Do not proceed when `aix.hard_blockers` is non-empty. In correction flows, `candidate_aix` may be low while final `aix` is acceptable after the adapter repairs or routes the answer.

`allowed_actions` is enforced. If an adapter recommends an action that the caller did not allow, AANA selects the safest available fallback action from the caller's list and adds a `recommended_action_not_allowed` violation.

Evidence can be passed as simple strings or as structured objects when provenance matters:

```json
{
  "source_id": "source-a",
  "retrieved_at": "2026-05-05T00:00:00Z",
  "trust_tier": "verified",
  "redaction_status": "redacted",
  "text": "Source A: AANA makes constraints explicit."
}
```

Production integrations should prefer structured evidence objects, keep raw private records out of request files when a redacted summary is enough, and treat missing or stale evidence as a reason to `retrieve`, `ask`, or `defer`.

Production evidence connector stubs are available for CRM/support, ticketing, email, calendar, IAM, CI/code review, deployment/release, billing/payment, data export, workspace files, and security systems. They define required source IDs, read scopes, auth/action boundaries, redaction expectations, freshness SLOs, failure modes, and structured evidence templates without performing external calls. `examples/evidence_mock_connector_fixtures.json` provides synthetic connector outputs for the strongest pilot systems and verifies that those outputs normalize into Workflow Contract evidence objects.

Evidence can be validated against an approved source registry:

```powershell
python scripts/aana_cli.py validate-evidence-registry --evidence-registry examples/evidence_registry.json
python scripts/aana_cli.py evidence-integrations --evidence-registry examples/evidence_registry.json
python scripts/aana_cli.py validate-workflow-evidence --workflow examples/workflow_research_summary_structured.json --evidence-registry examples/evidence_registry.json --require-structured
python scripts/aana_cli.py workflow-check --workflow examples/workflow_research_summary_structured.json --evidence-registry examples/evidence_registry.json --require-structured-evidence
```

For batch validation, use `workflow-batch --evidence-registry ... --require-structured-evidence` only with batches whose every item uses structured evidence. AANA reports source/freshness/structured-evidence findings per item with paths such as `$.requests[0].evidence[0].source_id`.

## Request Shape

Stable field reference:

- `workflow_request` version: `contract_version: "0.1"`.
- Required request fields: `adapter`, `request`.
- Optional request fields: `contract_version`, `workflow_id`, `candidate`, `evidence`, `constraints`, `allowed_actions`, and `metadata`.
- `workflow_result` version: `contract_version: "0.1"`.
- Required result fields: `contract_version`, `adapter`, `gate_decision`, `recommended_action`, `output`, and `audit_summary`.
- Public result shape: `gate_decision`, `recommended_action`, `violations`, `aix`, `candidate_aix`, `audit_summary`, and safe output in `output`.
- Adapter IDs are the catalog IDs exposed by the adapter gallery, such as `support_reply`, `crm_support_reply`, `email_send_guardrail`, `ticket_update_checker`, and `research_summary`.
- Evidence may be a string or a structured object. Structured evidence requires `text`; `source_id`, `retrieved_at`, `trust_tier`, and `redaction_status` are optional but recommended for pilot and production-like integrations.
- `runtime.py`, `legacy_runner.py`, verifier modules, adapter JSON internals, repair policies, and runner helper functions are implementation details. Do not import them as integration APIs.

Machine-readable example:

- [`examples/workflow_research_summary.json`](../examples/workflow_research_summary.json)
- [`examples/workflow_batch_productive_work.json`](../examples/workflow_batch_productive_work.json)
- [`examples/workflow_contract_examples.json`](../examples/workflow_contract_examples.json)

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

Batch request shape:

```json
{
  "contract_version": "0.1",
  "batch_id": "demo-batch-productive-work-001",
  "requests": [
    {
      "workflow_id": "demo-workflow-research-summary-001",
      "adapter": "research_summary",
      "request": "Write a concise research brief. Use only Source A and Source B.",
      "candidate": "AANA improves productivity by 40% for all teams [Source C].",
      "evidence": ["Source A: AANA makes constraints explicit."],
      "constraints": ["Do not invent citations."]
    }
  ]
}
```

## CLI

The public CLI runtime path is contract-first:

- `workflow-check` and `workflow-batch` accept Workflow Contract payloads directly.
- `run <adapter_id>` is a gallery shortcut that materializes a Workflow Contract request from the adapter catalog entry, then returns the same Workflow Result shape as `workflow-check`.
- `run-file` executes an arbitrary adapter JSON file directly and is intended for adapter development diagnostics, not app or agent integration.

Validate a workflow request:

```powershell
python scripts/aana_cli.py validate-workflow --workflow examples/workflow_research_summary.json
```

Run the gate:

```powershell
python scripts/aana_cli.py workflow-check --workflow examples/workflow_research_summary.json
```

Run a batch of workflow checks:

```powershell
python scripts/aana_cli.py validate-workflow-batch --batch examples/workflow_batch_productive_work.json
python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json
```

Or pass the fields directly:

```powershell
python scripts/aana_cli.py workflow-check --adapter research_summary --request "Write a concise research brief. Use only Source A and Source B. Label uncertainty." --candidate "AANA improves productivity by 40% for all teams [Source C]." --evidence "Source A: AANA makes constraints explicit." --evidence "Source B: Source coverage can be incomplete." --constraint "Do not invent citations." --constraint "Do not add unsupported numbers."
```

Print schemas:

```powershell
python scripts/aana_cli.py workflow-schema
python scripts/aana_cli.py workflow-schema workflow_request
python scripts/aana_cli.py workflow-schema workflow_batch_request
python scripts/aana_cli.py workflow-schema workflow_result
python scripts/aana_cli.py workflow-schema workflow_batch_result
```

## HTTP Service

Start the installed FastAPI policy service:

```powershell
aana-fastapi --host 127.0.0.1 --port 8766 --audit-log eval_outputs/audit/aana-fastapi.jsonl
```

For production-like local runs, require POST authentication:

```powershell
$env:AANA_BRIDGE_TOKEN = "replace-with-a-secret"
aana-fastapi --host 127.0.0.1 --port 8766 --audit-log eval_outputs/audit/aana-fastapi.jsonl --rate-limit-per-minute 120
```

Clients must then send either `Authorization: Bearer <token>` or `X-AANA-Token: <token>` on POST requests. The service also rejects oversized POST bodies; the default limit is `65536` bytes and can be changed with `--max-request-bytes`. `--rate-limit-per-minute` adds a process-local per-client POST limit. With `--audit-log`, successful `/agent-check`, `/workflow-check`, and `/workflow-batch` calls append redacted audit records from the service process.

See [`fastapi-service.md`](fastapi-service.md) for public service startup, auth, request-size limits, readiness checks, audit append guarantees, and deployment guidance. The legacy [`http-bridge-runbook.md`](http-bridge-runbook.md) covers `python scripts/aana_server.py` for repo-local playground, dashboard, and local demo workflows.

For audit trails, use `aana.audit_workflow_check(workflow_request, result)` or `aana.audit_workflow_batch(batch_request, result)`. These helpers produce redacted records with IDs, gate decisions, recommended actions, AIx score summaries, violation codes, counts, and SHA-256 fingerprints for checked text. They do not include raw requests, candidates, evidence, constraints, or outputs.

The CLI can append redacted workflow audit records to JSONL:

```powershell
python scripts/aana_cli.py workflow-check --workflow examples/workflow_research_summary.json --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py workflow-batch --batch examples/workflow_batch_productive_work.json --audit-log eval_outputs/audit/aana-audit.jsonl
python scripts/aana_cli.py audit-summary --audit-log eval_outputs/audit/aana-audit.jsonl
```

Workflow routes:

- `POST /validate-workflow`
- `POST /workflow-check`
- `POST /validate-workflow-batch`
- `POST /workflow-batch`
- `GET /openapi.json`
- `GET /docs`
- `GET /ready`

PowerShell example:

```powershell
$workflow = Get-Content examples/workflow_research_summary.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8766/validate-workflow -Body $workflow -ContentType 'application/json'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8766/workflow-check -Body $workflow -ContentType 'application/json'

$batch = Get-Content examples/workflow_batch_productive_work.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8766/workflow-batch -Body $batch -ContentType 'application/json'
```

## Adapter Boundary

The contract is stable, but each adapter defines its own domain logic. For example:

- `research_summary`: citations, source boundaries, supported claims, uncertainty.
- `support_reply`: verified account facts, private data minimization, secure routing.
- `travel_planning`: budget, transport, ticket caps, lunch requirements.
- `meal_planning`: grocery budget, dietary exclusions, day coverage.

For a new domain, keep the same Workflow Contract and swap in a new adapter.

Canonical workflow example families are indexed in [`examples/workflow_contract_examples.json`](../examples/workflow_contract_examples.json):

- `enterprise`: CRM/support, email, ticketing, data export, IAM, code review, deployment, and incident response workflows.
- `personal_productivity`: email, calendar, file operation, booking/purchase, and research grounding workflows.
- `government_civic`: procurement/vendor risk, grant/application review, insurance claim triage, publication review, and research grounding workflows.

## Production Notes

The contract is intentionally small. A production integration should add:

- authenticated evidence and source IDs,
- retrieval provenance,
- audit logs for candidate, AIx summaries, violations, repair, and final output,
- stricter domain verifiers,
- human review for high-impact or low-confidence decisions,
- deployment controls around the HTTP bridge.

Keep claims narrow: the Workflow Contract standardizes how apps call AANA. It does not prove that every adapter is production-safe without domain validation.
