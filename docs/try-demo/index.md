# Try Demo

Use this entry point when you want to see AANA work before integrating it into an app or building a new adapter.

## Recommended Local Path

This is the one recommended developer path for local platform onboarding:

1. Install the repo.
2. Run `doctor`.
3. Run one gallery example.
4. Run a Workflow Contract check.
5. Start the HTTP bridge with audit logging.
6. Inspect the redacted audit output.

```powershell
python -m pip install -e .
aana doctor
aana run travel_planning
aana workflow-check --workflow examples/workflow_research_summary.json --audit-log eval_outputs/audit/local-onboarding.jsonl
python scripts/aana_server.py --host 127.0.0.1 --port 8765 --audit-log eval_outputs/audit/aana-bridge.jsonl
aana audit-summary --audit-log eval_outputs/audit/local-onboarding.jsonl
```

The bridge exposes `http://127.0.0.1:8765/ready`, `http://127.0.0.1:8765/playground`, `http://127.0.0.1:8765/adapter-gallery`, `/workflow-check`, `/agent-check`, and `/openapi.json`.

## Hosted Demo

Try the hosted synthetic demo if you want to inspect behavior before installing:

- [Hosted demo](../demo/index.html)
- [Tool call gate demo](../tool-call-demo/index.html)
- [Hosted demo notes](../hosted-demo.md)
- [Adapter gallery](../adapter-gallery/index.html)

The demo surfaces use synthetic examples only. They cannot send, delete, deploy, purchase, export, or store secrets.

## Advanced Research And Eval Workflows

Research/eval workflows are separate from platform onboarding. Use them after the recommended local path when you need benchmark-style scoring, model-provider runs, paper tables, or experimental comparison artifacts:

- [Evaluation design](../evaluation-design.md)
- [Results interpretation](../results-interpretation.md)
- [Pilot evaluation kit](../pilot-evaluation-kit.md)
- [Paper pilot results](../paper-pilot-results-section.md)

## What To Read Here

- [Getting started](../getting-started.md): command hub and local install basics.
- [Hosted demo](../hosted-demo.md): static browser demo boundary.
- [Local desktop/browser demos](../local-desktop-browser-demos.md): local demo runner notes.
- [Adapter gallery](../adapter-gallery.md): searchable catalog of workflows.
- [Application playbook](../application-playbook.md): where the demo pattern fits in real workflows.
- [Results interpretation](../results-interpretation.md): how to read demo/eval outputs without overstating them.

Production positioning: this repository is demo-ready and pilot-ready for controlled evaluation, but it is not production-certified by itself. Production readiness requires live evidence connectors, domain owner signoff, audit retention, observability, and human review paths.
