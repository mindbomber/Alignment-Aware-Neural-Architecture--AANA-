# AANA Metrics Dashboard

The local HTTP bridge serves a reviewer dashboard at:

```powershell
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/aana-dashboard.jsonl --shadow-mode
```

Open:

```text
http://127.0.0.1:8765/dashboard
```

The dashboard reads only redacted audit records through `GET /dashboard/metrics`. It does not render raw prompts, candidates, evidence, safe responses, outputs, private records, or source documents.

## What Reviewers See

- Gate pass/fail counts.
- Recommended action counts.
- Top violation codes and daily violation trends.
- AIx average, minimum, and maximum scores.
- AIx hard-blocker totals and top blocker codes.
- Adapter-level breakdowns for checks, actions, violations, AIx, hard blockers, and shadow-mode behavior.
- Family-level breakdowns for usage, would-block rate, revise/defer/refuse rate, AIx average/min/max, hard blockers, human-review escalations, and evidence-missing rate.
- Shadow-mode would-block and would-intervene rates.

## Dashboard Feed

The JSON feed is:

```text
GET /dashboard/metrics
```

It returns `audit_dashboard_version`, `cards`, `aix`, `gate_decisions`, `recommended_actions`, `violation_trends`, `top_violations`, `hard_blockers`, `adapter_breakdown`, `family_breakdown`, `role_breakdown`, `shadow_mode`, and the underlying redacted `metrics_export`.

The MI observability feed is:

```text
GET /dashboard/mi-metrics
```

It reads `docs/evidence/peer_review/mi_pilot/research_citation/mi_dashboard.json` and returns pass/fail rate, propagated error rate, correction success rate, false accept/refusal rates, global AIx drift, and workflow rows for the Mechanistic Interoperability panel.

If the bridge was not started with `--audit-log`, the dashboard returns a waiting state with zero counts. Once checks append redacted audit records, refresh the page to review pilot behavior.

## Review Interpretation

Use the dashboard to decide whether AANA is improving safety and workflow quality in a pilot:

- A high revise/defer rate can be useful in shadow mode when it reveals risky actions that production currently allows.
- A high hard-blocker count usually means missing evidence, policy, approval, or private-data controls need work before enforcement.
- AIx average/min/max should be reviewed with hard blockers; a numeric score does not override a hard gate.
- Adapter breakdowns help identify where pilots need better evidence connectors, policy tuning, or user workflow changes.
