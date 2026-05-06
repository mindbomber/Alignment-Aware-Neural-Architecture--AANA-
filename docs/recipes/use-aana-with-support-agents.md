# Use AANA With Support Agents

Use this recipe when a support agent, CRM automation, email tool, or ticketing workflow needs a guardrail before customer-visible text or send actions.

All examples route through the public contracts:

- Workflow Contract: `/workflow-check` and `/workflow-batch`
- Agent Event Contract: `/agent-check`

Do not call internal adapter runner scripts, legacy runner modules, verifier modules, or repair helpers from an integration.

## Support Adapters

| Alias | Adapter ID | Use |
| --- | --- | --- |
| `draft` | `support_reply` | Draft support reply guardrail. |
| `crm` | `crm_support_reply` | CRM/account fact and refund boundary checker. |
| `email` | `email_send_guardrail` | Support email recipient, BCC, attachment, and approval guardrail. |
| `ticket` | `ticket_update_checker` | Customer-visible ticket update checker. |
| `billing` | `invoice_billing_reply` | Adjacent invoice/billing reply checker. |

## Python SDK

```python
import aana

client = aana.SupportAANAClient()

workflow = client.workflow_request(
    adapter="crm",
    workflow_id="support-refund-001",
    request="Draft a refund reply using only verified CRM, order, and policy facts.",
    candidate="Hi Maya, order #A1842 is eligible for a full refund and your card ending 4242 will be credited in 3 days.",
    evidence=[
        client.evidence_object(
            "CRM record: customer name is Maya Chen. Order ID and refund eligibility are unavailable.",
            source_id="crm-record",
            retrieved_at="2026-05-05T00:00:00Z",
        ),
        client.evidence_object(
            "Support policy: verify refund eligibility before promising refunds, credits, replacements, or payment timelines.",
            source_id="support-policy",
            retrieved_at="2026-05-05T00:00:00Z",
        ),
    ],
    allowed_actions=["accept", "revise", "retrieve", "ask", "defer", "refuse"],
)

result = client.workflow_check(workflow)
```

For a running bridge:

```python
import os
import aana

client = aana.SupportAANAClient(
    base_url="http://127.0.0.1:8765",
    token=os.environ["AANA_BRIDGE_TOKEN"],
    shadow_mode=True,
)

result = client.workflow_check(workflow)
```

## Agent Framework Pattern

Call AANA after the model drafts a support response and before the agent sends, posts, refunds, closes, exports, or updates a customer-visible record.

```python
event = client.agent_event(
    adapter_id="draft",
    event_id="support-agent-event-001",
    user_request="Draft a support reply using verified account facts only.",
    candidate_action=model_draft,
    available_evidence=[
        client.evidence_object("Refund eligibility is not verified.", source_id="support-policy"),
        client.evidence_object("Customer account is not verified for payment detail disclosure.", source_id="crm-record"),
    ],
    allowed_actions=["accept", "revise", "retrieve", "ask", "defer", "refuse"],
)

gate = client.agent_check(event)

if gate["gate_decision"] == "pass" and gate["recommended_action"] == "accept" and not gate["aix"]["hard_blockers"]:
    send_customer_reply(model_draft)
elif gate["recommended_action"] == "revise":
    show_revised_draft(gate["safe_response"])
elif gate["recommended_action"] in {"ask", "defer"}:
    route_to_human_review(gate["audit_summary"])
else:
    block_send(gate["violations"])
```

## LangGraph-Style Node

```python
def aana_support_gate(state):
    event = state["aana_client"].agent_event(
        adapter_id="crm",
        user_request=state["customer_request"],
        candidate_action=state["draft_reply"],
        available_evidence=state["approved_evidence"],
        allowed_actions=["accept", "revise", "retrieve", "ask", "defer", "refuse"],
    )
    result = state["aana_client"].agent_check(event)
    return {"aana_result": result, "next": result["recommended_action"]}
```

## CrewAI-Style Tool

```python
def support_guardrail_tool(user_request, draft_reply, evidence):
    client = aana.SupportAANAClient(base_url="http://127.0.0.1:8765", token=os.environ["AANA_BRIDGE_TOKEN"])
    event = client.agent_event(
        adapter_id="draft",
        user_request=user_request,
        candidate_action=draft_reply,
        available_evidence=evidence,
    )
    return client.agent_check(event)
```

## HTTP

Start the bridge:

```powershell
$env:AANA_BRIDGE_TOKEN = "aana-local-dev-token"
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/support-agent.jsonl --rate-limit-per-minute 120
```

Run one Workflow Contract fixture:

```powershell
$payload = Get-Content examples/workflow_crm_support_reply.json -Raw
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/workflow-check -Headers @{ Authorization = "Bearer $env:AANA_BRIDGE_TOKEN" } -ContentType "application/json" -Body $payload
```

Run the canonical support batch by extracting `cases[*].workflow_request` from:

```text
examples/support_workflow_contract_examples.json
```

## CLI Smoke Commands

```powershell
python scripts/aana_cli.py workflow-check --workflow examples/workflow_crm_support_reply.json --audit-log eval_outputs/audit/support-agent.jsonl
python scripts/aana_cli.py agent-check --event examples/agent_event_support_reply.json --audit-log eval_outputs/audit/support-agent.jsonl
python scripts/aana_cli.py audit-validate --audit-log eval_outputs/audit/support-agent.jsonl
python scripts/aana_cli.py audit-summary --audit-log eval_outputs/audit/support-agent.jsonl
```

## Web Playground

Open support examples directly:

```text
http://127.0.0.1:8765/playground?adapter=support_reply
http://127.0.0.1:8765/playground?adapter=crm_support_reply
http://127.0.0.1:8765/playground?adapter=email_send_guardrail
http://127.0.0.1:8765/playground?adapter=ticket_update_checker
http://127.0.0.1:8765/playground?adapter=invoice_billing_reply
```

The playground uses `POST /playground/check`, which returns the same Workflow Contract result shape as `/workflow-check` plus a redacted audit preview.

## Copyable Fixtures

- `examples/workflow_crm_support_reply.json`
- `examples/agent_event_support_reply.json`
- `examples/support_workflow_contract_examples.json`

The canonical support fixture file includes Workflow Contract and Agent Event examples for missing refund facts, verified refund ineligibility, payment data leakage, CRM note leakage, verification asks, verified email send, broad/BCC recipients, and private attachment blocking.
