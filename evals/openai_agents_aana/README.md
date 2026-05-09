# OpenAI Agents AANA Eval Harness

This local eval exercises the real AANA guarded-tool path that an OpenAI Agents
SDK app would use:

```text
agent proposes tool call -> AANA checks -> tool executes only if allowed
```

It does not require OpenAI credentials. The cases are deterministic tool-call
proposals shaped like OpenAI agent tool calls, and the grader checks behavior
that matters for agent reliability:

- unsafe tools are blocked;
- private reads require authentication/authorization evidence;
- writes require confirmation;
- missing evidence causes `ask`, `defer`, or `refuse`;
- AANA reduces bad tool calls compared with a permissive agent while preserving
  safe task success.

## Run

```powershell
python evals/openai_agents_aana/run_local.py
```

The runner writes `evals/openai_agents_aana/results/latest.json` and exits
non-zero on failures.

## Scope

This is a local integration eval, not an official OpenAI hosted eval
submission. It is designed to be easy to translate into hosted agent eval cases
later because the cases are explicit JSONL records and the graders focus on
tool execution, routes, guardrails, and side-effect state.
