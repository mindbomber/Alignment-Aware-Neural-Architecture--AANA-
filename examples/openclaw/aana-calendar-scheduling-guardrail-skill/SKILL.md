# AANA Calendar Scheduling Guardrail Skill

Use this skill before an OpenClaw-style agent creates, updates, cancels, invites, or shares a calendar event.

This is an instruction-only skill. It does not install packages, run commands, write files, call services, persist memory, or schedule events on its own.

## Core Principle

Calendar changes affect other people. Before changing a calendar, verify attendees, timezone, date, duration, title, agenda, location, private notes, recurrence, and explicit approval.

## Required Checks

- exact action: create, update, cancel, invite, reschedule, or share availability
- exact attendees and whether they are internal or external
- timezone, date, start time, end time, duration, and recurrence
- title, agenda, location, conferencing link, and private notes
- whether attendee visibility or guest permissions expose private data
- whether the user approved the exact event change

## Decision Rule

- If details are complete, low-risk, and explicitly approved, proceed.
- If attendees, timezone, date, duration, or recurrence are unclear, ask.
- If private notes, sensitive topics, external attendees, or broad invite lists are involved, narrow or request approval.
- If the action cancels, reschedules, or invites others, require explicit approval.
- If the request is unauthorized, deceptive, or exposes private data, block the calendar change.

## Output Pattern

```text
AANA calendar gate:
- Action: create / update / cancel / invite / reschedule / share_availability
- Attendees: exact / missing / ambiguous / external / group_alias
- Time: confirmed / missing / timezone_unclear / conflicting
- Privacy: clear / private_notes / sensitive / unknown
- Approval: approved / required / unclear / denied
- Decision: proceed / ask / narrow / request_approval / block
```
