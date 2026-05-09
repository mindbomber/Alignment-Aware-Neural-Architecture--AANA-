# AANA Generalization Audit

This audit exists to keep AANA architecture work separate from benchmark-specific
score chasing. A benchmark can expose failure modes, but production AANA changes
must improve the verifier, grounding, correction policy, or gate in a way that
transfers beyond one known task instance.

## Current Finding

The tau2 scaffold in `examples/tau2/aana_contract_agent.py` contains two kinds of
logic:

- General AANA logic: pre-tool-call gate events, v1/v2 routing, tool-category
  inference, authorization-state checks, evidence summaries, correction modes,
  and base/gate/gate-plus-correction ablations.
- Benchmark probes: exact task/user/order/item/payment identifiers and exact
  recovery flows discovered from a small tau2 slice.

Benchmark probes are useful for diagnosing what a general planner should learn,
but they are not evidence that AANA generalized. They must be reported as probes
or disabled for general runs.

The scaffold now keeps these probe paths outside the general scaffold and behind
`--allow-benchmark-probes`. The default path should be treated as the general
architecture path.

The default workflow is explicitly non-probe only: `workflow_scope` is
`general_non_probe`, and diagnostic probes require both
`--allow-benchmark-probes` and `AANA_ENABLE_DIAGNOSTIC_PROBES=1`.

## Generalization Standard

A change counts as general AANA work only if it satisfies all of the following:

- It operates from runtime evidence, policy, tool metadata, user intent, and
  retrieved records, not known benchmark answers.
- It does not hardcode benchmark task IDs, user IDs, order IDs, item IDs, payment
  method IDs, exact names, exact emails, exact zip codes, or exact hidden labels.
- It can be tested on held-out tasks whose identifiers and entity values were not
  visible during implementation.
- Every adapter improvement must include a held-out, blind, external, or
  maintainer-eval validation record before it is considered complete.
- It has an ablation against at least one baseline and reports both success and
  safety/control metrics.
- It preserves the AANA loop: generator, evidence/retrieval, verifier stack,
  correction policy, and gate.

## Adapter Audit

### Retail tau2 order workflow

Status: general adapter scaffold implemented; needs held-out validation.

Implemented:

- Parses identity facts from user messages.
- Locates the user with available identity tools.
- Reads user details and derives candidate orders dynamically.
- Selects relevant orders and items from retrieved order records by workflow,
  status, order reference, and requested product names.
- Fetches product records for product IDs found in retrieved orders.
- Scores replacement variants from user constraints and retrieved product
  options such as size, color, brightness, material, power source, capacity,
  availability, and price.
- Requires explicit confirmation before write tools.
- Constructs write arguments only from retrieved records and selected variants.

Remaining risks:

- Product and option matching is lexical, not yet a learned or model-judged
  semantic matcher.
- Multi-order workflows may need better batching and confirmation summaries.
- Cancellation reason extraction is not yet fully implemented.
- Held-out retail validation is required before treating results as public
  evidence of generalization.

### Banking card recommendation

Status: partially general within the tau2 banking domain.

Acceptable pieces:

- Uses policy retrieval before recommending.
- Scores cards against stated constraints.
- Avoids private account lookup for general product advice.

Risks:

- Product names and scoring weights are encoded directly in the scaffold.
- This should become a data-driven adapter config or policy-derived product
  scorer before being treated as general banking architecture.

Required replacement:

- Extract product candidates from retrieved policy evidence.
- Score candidates from structured policy facts when available.
- Keep domain-specific product names in adapter configuration, not scaffold code.

Current progress:

- Banking product names, card policy query text, planner guidance, subscription
  terms, and scorer weights now live in
  `examples/tau2/aana_tau2_adapter_config.json`.
- The scaffold ranks configured profiles generically instead of returning
  hardcoded card names from special-case branches.

### Banking identity / bypass workflow

Status: exact probe moved out of the general scaffold; remaining default logic is
generic identity-risk correction.

Issues:

- The exact bypass code, exact user identity strings, and target email now live
  only in `examples/tau2/aana_tau2_probe_planners.py`.
- That probe is useful for diagnosing authorization-state handling, but it is not
  a general identity-verification architecture.
