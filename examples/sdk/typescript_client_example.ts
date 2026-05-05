import { AanaClient, workflowRequest } from "../../sdk/typescript/src/index";

const client = new AanaClient({
  baseUrl: process.env.AANA_BRIDGE_URL ?? "http://127.0.0.1:8765",
  token: process.env.AANA_BRIDGE_TOKEN,
  shadowMode: true
});

const request = workflowRequest({
  adapter: "research_summary",
  request: "Answer using only Source A and label uncertainty.",
  candidate: "The claim is proven by Source C.",
  evidence: client.evidence("Source A: The available evidence is incomplete.", {
    source_id: "source-a",
    retrieved_at: new Date().toISOString()
  }),
  constraints: ["Do not cite unretrieved sources."]
});

const result = await client.workflowCheck(request);
console.log(result.recommended_action);
