# Community Issue Intake

Use this playbook when applying AANA to public GitHub issues, research threads, forum posts, or community requests. The goal is not to claim AANA can solve any open problem. The goal is to identify issues where verifier-grounded correction has a concrete advantage: explicit constraints, available evidence, bounded actions, and audit-safe outputs.

## Fit Criteria

Good first targets have all of these properties:

- The issue asks for an answer, review, benchmark, adapter, guardrail, documentation change, evaluation harness, or reproducible check.
- The success criteria can be written as constraints.
- Evidence can be attached from public issue text, docs, code, papers, logs, or fixtures.
- The proposed output can be routed to `accept`, `revise`, `retrieve`, `ask`, `defer`, or `refuse`.
- A wrong answer has a meaningful failure mode, such as hallucinated claims, missing citations, unsafe deployment guidance, privacy leakage, benchmark drift, or unsupported confidence.

Avoid issues where the desired result is mostly taste, vague speculation, private investigation, unbounded product design, or a direct intervention in a system we cannot inspect.

## Intake Loop

1. Capture the public source URL, repository, issue title, issue body, labels, and relevant maintainer comments.
2. Classify the issue family: alignment evaluation, mechanistic interpretability, RAG grounding, safety review, deployment guardrail, documentation, benchmark, or adapter request.
3. Map constraints:
   - `K_P`: factual, code, benchmark, citation, reproducibility, and environment constraints.
   - `K_B`: user harm, privacy, manipulation, medical/legal/financial risk, and human-review constraints.
   - `K_C`: repository scope, contribution rules, license, maintainer asks, issue labels, accepted output shape, and CI requirements.
   - `F`: evidence freshness, source reliability, verifier calibration, and confidence justification.
4. Choose the closest existing adapter. Prefer `research_answer_grounding`, `research_summary`, `code_change_review`, `model_evaluation_release`, or `publication_check` before creating a new adapter.
5. Create a Workflow Contract with the issue request, a candidate answer or patch plan, public evidence, constraints, and allowed actions.
6. Run `aana workflow-check` and inspect the gate decision, recommended action, AIx summary, hard blockers, and safe response.
7. Only publish or propose the answer after the route is `accept`, or after a `revise` route has been handled and rechecked.

## Scout Command

Generate a public GitHub candidate list:

```powershell
python scripts/benchmarks/community_issue_scout.py --output examples/community_issue_candidates.json
```

Use targeted queries when a community or domain is already known:

```powershell
python scripts/benchmarks/community_issue_scout.py --query '"mechanistic interpretability" state:open' --query '"RAG" hallucination label:"help wanted" state:open'
```

The scout output is an intake heuristic. It is not an AANA gate result, does not prove the issue is worth pursuing, and should not be published directly. Convert one candidate at a time into a Workflow Contract, attach public evidence, and run `workflow-check` before drafting a community response or pull request plan.

Create an AANA-gated workpack for a selected issue:

```powershell
python scripts/benchmarks/community_issue_solver.py --repository adhit-r/fairmind --limit 1
```

The solver writes a workpack under `eval_outputs/community_issue_solver/` with a Workflow Contract, issue-response draft, AANA gate result, and any follow-on code guardrail artifacts. It intentionally stops before posting comments, opening pull requests, or pushing branches.

## Triage Output

For each candidate issue, produce:

- `source`: URL and repository.
- `problem`: one-sentence issue summary.
- `aana_fit`: high, medium, or low.
- `adapter`: selected existing adapter or proposed new adapter.
- `constraints`: grouped by `K_P`, `K_B`, `K_C`, and optional `F`.
- `evidence_needed`: public artifacts needed before a useful answer.
- `first_action`: draft answer, ask clarifying question, reproduce, build fixture, add verifier, or defer.
- `publish_boundary`: what can be shared publicly without leaking private data or overstating results.

## Suggested Starting Areas

- AI alignment evaluation issues where claims must be tied to reproducible benchmarks or citations.
- Mechanistic interpretability issues where the useful contribution is a clear experiment plan, traceability checklist, or benchmark harness rather than an unsupported theory claim.
- RAG or hallucination issues where source grounding, citation limits, and unsupported-answer refusal can be checked.
- GitHub Action or CI guardrail issues where AANA can review risky changes before deployment.
- Documentation issues where the correction loop can prevent inflated claims about the platform.

## Example

See `examples/workflow_community_issue_research_grounding.json` for a runnable Workflow Contract that turns a public mechanistic-interpretability issue into an AANA-checkable research-grounding task.

See `examples/community_issue_candidates.json` for a generated candidate list from the default scout queries.
