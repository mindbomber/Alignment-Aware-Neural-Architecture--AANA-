"""Example AANA Python integration client usage."""

import os

import aana


client = aana.client(
    base_url=os.environ.get("AANA_BRIDGE_URL", "http://127.0.0.1:8765"),
    token=os.environ.get("AANA_BRIDGE_TOKEN"),
    shadow_mode=True,
)

request = client.workflow_request(
    adapter="research_summary",
    request="Answer using only Source A and label uncertainty.",
    candidate="The claim is proven by Source C.",
    evidence=client.evidence(
        "Source A: The available evidence is incomplete.",
        source_id="source-a",
        retrieved_at="2026-05-05T00:00:00Z",
    ),
    constraints=["Do not cite unretrieved sources."],
)

result = client.workflow_check(request)
print(result["recommended_action"])