- Default banking identity corrections now use generic email-conflict and
  missing-factor patterns, not known benchmark identities.

Required replacement:

- Represent recovery codes as evidence-backed claims with source, freshness, and
  validity checks.
- Log verification using verified user/account fields from records, not literal
  probe constants.
- Transfer to human review when evidence cannot validate the recovery path.

## TODO

1. Move benchmark probes out of the default scaffold path.
   - Done for tau2 retail generalization.
   - Done for the exact banking bypass probe by moving it to
     `examples/tau2/aana_tau2_probe_planners.py`, reachable only through
     `--allow-benchmark-probes`.
   - Done for default workflow hardening: diagnostic probes now require
     `AANA_ENABLE_DIAGNOSTIC_PROBES=1` in addition to the CLI flag, and run
     output labels the scope as `general_non_probe` or `diagnostic_probe_only`.

2. Strengthen the general retail workflow planner.
   - Add a typed `OrderWorkflowState` dataclass instead of an internal dict.
   - Replace lexical product/option matching with a semantic matcher.
   - Add robust multi-order batching for return, exchange, and modify workflows.
   - Add cancellation reason extraction and validation.
   - Add unit fixtures for identity, order selection, item selection, variant
     scoring, confirmation tracking, and write argument construction.

3. Convert domain constants into adapter configuration.
   - Product catalog names, card profiles, and policy query templates should live
     in adapter JSON or retrieved evidence, not hardcoded scaffold logic.

4. Add a benchmark-fitting lint.
   - Flag task IDs, exact user IDs, order IDs, product IDs, item IDs, payment IDs,
     and known benchmark names inside general adapter paths.
   - Allow those literals only in fixtures, expected outputs, or explicitly named
     probe files.
   - Current enforcement: `python scripts/validate_benchmark_fit_lint.py`
     validates `examples/benchmark_fit_lint_manifest.json`.
   - Coverage now includes checked-in adapter JSON files, starter pilot adapter
     configs, tau2 scaffolds, adapter-runner family modules, and benchmark/eval
     scripts.

5. Add held-out validation gates.
   - Every adapter improvement must be tested on at least one held-out slice.
   - Current enforcement: `python scripts/validate_adapter_heldout.py` validates
     `examples/adapter_heldout_validation.json`.
   - The gate rejects training, tuning, dev, calibration, or probe-enabled runs as
     evidence for a completed adapter improvement.
   - Report public claims only from runs without `--allow-benchmark-probes`.
   - Coverage now treats adapter JSON files, starter pilot configs, tau2 adapter
     config/scaffold files, adapter-runner modules, adapter-gallery data, and
     family docs/data as adapter-family surfaces that require held-out validation
     records when changed.

6. Update benchmark reporting language.
   - Label probe runs as diagnostic.
   - Label default runs as architecture/generalization runs.
   - Never merge probe results into public AANA claims.
   - Current enforcement: `python scripts/validate_benchmark_reporting.py`
     validates `examples/benchmark_reporting_manifest.json`.
   - Public claims are blocked if they include probe results, use
     `--allow-benchmark-probes`, lack limitations, or mark mixed/probe runs as
     public-claim eligible.

7. Refactor tau2 scaffolding.
   - Keep `aana_contract_agent.py` as the general scaffold.
   - Move probe planners into a separate file such as
     `examples/tau2/aana_tau2_probe_planners.py`.
   - Make imports explicit and opt-in for diagnostic experiments only.
   - Current status: complete for the known exact banking bypass probe.

## Decision Rule

If a change makes a benchmark score better because it knows the answer, reject it
from the general AANA path. If a change makes the system better at discovering,
verifying, correcting, asking, deferring, or refusing from runtime evidence, it is
eligible for the general AANA path.

Operational gate:

- `python scripts/validate_benchmark_fit_lint.py` blocks known answer literals in
  general scaffold paths.
- `python scripts/validate_adapter_heldout.py` blocks adapter improvements that
  lack held-out evidence.
- `python scripts/validate_benchmark_reporting.py` blocks public claims that mix
  diagnostic probe results into measured AANA claims.
- `python scripts/validate_hf_dataset_registry.py` blocks accidental reuse of
  the same Hugging Face dataset/config/split for both calibration/tuning and
  external-reporting/public claims.
