# AANA Public Roadmap

Current public claim:

```text
AANA is a pre-action control layer for AI agents: agents propose actions,
AANA checks evidence/auth/risk, and tools execute only when the route is accept.
```

Claim boundary: AANA is being developed as an audit/control/verification/
correction layer around agents. It is not yet proven as a raw agent-performance
engine.

This roadmap is intentionally practical. Each item should either improve
developer adoption, external validity, runtime safety, or public review quality.

## Status Key

- `stable`: public contract or workflow is frozen except for backward-compatible
  additions.
- `active`: implemented enough to use, but still being hardened or validated.
- `next`: planned near-term work.
- `blocked`: waiting on external review, maintainer feedback, or real-world
  pilot access.

## 1. Contract Stability

Status: `stable` for Agent Action Contract v1, `active` for compatibility
testing.

Goal: make AANA useful as a reusable standard, not a one-off repo.

Current:

- Agent Action Contract v1 is frozen around seven required fields:
  `tool_name`, `tool_category`, `authorization_state`, `evidence_refs`,
  `risk_domain`, `proposed_arguments`, and `recommended_route`.
- Route semantics are centralized for `accept`, `revise`, `retrieve`, `ask`,
  `defer`, and `refuse`.
- Execution rule is uniform: only `accept` can execute.
- Contract freeze tests cover Python SDK, TypeScript SDK, FastAPI, MCP, docs,
  examples, and Hugging Face Space surfaces.

Next:

- Add more negative compatibility fixtures for malformed evidence, unknown
  tools, stale authorization, contradictory evidence, and route alias drift.
- Publish compact JSON Schema examples for every major route.
- Keep future v2/v3 fields backward-compatible by default.

Exit criteria:

- Public examples and SDK/API/MCP surfaces continue to pass contract freeze
  tests in `python scripts/validate_aana_platform.py --timeout 240`.

## 2. SDK / API / MCP Integrations

Status: `active`.

Goal: make the adoption path simple:

```text
agent proposes -> AANA checks -> tool executes only if route == accept
```

Current:

- Python SDK exposes `aana.check_tool_call(...)`, `aana.gate_action(...)`, and
  `aana.wrap_agent_tool(...)`.
- TypeScript SDK mirrors the decision shape.
- FastAPI service exposes `GET /health`, `POST /pre-tool-check`, and
  `POST /agent-check`.
- MCP-style surface exposes `aana_pre_tool_check`.
- Runnable examples cover plain Python, OpenAI Agents SDK, LangChain, AutoGen,
  CrewAI, MCP, and FastAPI API-guard usage.
- Integration validator currently checks route parity, blocked-tool
  non-execution, decision-shape parity, audit completeness, and schema behavior.

Next:

- Add more realistic side-effect mocks for email, file export, deployment,
  payment, CRM update, and private read tools.
- Add TypeScript examples matching the Python integration examples.
- Add Docker/local-service examples for FastAPI API-guard deployment.
- Expand middleware recovery examples for `ask`, `retrieve`, `defer`, and
  `refuse`, not just blocked writes.

Exit criteria:

- `python scripts/validation/validate_agent_integrations.py` remains the public
  integration proof and passes on a clean checkout.

## 3. Hugging Face Held-Out Validation

Status: `active`.

Goal: use HF datasets to calibrate and test adapter families without tuning and
claiming on the same split.

Current:

- Dataset registry tracks calibration, held-out validation, and external
  reporting split use.
- Public evidence pack includes privacy/PII, grounded QA, tool-use control,
  public/private read routing, authorization robustness, safety/adversarial,
  finance, governance/compliance, and integration validation artifacts.
- Privacy/PII and grounded QA experiments are labeled diagnostic where claims
  are not yet strong enough.

Next:

- Continue false-positive reduction on privacy/PII while preserving high-risk
  recall.
- Improve grounded QA semantic contradiction and baseless-claim detection using
  calibrated verifier layers.
- Expand agent tool-use held-out traces with noisier evidence and ambiguous
  authorization states.
- Add governance/compliance datasets with human-reviewed labels where
  available.

Exit criteria:

- Every adapter family used in public claims has at least one held-out external
  validation artifact and clear split isolation.

