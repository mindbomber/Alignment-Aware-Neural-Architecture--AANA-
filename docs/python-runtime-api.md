# AANA Python Runtime API

The Python runtime API is the stable programmatic entry point for applications, agents, notebooks, services, and tests that need to call AANA without going through the CLI.

Public import:

```python
import eval_pipeline
```

Compatibility import:

```python
import aana
```

`eval_pipeline` exposes the typed runtime API. `aana` keeps the original dictionary-returning helper functions for backward compatibility and also exposes typed helpers with a `_typed` suffix.

## Version

Current runtime API version: `0.1`

```python
import eval_pipeline

assert eval_pipeline.RUNTIME_API_VERSION == "0.1"
```

The runtime result object carries both:

- `api_version`: the Python runtime API version.
- `contract_version`: the Workflow Contract version used by the request and result.

## Public Surface

The stable `eval_pipeline` public exports are intentionally narrow:

- dataclasses: `RuntimeResult`, `ValidationReport`, `WorkflowRequest`, `WorkflowResult`, `WorkflowBatchRequest`, `WorkflowBatchResult`
- exceptions: `AANAError`, `AANAInputError`, `AANAValidationError`, `AANACheckError`
- checks: `check`, `check_request`, `check_batch`, `check_file`, `check_batch_file`
- validation: `validate_request`, `validate_batch`
- utility: `load_json_object`, `schemas`

Lower-level modules such as `agent_api`, `workflow_contract`, `audit`, and `production` remain available for repository tooling, but production integrations should depend on the public exports above.

## Single Check

```python
import eval_pipeline

result = eval_pipeline.check(
    adapter="research_summary",
    request="Write a concise research brief. Use only Source A and Source B.",
    candidate="AANA improves productivity by 40% for all teams [Source C].",
    evidence=["Source A: AANA makes constraints explicit."],
    constraints=["Do not invent citations."],
)

if (
    result.passed
    and result.recommended_action == "accept"
    and result.aix["decision"] == "accept"
):
    print(result.result.output)
else:
    print(result.recommended_action)
```

`RuntimeResult.result` is a typed `WorkflowResult` for single checks.

## Typed Requests

```python
import eval_pipeline

request = eval_pipeline.WorkflowRequest(
    adapter="research_summary",
    request="Write a concise research brief. Use Source A only.",
    candidate="Unsupported answer [Source C].",
    evidence=[
        {
            "source_id": "source-a",
            "retrieved_at": "2026-05-05T00:00:00Z",
            "trust_tier": "verified",
            "redaction_status": "redacted",
            "text": "Source A: AANA makes constraints explicit.",
        }
    ],
    constraints=["Use Source A only."],
)

result = eval_pipeline.check_request(request)
```

## Batch Checks

```python
import eval_pipeline

batch = eval_pipeline.check_batch_file("examples/workflow_batch_productive_work.json")

print(batch.result.summary)
for item in batch.result.results:
    print(item.workflow_id, item.recommended_action)
```

`RuntimeResult.result` is a typed `WorkflowBatchResult` for batch checks.

## Exceptions

The public runtime API does not expose raw `ValueError`, `OSError`, or `JSONDecodeError` for normal integration failures.

- `AANAInputError`: a file, JSON payload, or API argument cannot be loaded.
- `AANAValidationError`: a payload fails the Workflow Contract validator.
- `AANACheckError`: a valid request cannot be checked, for example because the adapter id is unknown.
- `AANAError`: base class for all public runtime failures.

Example:

```python
import eval_pipeline

try:
    result = eval_pipeline.check_file("examples/workflow_research_summary.json")
except eval_pipeline.AANAValidationError as exc:
    print(exc.report)
except eval_pipeline.AANAError as exc:
    print(exc.to_dict())
```

Every public exception supports `to_dict()` for structured logging.

## Evidence Connector Helpers

The legacy `aana` surface exposes connector-contract helpers for pilots and production connector tests:

```python
import aana

fixtures = aana.load_evidence_mock_fixtures("examples/evidence_mock_connector_fixtures.json")
report = aana.run_evidence_mock_connector("deployment", fixtures=fixtures, now="2026-05-05T01:00:00Z")

assert report["valid"]
assert report["evidence"][0]["metadata"]["normalized"]
```

Use `aana.normalize_evidence_object(...)` inside connector tests to ensure a system-specific record becomes a Workflow Contract evidence object before it reaches an adapter gate.

## Audit Review Helpers

Redacted audit records can be validated and converted into reviewer artifacts:

```python
import aana

records = aana.load_audit_records("eval_outputs/audit/aana-audit.jsonl")
schema = aana.validate_audit_records(records)
drift = aana.audit_aix_drift_report(records)

assert schema["valid"]
assert drift["valid"]
```

Use `aana.write_audit_reviewer_report(...)` to create a Markdown handoff from an audit JSONL file plus optional metrics, drift, and manifest artifacts.

## Legacy `aana` Compatibility

Existing calls keep returning dictionaries:

```python
import aana

legacy = aana.check_file("examples/workflow_research_summary.json")
assert isinstance(legacy, dict)
```

Typed helpers are available beside them:

```python
typed = aana.check_file_typed("examples/workflow_research_summary.json")
assert typed.api_version == "0.1"
```

## Result Contract

`RuntimeResult.to_dict()` returns a stable wrapper:

```json
{
  "api_version": "0.1",
  "kind": "workflow",
  "ok": true,
  "contract_version": "0.1",
  "validation": {
    "valid": true,
    "errors": 0,
    "warnings": 0,
    "issues": [],
    "api_version": "0.1"
  },
  "result": {
    "contract_version": "0.1",
    "adapter": "research_summary",
    "gate_decision": "pass",
    "recommended_action": "revise"
  }
}
```

The `result` object contains the full Workflow Result or Workflow Batch Result, including AIx, candidate AIx, violations, output, and raw adapter result fields when available.

## Version Bump Rules

Compatible additions can remain on runtime API `0.1`:

- adding optional fields to `RuntimeResult.to_dict()`,
- adding new typed helper functions,
- adding new exception subclasses under `AANAError`,
- adding schemas to `schemas()`.

Breaking changes require a runtime API version bump and migration notes:

- changing exception class meanings,
- changing `RuntimeResult.to_dict()` required keys,
- changing `passed`, `gate_decision`, `recommended_action`, or `aix` semantics,
- removing public exports from `eval_pipeline.__all__`,
- changing a typed helper from raising public `AANAError` subclasses to raw lower-level exceptions.
