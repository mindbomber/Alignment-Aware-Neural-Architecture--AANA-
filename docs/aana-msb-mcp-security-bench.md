# AANA MSB / MCP Security Bench Submission Artifact

Result label: `external_benchmark_protocol_submission`

This artifact targets [MCP Security Bench (MSB)](https://huggingface.co/datasets/DongsenZhang/MSB) as an agent tool-use/control benchmark. It evaluates AANA as a pre-tool-call audit/control/verification/correction layer, not as a base LLM and not as a raw autonomous task-performance engine.

## Benchmark Fit

MSB is a strong AANA target because it tests MCP-specific attacks across the tool-use pipeline:

- tool signature attacks
- tool parameter attacks
- tool response attacks
- retrieval injection attacks
- mixed MCP attack chains

AANA sits before tool execution and checks the Agent Action Contract v1 fields: tool category, authorization state, evidence refs, risk domain, proposed arguments, and recommended route.

## What Was Run

Script:

```bash
python scripts/benchmarks/run_msb_mcp_security_bench.py \
  --output docs/evidence/peer_review/msb_mcp_security_bench_aana_results.json
```

Dataset source:

- `DongsenZhang/MSB`
- configs: `agent_task`, `attack_task`, `attack_type`
- source: Hugging Face raw dataset files on the main branch

The runner converts published MSB benign task/tool pairs and attack-task templates into AANA pre-tool-call events. Benchmark labels are not provided to the gate. Labels are used only after AANA returns a route.

## Current Measurements

| Metric | Plain permissive agent | AANA v2 |
| --- | ---: | ---: |
| Cases | 124 | 124 |
| MSB attack cases | 60 | 60 |
| Attack block rate / unsafe-action recall | 0.000 | 1.000 |
| Safe public-read allow rate | 1.000 | 1.000 |
| Benign consequential-action control rate | 0.000 | 0.930 |
| Schema failure rate | 0.000 | 0.000 |
| Route-family accuracy | 0.516 | 0.976 |

Interpretation:

- A permissive agent executes all attack templates.
- AANA blocks or escalates every converted MSB attack template.
- AANA allows safe public-read cases.
- AANA often asks or defers on benign writes/private reads because those are consequential actions and need authorization/evidence before execution.

## Claim Boundary

This is not a full MSB harness replay. The HF Dataset Viewer exposes task/template rows, not the complete generated 2,000+ attack execution logs. This artifact is therefore a protocol-level submission and reproducible control-layer validation.

Full leaderboard-grade evidence should replay the MSB GitHub harness with AANA inserted directly before MCP tool execution, then run MSB's native `metrics.py` over logs and operation outputs.

## Next Step

For official MSB review, submit this artifact as a maintainer-review protocol first:

- result JSON: `docs/evidence/peer_review/msb_mcp_security_bench_aana_results.json`
- runner: `scripts/benchmarks/run_msb_mcp_security_bench.py`
- claim: AANA is an MCP pre-tool-call control layer
- request: confirm whether maintainers want a harness PR, standalone result artifact, or issue/discussion first
