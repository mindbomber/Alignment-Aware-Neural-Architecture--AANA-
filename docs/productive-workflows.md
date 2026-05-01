# Productive Workflows With AANA

AANA is becoming a plug-in pattern for everyday work where the answer is useful only if it respects checkable boundaries. The first demos covered planning and support. The next platform milestone is knowledge work: research, analysis, writing, and synthesis.

The runnable starting point is [`examples/research_summary_adapter.json`](../examples/research_summary_adapter.json). It shows how to gate a draft before it becomes a brief, memo, report, or agent answer.

## What It Checks

The research-summary adapter turns a common knowledge-work failure into an executable gate:

- Allowed sources: cite only the sources the workflow actually provided.
- Supported claims: block invented numbers, universal claims, guarantees, and unsupported benchmark language.
- Uncertainty labels: require the answer to say when evidence is incomplete.
- Useful output: after correction, still produce a concise brief instead of only refusing.

Run it without an API key:

```powershell
python scripts/aana_cli.py run research_summary
```

For agents:

```powershell
python scripts/aana_cli.py agent-check --event examples/agent_events/research_summary.json
```

## Where This Applies

Research workflows:

- literature notes,
- source-grounded summaries,
- evidence tables,
- citation-aware briefs,
- "what do we know so far?" synthesis.

Analysis workflows:

- KPI summaries with fixed source data,
- spreadsheet or report interpretation,
- budget, count, and date checks,
- claims that must trace back to rows, files, or source notes.

Writing workflows:

- executive briefs,
- grant or product copy with claim limits,
- public-facing summaries that cannot overstate evidence,
- drafts that must preserve legal, policy, or brand constraints.

Knowledge workflows:

- internal knowledge-base answers,
- support macros,
- meeting-summary actions,
- research assistant outputs,
- AI-agent responses before publishing or sending.

## Plug-In Pattern

1. Define the workflow: what the user or agent is trying to produce.
2. Name the unacceptable failures: invented citation, unsupported number, missing caveat, private info, impossible fact, policy overclaim.
3. Add verifiers: citation parser, source whitelist, calculation check, schema check, retrieval provenance, human-review flag.
4. Choose correction actions: revise, retrieve, ask, refuse, defer, or accept.
5. Put the gate before the output is sent, published, saved, or used by another agent.

The goal is not to make every model answer "more careful." The goal is to give productive-work systems a correction path that does not allow the draft to hand-wave away the constraints.

## Production Upgrade Path

The checked-in adapter is intentionally small and deterministic. To make it production-grade, connect it to:

- real document or retrieval IDs,
- source spans and citation provenance,
- calculation checks for numbers,
- policy-specific forbidden claims,
- audit logs of candidate, violations, repair, and final gate,
- human review for high-impact or low-confidence cases.

Keep claims narrow: the adapter proves this contract and example gate behavior work. A real deployment should validate the verifiers against the documents, data, and risk level of the target domain.
