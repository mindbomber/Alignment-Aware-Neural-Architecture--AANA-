#!/usr/bin/env python3
"""Validate support-specific SLA and undecidable failure policy."""

from __future__ import annotations

import argparse
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "examples" / "support_sla_failure_policy.json"
REQUIRED_FALLBACKS = {
    "evidence_unavailable": {"retrieve", "ask"},
    "crm_unavailable": {"defer"},
    "verification_missing": {"ask"},
    "privacy_risk": {"refuse"},
    "policy_ambiguity": {"defer"},
    "bridge_unavailable_irreversible": {"refuse", "defer"},
    "bridge_unavailable_draft": {"ask", "defer"},
}
REQUIRED_SUPPORT_ADAPTERS = {
    "support_reply",
    "crm_support_reply",
    "email_send_guardrail",
    "ticket_update_checker",
    "invoice_billing_reply",
}
REQUIRED_AUDIT_TERMS = {
    "fallback_condition_id",
    "audit_code",
    "execution mode",
    "human review route",
}
FORBIDDEN_AUDIT_TERMS = {
    "raw customer message",
    "raw candidate response",
    "full CRM record",
    "payment data",
    "internal notes",
    "attachment bodies",
    "secrets",
    "tokens",
}


def load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def validate_support_sla_failure_policy(path=DEFAULT_POLICY):
    payload = load_json(path)
    errors = []

    if payload.get("default_failure_action") != "defer":
        errors.append("default_failure_action must be defer.")

    adapters = set(payload.get("scope", {}).get("adapters", []))
    missing_adapters = sorted(REQUIRED_SUPPORT_ADAPTERS - adapters)
    if missing_adapters:
        errors.append(f"scope.adapters missing support adapters: {', '.join(missing_adapters)}")

    allowed_actions = set(payload.get("allowed_actions", []))
    if allowed_actions != {"accept", "revise", "retrieve", "ask", "defer", "refuse"}:
        errors.append("allowed_actions must be accept, revise, retrieve, ask, defer, refuse.")

    fallbacks = payload.get("undecidable_fallbacks", [])
    fallbacks_by_id = {item.get("id"): item for item in fallbacks}
    missing_fallbacks = sorted(set(REQUIRED_FALLBACKS) - set(fallbacks_by_id))
    if missing_fallbacks:
        errors.append(f"undecidable_fallbacks missing: {', '.join(missing_fallbacks)}")

    for fallback_id, required_actions in REQUIRED_FALLBACKS.items():
        fallback = fallbacks_by_id.get(fallback_id, {})
        actions = set(fallback.get("allowed_actions", []))
        if actions != required_actions:
            errors.append(f"{fallback_id}: allowed_actions must be {', '.join(sorted(required_actions))}.")
        if fallback.get("default_action") not in required_actions:
            errors.append(f"{fallback_id}: default_action must be one of its allowed_actions.")
        for field in ("condition", "safe_response", "audit_code"):
            if not str(fallback.get(field, "")).strip():
                errors.append(f"{fallback_id}: {field} is required.")
        if fallback_id in {"crm_unavailable", "privacy_risk", "policy_ambiguity"} and fallback.get("human_review") is not True:
            errors.append(f"{fallback_id}: human_review must be true.")

    irreversible = fallbacks_by_id.get("bridge_unavailable_irreversible", {})
    if irreversible.get("failure_mode") != "fail_closed":
        errors.append("bridge_unavailable_irreversible.failure_mode must be fail_closed.")
    if irreversible.get("default_action") != "refuse":
        errors.append("bridge_unavailable_irreversible.default_action must be refuse.")

    draft = fallbacks_by_id.get("bridge_unavailable_draft", {})
    if draft.get("failure_mode") != "fail_advisory_when_mode_allows":
        errors.append("bridge_unavailable_draft.failure_mode must be fail_advisory_when_mode_allows.")
    if draft.get("default_action") not in {"ask", "defer"}:
        errors.append("bridge_unavailable_draft.default_action must be ask or defer.")

    mode_policy = payload.get("mode_policy", {})
    for mode in ("shadow", "advisory", "enforced"):
        if mode not in mode_policy:
            errors.append(f"mode_policy missing {mode}.")
    if mode_policy.get("advisory", {}).get("bridge_unavailable_irreversible") != "fail_closed":
        errors.append("advisory bridge_unavailable_irreversible must fail_closed.")
    if mode_policy.get("enforced", {}).get("bridge_unavailable_irreversible") != "fail_closed":
        errors.append("enforced bridge_unavailable_irreversible must fail_closed.")
    if mode_policy.get("advisory", {}).get("bridge_unavailable_draft") != "fail_advisory":
        errors.append("advisory bridge_unavailable_draft must fail_advisory.")

    sla_targets = payload.get("sla_targets", {})
    for target_id, target in sla_targets.items():
        if not isinstance(target.get("target_latency_ms"), int) or target["target_latency_ms"] <= 0:
            errors.append(f"{target_id}: target_latency_ms must be a positive integer.")
        if not isinstance(target.get("max_latency_ms"), int) or target["max_latency_ms"] < target.get("target_latency_ms", 0):
            errors.append(f"{target_id}: max_latency_ms must be >= target_latency_ms.")
        if target.get("on_timeout") not in {"ask", "defer", "refuse"}:
            errors.append(f"{target_id}: on_timeout must be ask, defer, or refuse.")
    if sla_targets.get("support_email_send", {}).get("on_timeout") != "refuse":
        errors.append("support_email_send.on_timeout must be refuse.")

    audit_text = " ".join(payload.get("audit_requirements", []))
    for term in REQUIRED_AUDIT_TERMS:
        if term not in audit_text:
            errors.append(f"audit_requirements must include {term!r}.")
    for term in FORBIDDEN_AUDIT_TERMS:
        if term not in audit_text:
            errors.append(f"audit_requirements must forbid {term!r}.")

    release_gate = payload.get("release_gate", {})
    if release_gate.get("script") != "scripts/validate_support_sla_failure_policy.py":
        errors.append("release_gate.script must point to scripts/validate_support_sla_failure_policy.py.")
    if release_gate.get("category") != "production-profile":
        errors.append("release_gate.category must be production-profile.")
    if release_gate.get("blocks_release") is not True:
        errors.append("release_gate.blocks_release must be true.")

    return {
        "valid": not errors,
        "errors": errors,
        "fallback_count": len(fallbacks),
        "required_fallbacks": sorted(REQUIRED_FALLBACKS),
        "support_adapters": sorted(adapters),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default=DEFAULT_POLICY, help="Support SLA/failure policy JSON artifact.")
    args = parser.parse_args(argv)
    report = validate_support_sla_failure_policy(args.policy)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
