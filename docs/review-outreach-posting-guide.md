# AANA Review Outreach Posting Guide

Use this guide to ask for technical review without hype or overclaiming.

Core message:

```text
AANA is a pre-action control layer for AI agents: agents propose actions,
AANA checks evidence/auth/risk, and tools execute only when the route is accept.
```

Claim boundary:

```text
AANA is being shared for review as an audit/control/verification/correction
layer, not as a proven raw agent-performance engine.
```

Primary links:

- Try AANA in 2 minutes: <https://huggingface.co/spaces/mindbomber/aana-demo>
- Agent Action Contract v1: <https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/agent-action-contract-v1.md>
- Short technical report: <https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/aana-pre-action-control-layer-technical-report.md>
- Evidence pack: <https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack>
- GitHub repo: <https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA->

## Review Questions

Ask reviewers for concrete failures:

- Are routes correct?
- Are false positives acceptable?
- Is evidence handling sufficient?
- Does this generalize beyond examples?
- Can non-`accept` routes execute anywhere in an integration?
- Which benchmark or trace set would make this more convincing?

## Where To Post

Prefer communities where AANA directly maps to the conversation:

- GitHub Discussions or issues on agent/eval/security repos when there is an
  active thread about tool safety, MCP security, eval harnesses, authorization,
  audit logging, or groundedness.
- Hugging Face Discussions on the AANA model, evidence pack, and Space.
- LinkedIn posts for AI governance, agent safety, auditability, and compliance
  audiences.
- Reddit cautiously, especially `r/LocalLLaMA`, `r/MachineLearning`, and
  `r/LLMDevs`, only when the post is framed as review request and follows the
  subreddit rules.
- Discords for LangChain, OpenAI developers, MCP, evals, and AI safety only in
  channels meant for projects, feedback, evals, or open-source review.
- AI safety/evals communities where control-layer evidence, benchmark tracks,
  and failure analysis are welcome.

Do not mass-post. Use fewer, higher-quality posts that ask a specific technical
question.

## GitHub Discussion / Issue Comment

Use only when relevant to an existing discussion or maintainer request.

```markdown
I am looking for technical review on AANA as a pre-action control layer for AI
agents.

Pattern:

```text
agent proposes -> AANA checks evidence/auth/risk -> tool executes only if route == accept
```

The specific reason I think it may be relevant here is tool-use control:
blocking unsafe/private/write calls, preserving safe public reads, and emitting
audit-safe decision events before execution.

I am not claiming AANA is a better base agent or a raw task-performance engine.
The current claim is narrower: AANA may be useful as an audit/control/
verification/correction layer around existing agents.

Review links:

- Try it: https://huggingface.co/spaces/mindbomber/aana-demo
- Contract: https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/agent-action-contract-v1.md
- Short report: https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/aana-pre-action-control-layer-technical-report.md
- Evidence pack: https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack

Useful critique:

- Would the route be correct for your tool/eval cases?
- Are false positives acceptable?
- Is the evidence/auth model sufficient?
- Would you accept a control-layer/wrapper submission track?
```

## Hugging Face Discussion

```markdown
Seeking technical review of AANA as a pre-action control layer for AI agents.

AANA's pattern is:

```text
agent proposes -> AANA checks evidence/auth/risk -> tool executes only if route == accept
```

The public claim is narrow: AANA is being evaluated as an audit/control/
verification/correction layer, not as a proven raw agent-performance engine.

Please challenge:

1. Are routes correct?
2. Are false positives acceptable?
3. Is evidence handling sufficient?
4. Does this generalize beyond examples?

Links:

- Try AANA: https://huggingface.co/spaces/mindbomber/aana-demo
- Evidence pack: https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack
- Short report: https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/aana-pre-action-control-layer-technical-report.md
- Agent Action Contract v1: https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/agent-action-contract-v1.md
```

## LinkedIn

```text
I am looking for technical review on AANA, an open-source pre-action control
layer for AI agents.

The idea is simple:

agent proposes -> AANA checks evidence/auth/risk -> tools execute only when the
route is accept

This is not a claim that AANA is a better base agent. The current claim is that
it can make agent workflows more auditable, safer, more grounded, and more
controllable by enforcing a typed pre-action contract, blocked-tool
non-execution, and audit-safe decision logs.

I am especially looking for critiques from people working on agent tool use,
MCP, evals, AI governance, compliance, and security:

- Are routes correct?
- Are false positives acceptable?
- Is evidence handling sufficient?
- Does this generalize beyond examples?

Try AANA:
https://huggingface.co/spaces/mindbomber/aana-demo

Short report:
https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/aana-pre-action-control-layer-technical-report.md

Evidence pack:
https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack
```

## Reddit

Use a title that asks for review, not attention.

```text
Seeking review: AANA, a pre-action control layer for AI agent tool calls
```

Body:

```markdown
I am looking for technical criticism, not promotion.

AANA is an open-source pre-action control layer for AI agents:

```text
agent proposes -> AANA checks evidence/auth/risk -> tool executes only if route == accept
```

The goal is not to replace a base model or agent. The goal is to make tool use,
private reads, writes, grounded answers, and audit logging more controllable
before execution.

What I would like reviewers to challenge:

- Are routes correct?
- Are false positives acceptable?
- Is evidence handling sufficient?
- Does this generalize beyond examples?
- What benchmark or trace set would make this more convincing?

Try AANA:
https://huggingface.co/spaces/mindbomber/aana-demo

Short report:
https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/aana-pre-action-control-layer-technical-report.md

Evidence pack:
https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack

Known limitations: this is not yet proven as a raw agent-performance engine;
some labels are diagnostic; stronger claims need maintainer-accepted benchmark
protocols or external human-reviewed traces.
```

## Discord

Keep Discord posts shorter and ask before dropping multiple links.

```text
Is this a good channel to ask for review of an open-source agent tool-control
layer?

AANA is a pre-action gate:
agent proposes -> AANA checks evidence/auth/risk -> tools execute only on accept.

I am looking for critique on route correctness, false positives, evidence
handling, and whether it generalizes beyond examples. Happy to share the Space,
contract, and evidence pack if this is appropriate here.
```

If the channel says yes:

```text
Thanks. Links:

Try AANA: https://huggingface.co/spaces/mindbomber/aana-demo
Short report: https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/aana-pre-action-control-layer-technical-report.md
Evidence pack: https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack
Contract: https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/agent-action-contract-v1.md
```

## AI Safety / Evals Communities

```markdown
I am seeking review of AANA as a control-layer architecture for agent workflows.

The claim under review is intentionally narrow: AANA can make agents more
auditable, safer, more grounded, and more controllable by enforcing a
pre-action contract before consequential tool calls or grounded answers execute.

It is not yet proven as a raw agent-performance engine.

The most useful review would challenge:

- route correctness under ambiguous evidence,
- false positives and safe allow rate,
- authorization-state assumptions,
- evidence freshness/provenance/redaction handling,
- whether the diagnostic evidence generalizes to external traces,
- what benchmark protocol would be fair for a control-layer submission.

Short report:
https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/blob/master/docs/aana-pre-action-control-layer-technical-report.md

Evidence pack:
https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack
```

## Posting Rules

- Post only where AANA is directly relevant to the channel topic.
- Lead with "seeking review" or "request for critique."
- Include limitations in the first post.
- Do not claim official leaderboard status unless the benchmark maintainer has
  accepted the submission protocol.
- Do not claim AANA is proven as a raw agent-performance engine.
- Do not post the same text repeatedly across many communities.
- Follow each community's self-promotion and project-post rules.
