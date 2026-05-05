# AANA Runtime Connector Plugin

Marketplace slug: `aana-runtime-connector`

This OpenClaw plugin registers optional agent tools that let an agent call a user-configured local AANA bridge before taking higher-risk actions.

Use this plugin when you want OpenClaw-style agents to perform live AANA checks against the runtime API instead of relying only on instruction-only guardrail skills.

## Registered Tools

- `aana_runtime_health`: checks whether the configured AANA bridge is reachable.
- `aana_validate_event`: validates an AANA agent event object without running the gate.
- `aana_agent_check`: sends a planned agent answer or action to the AANA gate.
- `aana_validate_workflow`: validates an AANA Workflow Contract request without running the gate.
- `aana_workflow_check`: checks a proposed output or action through the AANA Workflow Contract gate.

All tools are optional. Users or administrators must explicitly allow them in OpenClaw tool configuration.

## Configuration

Set `bridgeBaseUrl` to a trusted loopback AANA bridge endpoint in your OpenClaw plugin configuration.

The connector intentionally does not ship a bridge server, Python helper, model provider, or policy engine. It only calls a bridge that the user or administrator has already reviewed and started.

## Safety Boundaries

- The plugin does not install dependencies.
- The plugin does not start background services.
- The plugin does not write files or store memory.
- The plugin does not send data to remote hosts.
- The plugin accepts only loopback bridge hosts.
- The plugin sends only the event or workflow payload supplied to the tool call.
- Payloads should be redacted and scoped to the decision being checked.

## Local Review Checklist

Before enabling this plugin, inspect:

- `package.json`
- `openclaw.plugin.json`
- `dist/index.js`
- `examples/`

Expected runtime behavior:

- registers five optional OpenClaw tools,
- validates that `bridgeBaseUrl` is present,
- rejects non-loopback bridge hosts,
- calls only the AANA bridge path needed for the selected tool,
- returns the bridge response as JSON text.

## When To Use This Instead Of The Guardrail Pack

Use the guardrail pack when you want no-code instruction procedures.

Use the runtime connector when you already have the AANA bridge running and want agents to call the live gate before sending, publishing, exporting, editing, booking, committing, or answering with uncertain evidence.
