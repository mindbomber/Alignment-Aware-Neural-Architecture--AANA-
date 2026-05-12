# AANA Enterprise Support Demo Flow

This is the polished buyer demo for the first enterprise-ops wedge:

```text
customer support + email send + ticket update
```

Run it with:

```powershell
python scripts/aana_cli.py enterprise-support-demo
```

The command writes:

- `support-email-ticket-batch.json`: the Workflow Contract batch.
- `audit.jsonl`: redacted runtime audit records.
- `metrics.json`: dashboard-ready audit metrics.
- `enterprise-dashboard.json`: buyer dashboard payload.
- `aix-report.json` and `aix-report.md`: the AIx Report.
- `demo-flow.json`: compact UI payload showing the demo story.
- `demo-summary.md`: reviewer-friendly walkthrough.

Open the local viewer from the repo root after running the command:

```powershell
python -m http.server 8123 --bind 127.0.0.1
```

Then visit:

```text
http://127.0.0.1:8123/web/enterprise-support-demo/
```

## What The Buyer Sees

The demo shows the full runtime governance loop:

1. AI proposes a support reply, email send, and ticket update.
2. AANA checks each proposed action against evidence and constraints.
3. AIx score and verifier findings appear.
4. Unsafe actions are revised or deferred before execution.
5. Redacted audit records are written.
6. Dashboard metrics update from the redacted audit log.
7. A buyer-facing AIx Report is generated.

This is pilot demo evidence only. It is not production certification.
