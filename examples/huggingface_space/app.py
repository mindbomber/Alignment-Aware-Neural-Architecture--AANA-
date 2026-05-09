"""Minimal Hugging Face Space demo for AANA Agent Action Contract v1.

The public Space surface must keep accepting these seven frozen fields:
tool_name, tool_category, authorization_state, evidence_refs, risk_domain,
proposed_arguments, and recommended_route.
"""

from __future__ import annotations

import json

import aana


EXAMPLE_EVENT = {
    "tool_name": "send_email",
    "tool_category": "write",
    "authorization_state": "user_claimed",
    "evidence_refs": ["draft_id:123"],
    "risk_domain": "customer_support",
    "proposed_arguments": {"to": "customer@example.com"},
    "recommended_route": "accept",
}


def check_json_event(event_json: str) -> str:
    """Return a pretty AANA decision for a pasted contract event."""

    payload = json.loads(event_json)
    result = aana.check_tool_call(payload)
    return json.dumps(result, indent=2, sort_keys=True)


def build_demo():
    """Build the optional Gradio UI only when the Space runtime imports it."""

    import gradio as gr

    with gr.Blocks(title="Try AANA") as demo:
        gr.Markdown("# AANA Agent Action Contract v1")
        event = gr.Code(
            value=json.dumps(EXAMPLE_EVENT, indent=2),
            language="json",
            label="Agent Action Contract v1 event",
        )
        output = gr.Code(language="json", label="AANA decision")
        gr.Button("Check tool call").click(check_json_event, inputs=event, outputs=output)
    return demo


if __name__ == "__main__":
    build_demo().launch()
