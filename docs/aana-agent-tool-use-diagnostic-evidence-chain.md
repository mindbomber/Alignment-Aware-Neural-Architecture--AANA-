# AANA Agent Tool-Use Diagnostic Evidence Chain

Result label: `diagnostic_heldout_chain`

This report ties together three Hugging Face-derived tool-use experiments for AANA as an audit/control/verification/correction layer. It does not claim raw autonomous agent task-performance superiority, and it is not an official leaderboard submission.

## Evidence Chain

| Step | Artifact | What it tests |
| --- | --- | --- |
| Broad tool-use control | `eval_outputs/agent_tool_use_hf_experiment_results.json` | Whether AANA blocks unsafe/private/write/unknown tool calls compared with a plain permissive agent. |
| Public/private read routing | `eval_outputs/public_private_read_routing_hf_experiment_results.json` | Whether AANA allows harmless public reads while escalating private reads without adequate authorization. |
| Authorization robustness | `eval_outputs/authorization_robustness_hf_experiment_results.json` | Whether AANA holds under noisy authorization and evidence conditions. |

Summary artifact: `eval_outputs/aana_agent_tool_use_diagnostic_evidence_chain.json`

## Current Measurements

| Metric | AANA v2 | Plain permissive baseline |
| --- | ---: | ---: |
| Broad tool-use unsafe-action recall | 1.000 | 0.000 |
| Broad tool-use safe allow rate | 1.000 | n/a |
| Public-read allow rate | 1.000 | 1.000 |
| Private-read escalation rate | 1.000 | n/a |
| False public allow rate on private reads | 0.000 | 1.000 |
| Authorized private-read allow rate | 1.000 | 1.000 |
| Missing-auth recall under noisy evidence | 1.000 | 0.000 |
| Stale-evidence defer rate | 1.000 | 0.000 |
| Contradictory-evidence defer/refuse rate | 1.000 | n/a |
| Private-read mislabel correction rate | 1.000 | 0.000 |
| Authorization robustness over-block rate | 0.000 | 0.000 |

## Over-Block Investigation

The authorization robustness run initially showed a `0.017` safe-public over-block rate. The single over-blocked case was a public directory search tool, `github_search_users`, from MCP-Atlas. The gate interpreted the token `users` as private identity-bound even though the event was declared `public_read` and only contained a generic query argument.

The fix was general, not benchmark-specific: public search/list style tools with no identity-bound argument keys remain public reads. Direct identity-bound access still routes as private when the tool or arguments require it.

After rerunning the experiment, AANA v2 reached:

- safe public-read allow rate: `1.000`
- missing-auth recall: `1.000`
- stale-evidence defer rate: `1.000`
- contradictory-evidence defer/refuse rate: `1.000`
- private-read mislabel correction rate: `1.000`
- route-family accuracy: `1.000`
- over-block rate: `0.000`

## Claim Boundary

These artifacts support this narrow claim:

> AANA can serve as an audit/control/verification/correction layer around agent tool calls, preserving public-read execution while blocking or escalating private reads and noisy authorization/evidence failures.

They do not prove:

- AANA is a raw agent-performance engine.
- AANA improves every autonomous task success metric.
- The labels are human-reviewed or benchmark-maintainer accepted.
- These are official leaderboard results.

## Limitations

- Labels are diagnostic and contract/span-derived unless separately reviewed.
- HF rows are transformed into Agent Action Contract v1 events, so the results validate the control layer, not the original benchmark task.
- MCPHunt is read through metadata because Dataset Viewer row access is unavailable for that dataset.
- Stronger public claims require a maintainer-accepted protocol or human-reviewed labels.
