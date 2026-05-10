# Public Review And Adoption

AANA is a pre-action control layer for AI agents: agents propose actions, AANA checks evidence/auth/risk, and tools execute only when the route is accept.

The runtime pattern is:

```text
agent proposes -> AANA checks evidence, authorization, risk, and auditability -> tools execute only on accept
```

Claim boundary: AANA is not yet proven as a raw agent-performance engine. Public results must stay labeled as calibration, held-out, diagnostic, probe-only, or external-reporting artifacts.

## Who Should Review AANA

- Agent framework maintainers building tool-use, orchestration, or middleware systems.
- MCP, function-calling, and tool-runtime developers who need pre-execution policy checks.
- AI safety, alignment, evals, and LLMOps researchers studying hallucination, authorization, and agent-control failures.
- Security, privacy, governance, compliance, and audit teams responsible for consequential agent actions.
- Regulated-domain platform teams in finance, healthcare, legal, education, HR, public services, and enterprise support.
- Benchmark maintainers who want a control-layer or wrapper track rather than only raw model/agent leaderboards.

## Try AANA In Two Minutes

- Try AANA in 2 minutes: <https://huggingface.co/spaces/mindbomber/aana-demo>
- Static docs demo: [tool-call-demo/index.html](tool-call-demo/index.html)
- Agent Action Contract v1 standard: [agent-action-contract-v1.md](agent-action-contract-v1.md)
- Agent Action Contract quickstart: [agent-action-contract-quickstart.md](agent-action-contract-quickstart.md)
- OpenAI Agents quickstart: [openai-agents-quickstart.md](openai-agents-quickstart.md)
- Runtime integration guide: [integrate-runtime/index.md](integrate-runtime/index.md)
- Public artifact hub: [aana-public-artifact-hub.md](aana-public-artifact-hub.md)
- Short technical report: [aana-pre-action-control-layer-technical-report.md](aana-pre-action-control-layer-technical-report.md)
- Detailed agent-action report: [aana-agent-action-technical-report.md](aana-agent-action-technical-report.md)
- Public roadmap: [public-roadmap.md](public-roadmap.md)
- Maintainer review / benchmark submission request: [maintainer-review-benchmark-submission-request.md](maintainer-review-benchmark-submission-request.md)
- Review outreach posting guide: [review-outreach-posting-guide.md](review-outreach-posting-guide.md)
- GitHub review discussion: <https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/discussions/8>
- Peer-review evidence pack: <https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack>

Local validation:

```powershell
python scripts/validate_aana_platform.py --timeout 240
python scripts/validation/validate_agent_integrations.py
```

## What Reviewers Should Challenge

- Route correctness: should the action be `accept`, `revise`, `retrieve`, `ask`, `defer`, or `refuse`?
- False positives: does AANA block safe public reads or harmless requests too often?
- Evidence handling: are missing, stale, contradictory, or low-trust evidence refs handled correctly?
- Authorization state: are `none`, `user_claimed`, `authenticated`, `validated`, and `confirmed` interpreted consistently?
- Blocked-tool non-execution: do wrappers actually prevent execution when AANA does not return `accept`?
- Audit safety: do logs include route, AIx score, blockers, missing evidence, auth state, and latency without raw secrets or private arguments?
- Generalization: does the behavior come from runtime evidence and contract rules rather than benchmark probes or answer keys?

## Integration Targets

AANA is meant to wrap agents, not replace them. The adoption path is:

```text
base agent or app -> AANA pre-action check -> tool executes only if route == accept -> audit event emitted
```

Supported or documented surfaces:

- CLI: `aana pre-tool-check`, `aana agent-check`, `aana audit-summary`, `aana evidence-pack`
- Python SDK: `aana.check_tool_call(...)`
- TypeScript SDK
- FastAPI policy service: `POST /pre-tool-check`, `POST /agent-check`
- MCP tool-call guard
- OpenAI Agents SDK, LangChain, AutoGen, and CrewAI middleware examples

## Shareable Summary

AANA is an open-source architecture for adding an auditable control layer around AI agents. It standardizes a pre-action contract, checks evidence and authorization before consequential tools execute, routes unsupported or unsafe actions to revise/ask/defer/refuse, and emits audit-safe decision logs. The current evidence supports AANA as an audit/control/verification/correction layer, not as a proven raw agent-performance engine.

## Review Request

If you are evaluating AANA, the most useful feedback is concrete:

- a tool call AANA should have blocked but allowed,
- a safe action AANA over-blocked,
- an evidence or authorization state the contract does not represent cleanly,
- an integration surface where non-`accept` routes can still execute,
- a benchmark or dataset where a control-layer submission would be appropriate.

For GitHub outreach and PRs, use the [community issue intake and PR targeting
policy](community-issue-intake.md). The short version: only open PRs where AANA
directly improves agent tool safety, MCP security, eval harnesses, audit
logging, authorization checks, or groundedness/citation verification.