## 4. Benchmark Submissions

Status: `active` for protocol artifacts, `blocked` for official leaderboard
claims until maintainer-accepted protocols exist.

Goal: submit AANA as a control layer or wrapper where that is the appropriate
benchmark track.

Current:

- Public evidence distinguishes diagnostic artifacts from official leaderboard
  claims.
- MSB / MCP Security Bench protocol artifact exists for MCP attack-template
  conversion.
- MCP-Bench wrapper work targets paired runs: same base agent plain vs same base
  agent with AANA before MCP tool execution.
- Maintainer-facing language asks for a control-layer/wrapper track rather than
  pretending AANA is a standalone model row.

Next:

- Ask benchmark maintainers whether they accept control-layer submissions.
- Run focused paired slices where unsafe/private/write actions are expected.
- Prefer benchmarks that can measure blocked-tool non-execution, safe public
  reads, audit events, and route correctness.
- Publish limitations next to every submission artifact.

Exit criteria:

- At least one benchmark maintainer accepts the protocol for an AANA
  control-layer/wrapper submission or gives concrete requested changes.

## 5. False-Positive Reduction

Status: `active`.

Goal: preserve high unsafe recall without making AANA unusably conservative.

Current:

- Public/private read routing and authorization robustness have already exposed
  where safe public reads can be over-blocked.
- Privacy/PII experiments show recall gains can hurt safe allow rate unless
  calibration is category-specific.
- Grounded QA experiments show numeric/entity checks can improve recall, but
  semantic contradiction needs calibrated verifier support.

Next:

- Track false positives by adapter family and route type.
- Separate calibration splits from held-out reporting splits.
- Add safe near-miss cases after every adapter change.
- Require held-out validation after adapter improvements.
- Add user-facing recovery quality metrics for false-positive cases:
  can the agent ask, retrieve, revise, or defer productively?

Exit criteria:

- Public reports include false-positive rate, safe allow rate, over-refusal
  rate, and representative false-positive examples for each adapter family.

## 6. Real-World Pilots

Status: `next` for external pilots, `active` for internal/starter pilot kits.

Goal: move from diagnostic examples to controlled, auditable pilots with real
workflow owners.

Current:

- Starter pilot kits exist for enterprise, personal productivity, and
  government/civic bundles.
- Internal pilot scripts can generate redacted audit logs, metrics, reviewer
  reports, and field-note templates.
- Public claim boundary remains conservative: pilot-ready does not mean
  production-certified.

Next:

- Recruit design partners in agent frameworks, MCP tooling, support operations,
  governance/compliance, security/devops, and research/grounded QA.
- Run shadow-mode pilots before enforcement-mode pilots.
- Require domain-owner signoff, incident handling, audit retention, connector
  permission review, and human-review paths.
- Publish only redacted, aggregate, permissioned pilot findings.

Exit criteria:

- At least one external pilot reports route quality, false positives,
  blocked-tool non-execution, audit usefulness, latency, and operator feedback
  with permission to publish an anonymized summary.

## Near-Term Priorities

1. Keep Agent Action Contract v1 stable while expanding compatibility tests.
2. Strengthen examples and SDK/API/MCP wrappers so developers can adopt AANA in
   minutes.
3. Continue HF held-out validation with strict split governance.
4. Target benchmark submissions where AANA is evaluated as a control layer.
5. Reduce false positives without weakening unsafe/private/write recall.
6. Start controlled real-world pilots with audit-safe reporting.

## How To Track Progress

Use these commands locally:

```powershell
python scripts/validate_aana_platform.py --timeout 240
python scripts/validation/validate_agent_integrations.py
python scripts/publication/build_peer_review_evidence_pack.py
```

Public artifacts:

- Try AANA: <https://huggingface.co/spaces/mindbomber/aana-demo>
- Evidence pack: <https://huggingface.co/datasets/mindbomber/aana-peer-review-evidence-pack>
- GitHub review discussion: <https://github.com/mindbomber/Alignment-Aware-Neural-Architecture--AANA-/discussions/8>
- Short technical report: [aana-pre-action-control-layer-technical-report.md](aana-pre-action-control-layer-technical-report.md)
