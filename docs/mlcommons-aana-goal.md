# MLCommons AANA Contribution Goal

AANA's MLCommons workstream is to help make benchmark and evaluation artifacts more auditable, safer to publish, easier to reproduce, and clearer about claim boundaries.

Core positioning:

> AANA helps MLCommons-adjacent workflows by adding audit/control/verification/provenance infrastructure, not by claiming better raw benchmark performance.

## Contribution Rules

- Use issues and pull requests, not direct commits to MLCommons default branches.
- Keep contributions generic and dependency-light unless maintainers explicitly request AANA integration.
- Do not claim AANA improves MLPerf performance.
- Label result artifacts as diagnostic, unofficial, official, held-out, probe-only, or external-reporting.
- Avoid storing raw secrets, tokens, private paths, full private arguments, or sensitive data in public logs or manifests.
- Prefer optional schemas, examples, validators, and docs before runtime changes.

## Active Threads

| Area | Repository | Contribution | Status |
| --- | --- | --- | --- |
| MLCube audit manifests | `mlcommons/mlcube` | Optional `mlcube.run_audit.v1` manifest proposal | Open issue: <https://github.com/mlcommons/mlcube/issues/367> |
| MLCube cookiecutter | `mlcommons/mlcube_cookiecutter` | Scaffold optional manifest example | Open issue: <https://github.com/mlcommons/mlcube_cookiecutter/issues/10> |
| MLCube examples | `mlcommons/mlcube_examples` | Add `hello_world/audit_manifest.example.json` | Open PR: <https://github.com/mlcommons/mlcube_examples/pull/70> |
| AILuminate safety smoke test | `mlcommons/ailuminate` | AANA demo prompt gate summary over public demo prompts | Open PR, CLA blocked: <https://github.com/mlcommons/ailuminate/pull/34> |
| ModelBench hazard detector | `mlcommons/modelbench` | Detector route/audit metadata proposal | Commented on issue: <https://github.com/mlcommons/modelbench/issues/1512#issuecomment-4422153155> |
| Croissant RAI metadata | `mlcommons/croissant` | Evidence refs, redaction status, and claim status for dataset RAI fields | Commented on issue: <https://github.com/mlcommons/croissant/issues/1012#issuecomment-4422162947> |
| MLPerf automation provenance | `mlcommons/mlperf-automations` | Optional run audit sidecar proposal | Open issue: <https://github.com/mlcommons/mlperf-automations/issues/955> |

## Planned Tracks

### 1. Safety And Risk Evaluation

Target repositories:

- `mlcommons/ailuminate`
- `mlcommons/modelbench`
- `mlcommons/jailbreak-taxonomy`

Useful AANA contributions:

- Route taxonomy for `accept`, `revise`, `ask`, `defer`, and `refuse`.
- Audit-safe failure case records.
- False-positive and false-negative reporting fields.
- Evidence-backed safety decision records.
- Claim-boundary language for diagnostic vs official results.

### 2. Dataset Provenance And Safety Metadata

Target repositories:

- `mlcommons/croissant`
- `mlcommons/BioCroissant`
- `mlcommons/datasets-contrib`
- `mlcommons/dataperf`

Useful AANA contributions:

- Dataset evidence reference examples.
- Privacy/PII risk labels.
- Redaction status fields.
- License/provenance completeness checks.
- Public-claim eligibility metadata.

### 3. MLPerf Automation And Result Provenance

Target repositories:

- `mlcommons/mlperf-automations`
- `mlcommons/ck`
- `mlcommons/mlcflow`
- `mlcommons/cm4mlperf-results`

Useful AANA contributions:

- Optional audit manifest generation after automation runs.
- Result manifest validation.
- Reproducibility confidence fields.
- Public-claim status and redaction status.
- Secret-safe logging examples.

### 4. Medical And Federated Evaluation

Target repositories:

- `mlcommons/medperf`
- `mlcommons/GaNDLF`
- `mlcommons/GaNDLF-Synth`

Useful AANA contributions:

- Audit-safe federated evaluation logs.
- Private-data non-leakage checks.
- Human-review escalation markers.
- Model output provenance examples.

### 5. Policies And Governance

Target repositories:

- `mlcommons/policies`
- `mlcommons/training_policies`
- `mlcommons/inference_policies`
- `mlcommons/automotive_policies`

Useful AANA contributions:

- Reproducibility evidence language.
- Safety/risk reporting fields.
- Public claim boundary language.
- Audit metadata requirements for submitted artifacts.

## Execution Checklist

- [x] Start with MLCube audit manifest proposal.
- [x] Add an example-only manifest PR to `mlcube_examples`.
- [x] Propose safety route/audit metadata in AILuminate or ModelBench.
- [x] Propose dataset redaction/provenance metadata in Croissant or datasets-contrib.
- [x] Propose automation result audit manifest in mlperf-automations or mlcflow.
- [ ] Summarize accepted, pending, and rejected maintainer feedback in AANA docs.
