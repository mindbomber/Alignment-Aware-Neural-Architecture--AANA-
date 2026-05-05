# AANA Message Send Guardrail Skill

Use this skill before an OpenClaw-style agent sends, posts, replies, forwards, or schedules a Slack, Teams, Discord, SMS, DM, or public channel message.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, or send messages on its own.

## Core Principle

Message sending is an external action. Verify channel, recipients, tone, private data, attachments, claims, and explicit send approval before posting.

## Required Checks

- destination: DM, group DM, private channel, public channel, SMS, or external workspace
- recipients, mentions, broadcast tags, and channel visibility
- tone, urgency, and conflict risk
- private data, secrets, customer data, internal links, and hidden thread context
- attachments, screenshots, links, files, and quoted content
- factual claims, commitments, deadlines, or policy statements
- explicit approval for sending or posting

## Decision Rule

- If this is a draft only, draft and stop.
- If channel, recipients, or approval are unclear, ask.
- If private data or unsupported claims appear, redact or revise.
- If sending is external, public, high-impact, or irreversible, require approval.
- If the send is unsafe, unauthorized, deceptive, or privacy-violating, block.

## Output Pattern

```text
AANA message gate:
- Destination: dm / group / private_channel / public_channel / sms / external
- Audience: exact / ambiguous / broad / public
- Tone: ready / revise / conflict_risk
- Privacy: clear / needs_redaction / sensitive / unknown
- Approval: approved / required / unclear / denied
- Decision: draft / revise / ask / redact / request_approval / send / block
```
