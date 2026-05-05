# AANA vs. SOTA LLMs and Multimodal Models

This note explains why AANA-style architecture is not the same thing as simply using a stronger frontier LLM or multimodal model.

Modern state-of-the-art models already include many alignment ingredients: instruction tuning, preference optimization, policy training, refusal behavior, tool use, retrieval, safety classifiers, critique-and-revision behavior, and sometimes inference-time reasoning over safety rules. Those methods matter, and AANA is compatible with them.

AANA differs because it treats alignment as an explicit runtime architecture around the model:

```text
S = (f_theta, E_phi, R, Pi_psi, G)
```

- `f_theta`: the base generator, which may be any strong LLM or multimodal model.
- `E_phi`: verifier stack for factual, human-impact, task, policy, and feedback-integrity constraints.
- `R`: retrieval or grounding module that supplies evidence for the specific decision.
- `Pi_psi`: correction policy that chooses `accept`, `revise`, `retrieve`, `ask`, `refuse`, or `defer`.
- `G`: alignment gate that decides whether the final answer or action may pass.

In short: a SOTA model is usually the generator. AANA is the auditable correction loop that surrounds the generator.

## What SOTA Models Usually Internalize

Frontier models often bake alignment pressure into training and product serving layers. That can improve the average response, but the user often cannot inspect which rule fired, which evidence was checked, which verifier failed, or why a risky action was revised instead of accepted.

Typical SOTA alignment mechanisms include:

- post-training with human or AI feedback,
- safety and policy classifiers,
- system prompts and tool policies,
- constitutional or policy-aware training,
- retrieval-augmented generation,
- self-critique or hidden deliberation,
- product middleware that blocks or rewrites some outputs.

These mechanisms can be powerful, but they are usually opaque to downstream teams and generic across many domains.

## What AANA Externalizes

AANA makes the correction machinery explicit:

- the candidate answer is not treated as final,
- verifier results are represented as structured evidence,
- correction actions are constrained to a small action set,
- domain evidence is part of the gate decision,
- failures can route to `retrieve`, `ask`, `refuse`, or `defer`,
- audit records can preserve decision metadata without storing raw private text,
- high-risk domains can increase correction pressure through beta scaling.

That externalization matters when an AI system is used for actions, workflow updates, customer replies, file operations, medical/legal/financial routing, deployment checks, or other cases where a polished answer can still be unsafe or unsupported.

## Why This Is Not Already Fully Baked Into Base Models

### 1. Deployment Constraints Are Local

A base model provider does not know your CRM records, refund policy, jurisdiction, account permissions, CI status, file path scope, calendar availability, data-retention rules, or production rollout plan. AANA adapters let each environment declare those constraints and evidence sources at runtime.

### 2. Verifiers Need Calibration and Ownership

A verifier can be wrong. AANA treats verifier calibration, fallback behavior, and human escalation as first-class production concerns. That is different from assuming one hidden classifier or one hidden model judgment is enough.

### 3. Runtime Gates Cost Latency and Infrastructure

A full loop can add retrieval calls, verifier passes, correction passes, audit writes, and human-review routing. General-purpose chat products often optimize for latency and conversational fluidity. AANA is for cases where the cost is justified by the consequence of a false accept.

### 4. Multimodal Inputs Increase the Need for Explicit Evidence

Multimodal models can inspect images, audio, documents, and screens, but that does not automatically prove that an answer obeyed the right policy, source boundary, consent rule, or action precondition. AANA can turn multimodal observations into evidence objects that verifiers and gates can inspect.

### 5. Hidden Alignment Is Hard to Govern

When alignment behavior is only inside weights or hidden middleware, downstream teams cannot easily audit failure modes, compare adapters, tune thresholds, or explain why a decision was accepted, revised, refused, or deferred. AANA favors inspectable contracts over hidden reassurance.

## Practical Difference

| Question | Strong SOTA model alone | AANA-style architecture |
|---|---|---|
| Where does generation happen? | Inside the model. | Inside a base model used as `f_theta`. |
| Where are domain constraints stored? | Often in prompt, policy, fine-tuning, or hidden middleware. | In adapters, workflow contracts, evidence registries, and governance policy. |
| What happens after a candidate answer? | Usually answer, refuse, or tool-call based on internal behavior. | Verify, retrieve, revise, ask, refuse, defer, or accept through an explicit gate. |
| Can a team audit why an answer passed? | Often limited to logs and product traces. | Audit records can include adapter, gate decision, action, violations, and fingerprints. |
| Does it guarantee safety? | No. | No. It makes correctability and failure routing explicit. |

## Relationship to Current Alignment Research

AANA is not opposed to training-time alignment, constitutional methods, deliberative alignment, retrieval-augmented generation, tool use, or multimodal reasoning. It can use all of them.

The distinction is architectural:

- Training-time alignment improves the model's learned behavior.
- Product guardrails filter or steer some model behavior.
- AANA defines a runtime correction loop with explicit verifiers, evidence, actions, and an alignment gate.

The best production version is likely a combination: strong aligned model as the generator, strong retrieval and tool interfaces as evidence, calibrated verifiers, domain adapters, audit integrity, and human review for high-impact uncertainty.

Related public examples of AANA-adjacent ingredients include [Anthropic's Constitutional AI](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback), which uses written principles and AI feedback to improve harmlessness, and [OpenAI's deliberative alignment](https://openai.com/index/deliberative-alignment/), which trains reasoning models to reason over safety specifications before answering. AANA's distinction is not that those ingredients are absent from frontier systems; it is that AANA makes the generator, evidence, verifiers, correction actions, gate, and audit trail explicit for a deployment.

## When to Prefer AANA

Use AANA-style architecture when:

- the system may take or prepare consequential actions,
- the right answer depends on environment-specific facts,
- false acceptance is costly,
- policy or evidence boundaries must be inspectable,
- the team needs audit records or human-review routing,
- correction is preferable to silent refusal or unchecked generation.

Use a plain SOTA model alone when the task is low-stakes, subjective, exploratory, or has no stable verifier or evidence source.
