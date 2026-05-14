# OpenClaw Plugin Install And Use

This repository includes two OpenClaw-style plugin surfaces:

- `examples/openclaw/aana-guardrail-pack-plugin/`: no-code, instruction-only guardrail skills.
- `examples/openclaw/aana-runtime-connector-plugin/`: low-code runtime connector tools for a reviewed local AANA bridge.

## Guardrail Pack

Use the guardrail pack when an agent should follow AANA review procedures without calling a live checker.

Install or import the plugin directory from:

```text
examples/openclaw/aana-guardrail-pack-plugin/
```

Review before enabling:

- `package.json`
- `openclaw.plugin.json`
- `dist/index.js`
- `skills/*/manifest.json`
- `skills/*/SKILL.md`

Expected behavior:

- instruction-only,
- no dependency installation,
- no commands,
- no services,
- no file writes,
- no event-file writes,
- no memory persistence,
- no network access.

Use mode guidance:

- `advisory`: the agent gets review procedures but the host does not enforce them.
- `approval_gated`: external actions require user approval after review.
- `review_required`: high-risk or unclear actions route to human review before action.

## Runtime Connector

Use the runtime connector when an agent should call a live AANA bridge.

Install or import the plugin directory from:

```text
examples/openclaw/aana-runtime-connector-plugin/
```

Start a reviewed bridge:

```powershell
$env:AANA_BRIDGE_TOKEN = "replace-with-a-long-random-token"
aana-fastapi --host 127.0.0.1 --port 8766 --audit-log eval_outputs/audit/aana-fastapi.jsonl --rate-limit-per-minute 120
```

Configure the connector:

```json
{
  "bridgeBaseUrl": "http://127.0.0.1:8766",
  "bridgeToken": "replace-with-a-long-random-token",
  "timeoutMs": 8000,
  "requireExplicitBridgeBaseUrl": true
}
```

Registered tools:

- `aana_runtime_health`
- `aana_runtime_ready`
- `aana_validate_event`
- `aana_agent_check`
- `aana_validate_workflow`
- `aana_workflow_check`
- `aana_validate_workflow_batch`
- `aana_workflow_batch`

## Required Agent Behavior

For both plugins, the agent must obey the AANA result:

- proceed only when `gate_decision` is `pass`, `recommended_action` is `accept`, and `aix.hard_blockers` is empty,
- revise and recheck when `recommended_action` is `revise`,
- ask the user when `recommended_action` is `ask`,
- defer to stronger evidence, owner review, or human review when `recommended_action` is `defer`,
- refuse the unsafe part when `recommended_action` is `refuse`,
- treat bridge errors, failed validation, missing auth, and rate limits as blockers for the planned action.

## High-Risk Workflows

Use [`examples/openclaw/high-risk-workflow-examples.json`](../examples/openclaw/high-risk-workflow-examples.json) to rehearse high-risk plugin behavior for email send, file operations, data export, code review, medical safety, financial safety, and research grounding.

Use [`docs/openclaw-skill-conformance.md`](openclaw-skill-conformance.md) as the conformance checklist for new skills or plugin bundles.
